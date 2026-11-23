# PyInstaller spec: 2 file .exe dùng chung thư viện
#   DubStudio.exe         — app có giao diện (không hiện cửa sổ console)
#   DubStudio-worker.exe  — bản console chạy tác vụ nặng ở process riêng (Demucs, kiểm tra GPU)
# Build: .venv\Scripts\pyinstaller packaging\dubstudio.spec --noconfirm --distpath build\dist --workpath build\work
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
datas, hidden = [], []
for pkg in ("rapidocr_onnxruntime", "demucs", "faster_whisper", "edge_tts", "certifi"):
    datas += collect_data_files(pkg)
for pkg in ("demucs", "dora", "julius", "openunmix", "lameenc", "edge_tts", "faster_whisper", "ctranslate2",
            "soundfile", "rapidocr_onnxruntime", "yt_dlp"):
    hidden += collect_submodules(pkg)
hidden += ["core.toolops", "core.voicematch", "core.metadata", "core.gpucheck", "core.asr", "core.separate"]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "jupyter", "pytest", "PyQt5", "PyQt6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = str(ROOT / "packaging" / "dubstudio.ico")

app_exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DubStudio", console=False, icon=icon,
              upx=False, version=None)
worker_exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="DubStudio-worker", console=True, icon=icon,
                 upx=False)
coll = COLLECT(app_exe, worker_exe, a.binaries, a.datas, upx=False, name="DubStudio")
