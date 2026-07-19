"""
Machine-specific paths. THIS IS THE ONLY FILE YOU SHOULD NEED TO EDIT
if you run this on a different computer.

Edit the two Steam paths below to match where things live on your machine, and
drop the server's pzserver.ini in this folder. Then from here run:

    python generate.py
"""
import os

# 1) Where Steam downloaded the Project Zomboid workshop mods
#    (the folder full of numbered mod folders like 3722134990).
WORKSHOP_DIR = r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600"

# 2) The Project Zomboid base-game install (the 'vanilla' baseline we score against).
GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"

# 3) The server config that says which mods are actually ON our server.
#    We only score mods listed here (its WorkshopItems= and Mods= lines).
#    Drop a copy of the live server's pzserver.ini in THIS folder and keep it
#    current -- if it goes stale you are scoring last season's mod list.
SERVER_INI = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pzserver.ini")

# Where generated reports are written (defaults to ./output next to these scripts).
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

# Base-game weapon definitions (rarely needs changing).
BASE_WEAPON_TXT = os.path.join(GAME_DIR, "media", "scripts", "generated", "items", "weapon.txt")
