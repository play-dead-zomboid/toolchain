"""
Firearm / ranged weapon scoring (locked). Skill axis = Aiming. Normalized to the
base-game ranged distribution (cap guns and the new B42 .30-30 excluded -- no data).

Tuned from ~11k hours of play feedback, NOT a melee clone:
 - Range barely matters (you rarely shoot past ~30).
 - Noise is lethal ONLY when you can't clear what it pulls (loud + low effective
   capacity = death -- why 4-round bolt rifles are sleepers).
 - Pellets = 2-3 real kills/shot into a crowd (shotguns are crowd kings).
 - No magazine (revolvers, break/pump shotguns) is an ADVANTAGE: less reload
   friction = more shots = survival.
 - Piercing + stopping power matter (5.56 AR pierces -> horde favorite).
Reported as floor(Aiming 0) / neutral(5) / ceiling(10).
"""
import config
from common import num, flag, parse_weapon_txt, is_ranged

NEUTRAL_A=5; ZHP_R=1.0; CRIT_VALUE=0.80; W_POWER=0.80; W_REL=0.20

def uses_magazine(p): return bool(p.get("magazinetype"))     # detachable mag = reload friction
def avgdmg(p): return (num(p,"MinDamage")+num(p,"MaxDamage"))/2
def pellets(p): return max(num(p,"Projectilecount"),1)
def durv(p): return num(p,"ConditionMax")*num(p,"ConditionLowerChanceOneIn")
def is_auto(p): return "auto" in (p.get("firemode","")+p.get("firemodepossibilities","")).lower()
def gun_class(p):
    rt=p.get("weaponreloadtype","").lower()
    if "shotgun" in rt or pellets(p) > 1: return "Shotgun"   # pellets = the reliable shotgun signal
    if "handgun" in rt: return "Handgun"
    if "bolt" in rt or "rifle" in p.get("attachmenttype","").lower(): return "Rifle"
    return "Firearm"

def hitfrac(p,A):
    hc=num(p,"HitChance")+num(p,"AimingPerkHitChanceModifier",4)*A
    return min(max(hc/100.0,0.05),0.98)
def rof(p):                                                  # follow-up speed; auto is modest (noise/ammo)
    auto=1.2 if is_auto(p) else 1.0
    recoil=30.0/(num(p,"RecoilDelay",20)+10)
    acq=(40.0/(num(p,"Aimingtime",40)+20))**0.3
    return auto*recoil*acq
def kills_per_shot(p):
    lethal=min(1.20, avgdmg(p)/ZHP_R)                        # a body/head shot kills; overkill wasted
    crowd =1+min(pellets(p)-1,8)*0.20                        # pellets -> 2-3 kills/shot into a crowd
    if flag(p,"PiercingBullets"): crowd+=0.60                # penetrate a line of zombies
    return lethal*crowd

def power_raw(p,A):
    kills=kills_per_shot(p)
    crit=num(p,"CriticalChance")+num(p,"AimingPerkCritModifier",0)*A
    critM=1+crit/100.0*CRIT_VALUE
    hf=hitfrac(p,A)
    mag=max(num(p,"MaxAmmo"),num(p,"ClipSize"),1)
    effcap=mag*kills                                         # kills available before reloading
    noise=1-min(num(p,"SoundRadius")/200.0,1)*max(0,1-effcap/12.0)*0.35   # loud+can't-clear = danger
    friction=1.15 if not uses_magazine(p) else 1.0          # revolver/break/pump: no mag-swap dance
    stop=1+min((num(p,"StopPower")+num(p,"KnockdownMod"))/20.0,1)*0.15
    magsus=min(max((effcap/10.0)**0.30,0.75),1.30)
    rng=1+min(num(p,"MaxRange")/25.0,1)*0.06                 # range rarely matters past ~25-30
    return kills*hf*critM*rof(p)*noise*friction*stop*magsus*rng
def reliab(p): return 1-min(num(p,"JamGunChance")/10.0,0.20)

def _pct(vals,q):
    s=sorted(vals); return s[min(int(q*(len(s)-1)),len(s)-1)] if s else 0
def calibrate():
    base=parse_weapon_txt(config.BASE_WEAPON_TXT)
    rng={n:p for n,p in base.items() if is_ranged(p,n)}
    pw95=_pct([power_raw(p,NEUTRAL_A) for p in rng.values()],0.95) or 1.0
    rl95=_pct([reliab(p) for p in rng.values()],0.95) or 1.0
    cls={}
    for n,p in rng.items(): cls.setdefault(gun_class(p),[]).append(p)
    stats={}
    for c,ps in cls.items():
        stats[c]={"dmg":max(avgdmg(x)*pellets(x) for x in ps),"range":max(num(x,"MaxRange") for x in ps),
                  "ammo":max(max(num(x,"MaxAmmo"),num(x,"ClipSize")) for x in ps),
                  "crit":max(num(x,"CriticalChance") for x in ps),"hit":max(num(x,"HitChance") for x in ps),"n":len(ps)}
    return dict(pw95=pw95,rl95=rl95,classes=stats)

def record(name,p,cal):
    pw=lambda A:100*power_raw(p,A)/cal["pw95"]
    rel=100*reliab(p)/cal["rl95"]
    head=W_POWER*pw(NEUTRAL_A)+W_REL*rel
    return dict(name=name,cls=gun_class(p),hand="auto" if is_auto(p) else "semi",
        head=head,power=pw(NEUTRAL_A),floor=pw(0),ceil=pw(10),reliab=rel,
        dmg=avgdmg(p),hit=num(p,"HitChance"),crit=num(p,"CriticalChance"),rng=num(p,"MaxRange"),
        durab=0,pellets=pellets(p),mag=max(num(p,"MaxAmmo"),num(p,"ClipSize")),jam=num(p,"JamGunChance"),
        sound=num(p,"SoundRadius"),ammo=p.get("ammotype","").replace("base:","").replace("bullets_",""),
        wt=num(p,"Weight"),durv=durv(p))
def tier(s): return "S" if s>=78 else "A" if s>=62 else "B" if s>=46 else "C" if s>=30 else "D"

def outlier_flags(p,cal):
    c=gun_class(p); st=cal["classes"].get(c); fl=[]
    if not st: return fl
    dp=avgdmg(p)*pellets(p)
    if dp>st["dmg"]: fl.append(f"dmg×pellets {dp:.1f} > {c} vanilla max {st['dmg']:.1f}")
    if num(p,"MaxRange")>st["range"]: fl.append(f"range {num(p,'MaxRange'):.0f} > {c} vanilla max {st['range']:.0f}")
    mag=max(num(p,"MaxAmmo"),num(p,"ClipSize"))
    if mag>st["ammo"]: fl.append(f"mag {mag:.0f} > {c} vanilla max {st['ammo']:.0f}")
    if num(p,"CriticalChance")>st["crit"]: fl.append(f"crit {num(p,'CriticalChance'):.0f} > {c} vanilla max {st['crit']:.0f}")
    if num(p,"HitChance")>st["hit"]: fl.append(f"hitchance {num(p,'HitChance'):.0f} > {c} vanilla max {st['hit']:.0f}")
    return fl

KIND="ranged"
