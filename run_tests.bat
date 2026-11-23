@echo off
chcp 65001 >nul
REM Chạy bộ test tự động.
REM   run_tests.bat        → test nhanh (vài giây, không cần mạng / FFmpeg)
REM   run_tests.bat all    → thêm test trên video thật (khoảng 1 phút, cần FFmpeg)
cd /d "%~dp0"
.venv\Scripts\python.exe -m pip install -q pytest
if /I "%1"=="all" (
    .venv\Scripts\python.exe -X utf8 -m pytest tests -v
) else (
    .venv\Scripts\python.exe -X utf8 -m pytest tests -v -m "not slow"
)
pause
