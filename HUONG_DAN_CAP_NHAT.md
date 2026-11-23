# Hướng dẫn phát hành bản cập nhật

## Thiết lập một lần

1. Tạo repo trên GitHub (vd `DubStudio`), để **Public** — repo Private thì người dùng không tải được bản cập nhật.
   Chỉ cần đăng bộ cài lên mục Releases, không bắt buộc đưa mã nguồn lên.
2. Mở `core/version.py`, sửa: `UPDATE_SOURCE = "github:TEN_TAI_KHOAN/DubStudio"`
3. Cài GitHub CLI và đăng nhập (mở cmd):
   ```
   winget install GitHub.cli
   gh auth login
   ```
   (chọn GitHub.com → HTTPS → Login with a web browser)
4. Build và phát hành bản đầu tiên như các bước dưới. Bộ cài từ bản này trở đi mới có tính năng tự cập nhật.

## Mỗi lần ra bản mới

1. Sửa code, chạy thử bằng `run.bat`.
2. Tăng số trong `core/version.py`: `VERSION = "0.3.0"`
3. Thêm lên **đầu** `CHANGELOG.md`:
   ```
   ## 0.3.0

   - Điều mới 1
   - Sửa lỗi 2
   ```
4. Chạy `build.bat` (10–15 phút) → ra `build/installer/DubStudio-Setup-0.3.0.exe`
5. Chạy `publish.bat` → tự tạo release `v0.3.0` trên GitHub và upload bộ cài.
6. Lưu vào Git: `git add -A` rồi `git commit -m "Bản 0.3.0"`

## Phía người dùng

- Mở app → vài giây sau tự kiểm tra; có bản mới thì hiện cửa sổ kèm danh sách thay đổi:
  **Cập nhật ngay** (tự tải, kiểm tra SHA-256, cài đè, mở lại app) · **Để sau** · **Bỏ qua bản này**.
- Lần đầu mở sau khi cập nhật → hiện "Có gì mới".
- Tự kiểm tra bất cứ lúc nào: tab **Hệ thống → Cập nhật phần mềm → Kiểm tra cập nhật**.
- Dữ liệu (cấu hình, API key, danh sách video, model AI) nằm ở `%LOCALAPPDATA%\DubStudio` → giữ nguyên khi cập nhật.

## Không dùng GitHub?

Đặt `UPDATE_SOURCE = "https://…/latest.json"` (link tải trực tiếp). `publish.bat` sẽ tạo `build/installer/latest.json`;
bạn upload bộ cài lên chỗ bất kỳ, dán link tải trực tiếp vào trường `url` trong latest.json rồi upload latest.json.
