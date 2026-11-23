import ctypes
import importlib.util
import os
import platform
import subprocess

from .media import NOWIN, which


def _cpu() -> str:
    if os.name == "nt":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    return platform.processor() or "Không rõ"


def _ram_gb() -> float:
    if os.name != "nt":
        return 0.0

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    ms = MS()
    ms.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return ms.ullTotalPhys / 1024 ** 3


def _gpus() -> list[str]:
    if os.name != "nt":
        return []
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
            capture_output=True, text=True, timeout=20, creationflags=NOWIN)
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def detect() -> dict:
    gpus = _gpus()
    nvidia = next((g for g in gpus if "nvidia" in g.lower()), None)
    return {
        "cpu": _cpu(),
        "ram": f"{_ram_gb():.0f} GB",
        "gpu": nvidia or (gpus[0] if gpus else "Không tìm thấy"),
        "cuda": bool(nvidia),
        "ffmpeg": bool(which("ffmpeg")),
        "ffprobe": bool(which("ffprobe")),
        "yt-dlp": bool(which("yt-dlp")),
        "faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "demucs": importlib.util.find_spec("demucs") is not None or importlib.util.find_spec("audio_separator") is not None,
        "paddleocr": importlib.util.find_spec("paddleocr") is not None or importlib.util.find_spec("rapidocr_onnxruntime") is not None,
        "edge_tts": importlib.util.find_spec("edge_tts") is not None,
    }
