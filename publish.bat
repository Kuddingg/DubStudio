@echo off
chcp 65001 >nul
REM Phát hành bản mới cho người dùng (chạy SAU build.bat). Xem HUONG_DAN_CAP_NHAT.md
cd /d "%~dp0"
.venv\Scripts\python.exe -X utf8 packaging\publish.py
pause
