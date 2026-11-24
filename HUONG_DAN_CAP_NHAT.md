# Chia sẻ app & phát hành bản cập nhật

Repo: **https://github.com/Kuddingg/DubStudio** (Public) · Nguồn cập nhật trong app: `github:Kuddingg/DubStudio`

## 1. Đưa app cho người khác tải và dùng

Gửi họ đường link này (luôn trỏ tới bản mới nhất):

**https://github.com/Kuddingg/DubStudio/releases/latest**

Trong mục **Assets** có 2 file, người nhận chọn 1:

| File | Dùng khi |
|---|---|
| `DubStudio-Setup-x.y.z.exe` (khuyên dùng) | Cài vào máy; **tự báo và tự cài bản mới** |
| `DubStudio-Portable-x.y.z.zip` | Không muốn / không được cài: giải nén ra thư mục bất kỳ (kể cả USB), bấm `DubStudio.exe`. Dữ liệu lưu trong thư mục `data` cạnh app. Có bản mới app vẫn báo, nhưng phải tải zip mới và giải nén đè (giữ thư mục `data`) |

Cả 2 đều **không cần cài Python** hay gì khác — đã gói sẵn mọi thứ.

Với bộ cài, người nhận làm:

1. Mở link → mục **Assets** → bấm `DubStudio-Setup-x.y.z.exe` để tải.
2. Chạy file vừa tải. Windows có thể hiện **"Windows protected your PC"** (vì bộ cài chưa ký số) →
   bấm **More info** → **Run anyway**.
3. Bấm Next đến khi xong (không cần quyền quản trị), mở DubStudio từ Start Menu / Desktop.
4. Vào tab **Hệ thống** dán API key Gemini của họ (miễn phí ở aistudio.google.com), xem thêm `HUONG_DAN_SU_DUNG.md`.

Máy người dùng cần: Windows 10/11 64-bit, Internet (dịch + giọng đọc), RAM 8 GB trở lên. Có card NVIDIA thì nhanh hơn
(bấm Hệ thống → Kiểm tra GPU → Áp dụng gợi ý).

## 2. Người dùng tự biết khi có bản mới

Không cần làm gì thêm: mỗi lần mở app, app tự kiểm tra GitHub. Có bản mới hơn → hiện cửa sổ **"Có bản mới"** kèm danh
sách thay đổi (lấy từ CHANGELOG):

- **Cập nhật ngay** → app tự tải, kiểm tra mã SHA-256, tự cài đè rồi tự mở lại. Dữ liệu (API key, cấu hình, danh sách video) giữ nguyên.
- **Để sau** → lần mở app sau sẽ hỏi lại · **Bỏ qua bản này** → không hỏi lại bản đó nữa.
- Mở lần đầu sau khi cập nhật → hiện **"Có gì mới"**.
- Tự kiểm tra bất cứ lúc nào: tab **Hệ thống → Cập nhật phần mềm → Kiểm tra cập nhật**.

## 3. Bạn ra bản mới (mỗi lần cập nhật)

1. Sửa code, chạy thử bằng `run.bat`; chạy `run_tests.bat all` để chắc không hỏng gì.
2. Tăng số phiên bản trong `core/version.py`, vd `VERSION = "0.3.0"`.
3. Thêm lên **đầu** danh sách trong `CHANGELOG.md` (người dùng sẽ đọc phần này):
   ```
   ## 0.3.0

   - Thêm …
   - Sửa lỗi …
   ```
4. Lưu vào Git và đẩy code lên:
   ```
   git add -A
   git commit -m "Bản 0.3.0"
   git push
   ```
5. Chạy `build.bat` (15–20 phút) → ra `build\installer\DubStudio-Setup-0.3.0.exe` và `DubStudio-Portable-0.3.0.zip`.
6. Chạy `publish.bat` → tự tạo bản phát hành `v0.3.0` trên GitHub, upload cả 2 file, ghi chú lấy từ CHANGELOG.

File thừa được **tự dọn**: `build.bat` xóa file tạm sau khi đóng gói (chỉ giữ bộ cài + zip), `publish.bat` xóa
luôn thư mục `build` sau khi đăng xong. Muốn dọn tay: `.venv\Scripts\python.exe packaging\clean.py` (thêm `--all`
để xóa cả bộ cài). Không bao giờ đụng tới `data` (API key, cấu hình, model) và `.venv`.

Xong. Từ lúc này, ai mở app cũng nhận được thông báo cập nhật; link `releases/latest` cũng tự trỏ sang bản mới.

**Lưu ý**
- Số phiên bản phải **tăng** (0.2.0 → 0.2.1 / 0.3.0); app chỉ báo khi bản trên GitHub mới hơn bản đang dùng.
- Không xóa / đổi tên repo, không chuyển sang Private, nếu không app của người dùng sẽ không tìm được bản mới.
- Muốn bộ cài chạy GPU NVIDIA: chạy `build.bat` trên máy có card NVIDIA (sau khi chạy `run.bat` ở máy đó một lần).
- `publish.bat` cần GitHub CLI đã đăng nhập (`gh auth status`). Máy mới: `winget install GitHub.cli` rồi `gh auth login`.

## 4. Gỡ một bản phát hành lỗi

Nếu lỡ phát hành bản lỗi: sửa lỗi, tăng số phiên bản (vd 0.3.1), build và publish lại — người dùng sẽ được báo bản 0.3.1.
Có thể xóa bản lỗi ở https://github.com/Kuddingg/DubStudio/releases (bấm vào bản đó → biểu tượng thùng rác).
