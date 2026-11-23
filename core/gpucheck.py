"""Kiểm tra khả năng tăng tốc phần cứng trên máy đang chạy (dùng khi mang app sang máy có GPU).

Thử THẬT từng phần thay vì chỉ đọc tên card:
- Encoder video: NVENC (NVIDIA), QuickSync (Intel), AMF (AMD) → encode thử 1 giây.
- PyTorch CUDA (Demucs tách nhạc chạy GPU).
- onnxruntime CUDA (OCR chạy GPU).
- CTranslate2 CUDA (nhận giọng nói ASR chạy GPU).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .media import NOWIN, which

ENCODERS = [("NVIDIA NVENC", "h264_nvenc"), ("Intel QuickSync", "h264_qsv"), ("AMD AMF", "h264_amf")]


def _py(code: str, timeout: int = 120) -> tuple[bool, str]:
    from .runtime import python_cmd
    try:
        r = subprocess.run([*python_cmd(), "-c", code], capture_output=True, text=True, timeout=timeout,
                           creationflags=NOWIN, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return False, "quá thời gian"
    out = (r.stdout or "").strip().splitlines()
    return r.returncode == 0, (out[-1] if out else (r.stderr or "").strip().splitlines()[-1:][0] if r.stderr else "")


def _encoder_ok(codec: str) -> tuple[bool, str]:
    ff = which("ffmpeg")
    if not ff:
        return False, "không có FFmpeg"
    r = subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=30:d=1",
                        "-c:v", codec, "-f", "null", "-"], capture_output=True, text=True, creationflags=NOWIN, timeout=60)
    if r.returncode == 0:
        return True, "encode thử thành công"
    return False, "không dùng được trên máy này (không có card / driver tương ứng)"


def run() -> dict:
    res: list[tuple[str, bool | None, str]] = []
    gpu = ""
    smi = which("nvidia-smi")
    if smi:
        r = subprocess.run([smi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, creationflags=NOWIN, timeout=20)
        gpu = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
    res.append(("Card NVIDIA", bool(gpu), gpu or "không tìm thấy (nvidia-smi)"))

    working = []
    for name, codec in ENCODERS:
        ok, msg = _encoder_ok(codec)
        res.append((f"Encoder {name}", ok, msg))
        if ok:
            working.append(name)

    ok, msg = _py("import torch;print(('CUDA ' + torch.version.cuda + ' · ' + torch.cuda.get_device_name(0)) "
                  "if torch.cuda.is_available() else 'NO')")
    torch_cuda = ok and msg != "NO"
    res.append(("Tách nhạc (PyTorch CUDA)", torch_cuda,
                msg if torch_cuda else ("PyTorch bản CPU → cài bản cu118 (xem requirements.txt)" if ok else msg or "chưa cài PyTorch")))

    ok, msg = _py("import onnxruntime as o;p=o.get_available_providers();print('CUDA' if 'CUDAExecutionProvider' in p else ','.join(p))")
    ort_cuda = ok and msg == "CUDA"
    res.append(("OCR (onnxruntime CUDA)", ort_cuda,
                "CUDAExecutionProvider sẵn sàng" if ort_cuda else ("chỉ có CPU → pip install onnxruntime-gpu" if ok else msg)))

    ok, msg = _py("import ctranslate2 as c;print(c.get_cuda_device_count())")
    ct_cuda = ok and msg.isdigit() and int(msg) > 0
    res.append(("Nhận giọng nói ASR (CUDA)", ct_cuda if ok else None,
                f"{msg} GPU" if ct_cuda else ("chỉ CPU" if ok else "chưa cài faster-whisper")))

    any_gpu = torch_cuda or ort_cuda or ct_cuda
    return {
        "items": res,
        "encoder": working[0] if working else "CPU · x264",
        "device": "GPU (CUDA)" if any_gpu else "CPU",
    }
