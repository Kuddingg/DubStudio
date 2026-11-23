# Hướng dẫn sử dụng DubStudio

DubStudio dịch và lồng tiếng video (Trung → Việt và nhiều ngôn ngữ khác) bằng AI:
lấy phụ đề gốc → dịch → tách nhạc nền → đọc lồng tiếng → căn khớp thời gian → xuất video.

## 1. Cài đặt lần đầu

1. Chạy `DubStudio-Setup-x.y.z.exe`, bấm Next đến khi xong (không cần quyền quản trị).
2. Mở DubStudio, vào tab **Hệ thống**:
   - **API key Gemini**: bấm *Hiện / sửa*, dán key (lấy miễn phí ở aistudio.google.com → *Get API key*). Có thể nhập nhiều key, mỗi dòng một key; hết quota app tự đổi key.
   - Máy có card NVIDIA: bấm **Kiểm tra GPU** → **Áp dụng gợi ý** để chạy nhanh hơn.
3. Lần đầu dùng tính năng nhận giọng nói / tách nhạc, app tự tải model AI (vài trăm MB), tiến độ hiện ngay trên dòng video.

## 2. Lồng tiếng một video (tab Biên tập)

1. **Thêm video**: bấm *Thêm video* / *Thư mục*, hoặc kéo thả file vào cửa sổ.
2. **Chọn cách lấy phụ đề** (mục Dịch thuật → Trích xuất):
   - **Hình (OCR)** — video có phụ đề in sẵn trên hình. Bấm **Tự dò vùng sub** để app tự tìm vị trí chữ,
     hoặc kéo khung **OCR** trên hình xem trước cho trùm đúng dòng chữ.
   - **Giọng (ASR)** — video không có phụ đề, app nghe lời thoại.
3. **Che phụ đề gốc**: bấm *Thêm vùng → Mờ*, kéo trùm lên chữ gốc (Tự dò vùng sub cũng tự đặt vùng Mờ nếu đã có).
4. **Chọn giọng đọc** (mục Giọng đọc AI): giọng, tốc độ, cao độ; bấm ▶ để nghe thử.
5. **Chọn kiểu phụ đề / khung hình** (mục Xuất bản, Kiểu phụ đề): khung 9:16 cho TikTok, màu chữ, viền…
6. Bấm **Bắt đầu**. Theo dõi tiến độ trên từng dòng video. Xong bấm **Kết quả** để mở thư mục video.

Mẹo: kéo thanh tua tới đoạn cần xem rồi bấm **Xem thử 10s** để kiểm tra nhanh (phụ đề, giọng, làm mờ)
trước khi xuất cả video.

## 3. Sửa phụ đề

Nhấp đúp vào video (hoặc bấm **Sửa phụ đề**):

- **Dòng thời gian** (dưới video): sóng âm + các câu dạng khối. Kéo khối để dời câu, kéo mép trái / phải để chỉnh
  lúc bắt đầu / kết thúc (không chồng được lên câu bên cạnh). Bấm chỗ trống để tua. Lăn chuột: cuộn ngang;
  **Ctrl + lăn**: phóng to / thu nhỏ.
- Bấm một câu để sửa thời gian / bản dịch → **Áp dụng**. Bấm **Nghe** để nghe giọng đọc câu đó.
- **Gộp câu sau** · **Tách câu** (tại đầu phát nếu nằm trong câu, và tại con trỏ trong ô Bản dịch).
- **Hoàn tác / Làm lại**: Ctrl+Z / Ctrl+Y (mọi thao tác: sửa, kéo, gộp, tách, xóa, dịch). **Ctrl+S** để lưu;
  đóng cửa sổ khi chưa lưu app sẽ hỏi.
- Cột **Giọng**: xanh = vừa khung · vàng = app sẽ đọc nhanh hơn một chút · đỏ = quá dài, nên rút gọn câu.
- **Dịch lại** (một câu), **Dịch câu trống**, **Dịch lại tất cả** (theo kịch bản đang chọn).
- **Tìm / Thay tất cả**, **Thêm dòng / Xóa dòng**, **Lưu SRT**.
- Bấm **Bắt đầu** lại để xuất video với phụ đề đã sửa. Bật *Giữ bản dịch đã có* (mặc định) thì các câu đã sửa
  không bị dịch đè.

## 4. Kịch bản dịch

Tab **Kịch bản dịch**: mỗi kịch bản là một cách dịch (Review phim, Tiên hiệp, Hài hước…):

- **Prompt**: mô tả giọng văn, cách xưng hô cho AI.
- **Thuật ngữ**: từ phải dịch cố định (vd 师兄 → sư huynh).
- **Bộ lọc từ**: thay từ sau khi dịch, mỗi dòng `từ gốc → từ thay`.

## 5. Công cụ lẻ (tab Công cụ)

Tách giọng & nhạc nền · Trích phụ đề ra SRT · Dịch file SRT · Tạo giọng từ SRT · Ghép phụ đề cứng ·
Đổi khung hình · Nén & đổi định dạng · Tải video · **Tìm giọng giống mẫu** (đưa video có giọng bạn thích,
app tìm giọng + cao độ + tốc độ giống nhất, bấm *Áp dụng*).

## 6. Cập nhật

App tự kiểm tra bản mới khi mở. Có bản mới → bấm **Cập nhật ngay**, app tự tải, cài và mở lại.
Cấu hình, API key, danh sách video được giữ nguyên.

## 7. Khi gặp lỗi

- Dịch lỗi "hết quota": đợi vài phút, thêm API key khác, hoặc chọn AI dịch = Ollama (chạy trên máy).
- Tạo giọng lỗi / chậm: kiểm tra mạng (giọng Edge cần Internet).
- Render lỗi bộ nhớ: đóng bớt phần mềm nặng, chọn Chất lượng = Nhanh.
- App báo lỗi bất ngờ: tab **Hệ thống → Nhật ký → Mở thư mục nhật ký**, gửi file `.log` mới nhất cho nhà phát triển.

## Phím tắt

| Thao tác | Tác dụng |
|---|---|
| Delete | Xóa vùng đang chọn trên khung xem trước |
| Nhấp đúp vùng Chữ | Sửa nội dung watermark |
| Nhấp đúp video | Mở Sửa phụ đề |
| Space (Sửa phụ đề) | Phát / tạm dừng |
| Nhấp đúp một câu | Nhảy video tới câu đó |
