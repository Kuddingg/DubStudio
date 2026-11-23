import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if getattr(sys, "frozen", False):
    # Bản cài đặt (.exe): thư mục cài (Program Files) không ghi được → dữ liệu nằm trong %LOCALAPPDATA%\DubStudio
    DATA = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DubStudio"
else:
    DATA = ROOT / "data"
CACHE = DATA / "cache"
PROJECTS = DATA / "projects"
PRESETS_FILE = DATA / "presets.json"
SETTINGS_FILE = DATA / "settings.json"

for _d in (DATA, CACHE, PROJECTS):
    _d.mkdir(parents=True, exist_ok=True)
