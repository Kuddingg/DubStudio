# DubStudio

Ứng dụng Windows dịch và lồng tiếng video bằng AI: lấy phụ đề gốc (OCR chữ trên hình hoặc nhận giọng nói) →
dịch (Gemini / Ollama) → tách nhạc nền (Demucs) → lồng tiếng (Edge TTS) → căn khớp thời gian → xuất video (FFmpeg).

- **Tải về**: [bản mới nhất](https://github.com/Kuddingg/DubStudio/releases/latest) → mục Assets →
  `DubStudio-Setup-x.y.z.exe`. Hướng dẫn: [HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md). App tự báo khi có bản mới.
- **Lịch sử thay đổi**: [CHANGELOG.md](CHANGELOG.md).

## Tính năng

- Trích phụ đề cứng bằng OCR (tự dò vị trí phụ đề) hoặc từ giọng nói (faster-whisper)
- Dịch theo kịch bản (prompt, thuật ngữ, bộ lọc từ), giữ nguyên câu đã sửa tay khi chạy lại
- Tách nhạc nền bằng AI, lồng tiếng có chỉnh tốc độ / cao độ, tự căn khớp không đọc chồng
- Xuất video: làm mờ sub gốc, logo, watermark, khung 9:16 / 1:1 / 16:9, xem thử 10 giây
- Cửa sổ sửa phụ đề, 9 công cụ lẻ, tìm giọng giống mẫu, tự viết tiêu đề / mô tả / hashtag
- Tự cập nhật qua GitHub Releases, API key mã hóa (Windows DPAPI), nhật ký + báo lỗi

## Chạy từ mã nguồn

Yêu cầu: Windows 10/11, Python 3.11, FFmpeg trong PATH (`winget install Gyan.FFmpeg`).

```
run.bat
```

Lần đầu `run.bat` tự tạo `.venv`, cài PyTorch (bản CUDA nếu có card NVIDIA, ngược lại bản CPU) và thư viện
trong `requirements.txt`, rồi mở app.

## Test

```
run_tests.bat        # test nhanh (vài giây)
run_tests.bat all    # thêm test trên video thật (khoảng 1 phút, cần FFmpeg)
```

Test nhanh cũng tự chạy trên GitHub Actions mỗi lần push.

## Đóng gói và phát hành

```
build.bat            # PyInstaller + FFmpeg + Inno Setup → build/installer/DubStudio-Setup-x.y.z.exe
publish.bat          # đăng bản mới lên GitHub Releases (app của người dùng tự nhận cập nhật)
```

Số phiên bản nằm duy nhất ở `core/version.py`. Chia sẻ app & quy trình ra bản mới: [HUONG_DAN_CAP_NHAT.md](HUONG_DAN_CAP_NHAT.md).
Build trên máy có GPU NVIDIA để bộ cài chạy được GPU.

## Cấu trúc

```
main.py               điểm vào (DubStudio.exe / DubStudio-worker.exe --py)
app/                  giao diện PySide6: main_window, pages/ (các tab), dialogs/, widgets/
core/                 xử lý: ocr, asr, translate, separate, tts, sync, render, pipeline, toolops,
                      updater, secret (DPAPI), log + crash, runtime (chạy được cả khi đóng gói)
packaging/            PyInstaller spec, Inno Setup, icon, publish.py
tests/                pytest
```

Dữ liệu người dùng: `data/` khi chạy từ mã nguồn, `%LOCALAPPDATA%\DubStudio` khi cài bằng bộ cài.
