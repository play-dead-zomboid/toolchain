"""
Melee weapon scoring (v4, locked). Skill axis = the weapon's governing skill
(Short Blade / Long Blade / Blunt / Axe / Spear). Everything is normalized to the
base-game melee distribution, so 100 == top of vanilla and a mod weapon reading
150 is plainly out of line.

Headline = 70% Power + 30% sustain-gated Durability, at neutral skill (~5).
Power    = kills-per-swing (B42 damage spread across multi-hit) x crit x real
           attack-speed (from weight+handedness, NOT the unreliable Swingtime field)
           x sustain (stamina economy -- the spine of melee value).
Reported as floor(skill 0) / neutral / ceiling(skill 10) -- a weapon's value is a
curve over skill, not one number (knives: low floor, high ceiling).
"""
import math
import config
from common import num, flag, gcat, parse_weapon_txt, is_melee

# ---- tunable assumptions (calibrated vs vanilla + community tier lists) ----
ZHP=1.5; DMG_BASE_L=0.70; DMG_PER_L=0.06; CRIT_PER_L=2.5; CRIT_VALUE=0.80
STAM_PER_L=0.05; SUSTAIN_BETA=0.50; SUSTAIN_REF=1.5; NEUTRAL_L=5
CLUSTER=0.40; W_POWER=0.70; W_DUR=0.30; FINISHER_MIN_L=2

SKILL={"smallblade":"ShortBlade","longblade":"LongBlade","blunt":"Blunt","axe":"Axe","spear":"Spear"}
def tree(p):
    c=gcat(p)
    for k,t in SKILL.items():
        if k in c: return t
    return "Blunt"
def is_1h(p): return not(flag(p,"TwoHandWeapon") or flag(p,"RequiresEquippedBothHands"))
def speed(p):
    w=max(num(p,"Weight"),0.3); return (1.25 if is_1h(p) else 1.0)/(0.6+0.18*w)
def avgdmg(p): return (num(p,"MinDamage")+num(p,"MaxDamage"))/2
def durv(p): return num(p,"ConditionMax")*num(p,"ConditionLowerChanceOneIn")
def sustain_of(p,L):
    hand=1.2 if not is_1h(p) else 1.0
    stam=max(num(p,"Weight")*hand*(1.1-STAM_PER_L*L),0.1)
    return min(max((SUSTAIN_REF/stam)**SUSTAIN_BETA,0.5),1.8)

def power_raw(p,L):
    effDmg=avgdmg(p)*(DMG_BASE_L+DMG_PER_L*L)
    hit=num(p,"MaxHitcount"); kills=min(1+(hit-1)*CLUSTER, effDmg/ZHP)
    crit=min(95.0,num(p,"CriticalChance")+CRIT_PER_L*L); critMult=1+crit/100*CRIT_VALUE
    role=min(max(min(num(p,"MaxRange"),2.0)-1.0,0),1)*0.10
    role+=min(max(num(p,"KnockdownMod"),3 if flag(p,"AlwaysKnockdown") else 0)/3.0,1)*0.10
    role+=min(num(p,"PushBackMod"),1)*0.05
    cat=gcat(p)
    spec=0.08 if "axe" in cat else 0
    if ("smallblade" in cat or "spear" in cat) and L>=FINISHER_MIN_L:    # solo instakill finisher (~skill 2+)
        spec+=0.06
    return kills*speed(p)*critMult*sustain_of(p,L)*(1+role+spec)
def dur_raw(p): return math.log10(max(durv(p),1))

def _pct(vals,q):
    s=sorted(vals); return s[min(int(q*(len(s)-1)),len(s)-1)] if s else 0
def calibrate():
    items=parse_weapon_txt(config.BASE_WEAPON_TXT)
    melee={n:p for n,p in items.items() if is_melee(p,n)}
    pw95=_pct([power_raw(p,NEUTRAL_L) for p in melee.values()],0.95) or 1.0
    du95=_pct([dur_raw(p) for p in melee.values()],0.95) or 1.0
    trees={}
    for n,p in melee.items(): trees.setdefault(tree(p),[]).append(p)
    stats={}
    for t,ps in trees.items():
        stats[t]={"dmg":max(avgdmg(x) for x in ps),"crit":max(num(x,'CriticalChance') for x in ps),
                  "dur":max(durv(x) for x in ps),"hit":max(num(x,'MaxHitcount') for x in ps),
                  "range":max(num(x,'MaxRange') for x in ps),"n":len(ps)}
    return dict(pw95=pw95,du95=du95,classes=stats)

def record(name,p,cal):
    pw=lambda L:100*power_raw(p,L)/cal["pw95"]
    dur=100*dur_raw(p)/cal["du95"]
    dur_eff=dur*min(sustain_of(p,NEUTRAL_L),1.2)/1.2
    head=W_POWER*pw(NEUTRAL_L)+W_DUR*dur_eff
    return dict(name=name,cls=tree(p),hand="1H" if is_1h(p) else "2H",
        head=head,power=pw(NEUTRAL_L),floor=pw(0),ceil=pw(10),durab=dur,
        dmg=avgdmg(p),hit=num(p,"MaxHitcount"),crit=num(p,"CriticalChance"),
        rng=num(p,"MaxRange"),wt=num(p,"Weight"),durv=durv(p),sustain=sustain_of(p,NEUTRAL_L))
def tier(s): return "S" if s>=78 else "A" if s>=62 else "B" if s>=46 else "C" if s>=30 else "D"

def outlier_flags(p,cal):
    t=tree(p); st=cal["classes"].get(t); fl=[]
    if not st: return fl
    if avgdmg(p)>st["dmg"]: fl.append(f"dmg {avgdmg(p):.1f} > {t} vanilla max {st['dmg']:.1f}")
    if num(p,"CriticalChance")>st["crit"]: fl.append(f"crit {num(p,'CriticalChance'):.0f} > {t} vanilla max {st['crit']:.0f}")
    if durv(p)>st["dur"]: fl.append(f"durability {durv(p):.0f} > {t} vanilla max {st['dur']:.0f}")
    if num(p,"MaxHitcount")>st["hit"]: fl.append(f"hitcount {num(p,'MaxHitcount'):.0f} > {t} vanilla max {st['hit']:.0f}")
    if num(p,"MaxRange")>st["range"]: fl.append(f"range {num(p,'MaxRange'):.2f} > {t} vanilla max {st['range']:.2f}")
    return fl

KIND="melee"
