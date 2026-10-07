import json
import os
import shutil
import py7zr
import utility
import var

var.select_skin = "default"

print(f"Skin: {var.select_skin}")

def install_skin(path):
    if os.path.exists(f"skins/{os.path.splitext(os.path.basename(path))[0]}"):
        try:
            os.rmdir(f"skins/{os.path.splitext(os.path.basename(path))[0]}")
        except:
            shutil.rmtree(f"skins/{os.path.splitext(os.path.basename(path))[0]}")
    with py7zr.SevenZipFile(path, mode='r') as z:
        z.extractall(path=f"skins/{os.path.splitext(os.path.basename(path))[0]}")
        install_skin_config(f"skins/{os.path.splitext(os.path.basename(path))[0]}/skin.json")

def install_skin_config(path):
    with open(path, "r") as f:
        data = json.load(f)
        utility.set_skin(data["name"])

install_skin("default_2t.7z")
print(f"Skin: {var.select_skin}")
