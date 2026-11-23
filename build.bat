@echo off
chcp 65001 >nul
REM Đóng gói DubStudio thành bộ cài .exe
REM Chạy trên máy nào thì bộ cài mang thư viện của máy đó:
REM   máy có GPU NVIDIA (đã cài PyTorch bản CUDA qua run.bat) -> bộ cài chạy được GPU.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Chua co moi truong .venv - hay chay run.bat mot lan truoc.
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m pip install -q pyinstaller
echo [1/3] Dong goi bang PyInstaller (mat vai phut)...
.venv\Scripts\pyinstaller.exe packaging\dubstudio.spec --noconfirm --distpath build\dist --workpath build\work --log-level WARN
if errorlevel 1 (
    echo Loi PyInstaller
    pause
    exit /b 1
)

echo [2/3] Chep FFmpeg vao goi...
if not exist build\dist\DubStudio\ffmpeg mkdir build\dist\DubStudio\ffmpeg
call :copyexe ffmpeg.exe || exit /b 1
call :copyexe ffprobe.exe || exit /b 1

echo [3/3] Tao bo cai...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo Chua co Inno Setup. Cai bang: winget install JRSoftware.InnoSetup
    echo Ban van chay duoc ban khong can cai dat: build\dist\DubStudio\DubStudio.exe
    pause
    exit /b 0
)
for /f "delims=" %%V in ('.venv\Scripts\python.exe -c "from core.version import VERSION; print(VERSION)"') do set "APPVER=%%V"
echo     Phien ban: %APPVER%
"%ISCC%" /Q /DAppVersion=%APPVER% packaging\installer.iss
if errorlevel 1 (
    echo Loi tao bo cai
    pause
    exit /b 1
)

echo [4/4] Tao ban portable (.zip, giai nen la chay, khong can cai)...
(
    echo DubStudio ban portable - du lieu luu trong thu muc data canh DubStudio.exe.
    echo Xoa file nay thi app luu du lieu vao %%LOCALAPPDATA%%\DubStudio nhu ban cai dat.
) > build\dist\DubStudio\portable.txt
if exist "build\installer\DubStudio-Portable-%APPVER%.zip" del "build\installer\DubStudio-Portable-%APPVER%.zip"
tar -a -c -f "build\installer\DubStudio-Portable-%APPVER%.zip" -C build\dist DubStudio
set "ZIPERR=%errorlevel%"
del build\dist\DubStudio\portable.txt
if not "%ZIPERR%"=="0" (
    echo Loi tao file zip portable
    pause
    exit /b 1
)
echo.
echo Xong! Bo cai va ban portable nam trong: build\installer\
explorer build\installer
exit /b 0

:copyexe
for /f "delims=" %%P in ('where %1 2^>nul') do (
    copy /y "%%P" build\dist\DubStudio\ffmpeg\ >nul
    exit /b 0
)
echo Khong tim thay %1 trong PATH - hay cai FFmpeg roi chay lai.
pause
exit /b 1
