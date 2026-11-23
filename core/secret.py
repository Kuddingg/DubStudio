"""Mã hóa API key bằng Windows DPAPI (CryptProtectData) trước khi lưu vào settings.json.

- Chỉ đúng tài khoản Windows đã lưu mới giải mã được → copy settings.json sang máy khác / người khác
  thì key không đọc được (phải nhập lại), không lộ key dạng chữ thường trong file.
- Không cần cài thêm thư viện (gọi thẳng crypt32.dll qua ctypes).
"""
from __future__ import annotations

import base64
import ctypes
import sys
from ctypes import wintypes

PREFIX = "dpapi:"
_ENTROPY = b"DubStudio-api-keys-v1"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    b = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    b._buf = buf          # giữ tham chiếu để buffer không bị thu hồi
    return b


def _call(fn, data: bytes) -> bytes:
    inp, ent, out = _blob(data), _blob(_ENTROPY), _Blob()
    ok = fn(ctypes.byref(inp), None, ctypes.byref(ent), None, None, 0x01, ctypes.byref(out))   # UI_FORBIDDEN
    if not ok:
        raise OSError(ctypes.WinError())
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def protect(text: str) -> str:
    if not text or sys.platform != "win32":
        return text
    return PREFIX + base64.b64encode(_call(ctypes.windll.crypt32.CryptProtectData, text.encode("utf-8"))).decode()


def unprotect(value: str) -> str:
    """Giải mã; giá trị cũ chưa mã hóa (bản trước) thì trả nguyên. Không giải mã được (máy/tài khoản khác) → ''."""
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value or ""
    try:
        return _call(ctypes.windll.crypt32.CryptUnprotectData, base64.b64decode(value[len(PREFIX):])).decode("utf-8")
    except (OSError, ValueError):
        return ""


SECRET_FIELDS = ("api_keys",)


def encrypt_section(d: dict) -> dict:
    return {k: (protect(v) if k in SECRET_FIELDS and isinstance(v, str) else v) for k, v in d.items()}


def decrypt_section(d: dict) -> dict:
    return {k: (unprotect(v) if k in SECRET_FIELDS else v) for k, v in d.items()}
