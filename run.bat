@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo [DubStudio] Lan chay dau: dang tao moi truong Python va cai thu vien, mat vai phut...
    python -m venv .venv || (echo Khong tim thay Python 3.11. Hay cai Python roi chay lai. & pause & exit /b 1)
    .venv\Scripts\python.exe -m pip install --upgrade pip
    where nvidia-smi >nul 2>nul
    if %errorlevel%==0 (
        echo [DubStudio] Phat hien GPU NVIDIA: cai PyTorch ban CUDA
        .venv\Scripts\pip.exe install torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118
        .venv\Scripts\pip.exe install onnxruntime-gpu
    ) else (
        echo [DubStudio] Khong co GPU NVIDIA: cai PyTorch ban CPU
        .venv\Scripts\pip.exe install torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu
    )
    .venv\Scripts\pip.exe install -r requirements.txt || (echo Cai thu vien loi, xem thong bao o tren. & pause & exit /b 1)
)
start "" .venv\Scripts\pythonw.exe main.py
