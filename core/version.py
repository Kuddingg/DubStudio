# Số phiên bản DUY NHẤT của app. Muốn phát hành bản mới: tăng số này, ghi thay đổi vào CHANGELOG.md,
# chạy build.bat rồi publish.bat (app, tab Hỗ trợ và tên file bộ cài đều tự lấy từ đây).
VERSION = "0.3.0"

# Nơi app kiểm tra bản mới. Một trong hai kiểu:
#   "github:TEN_TAI_KHOAN/TEN_REPO"           → GitHub Releases (repo phải để Public để người dùng tải được)
#   "https://.../latest.json"                  → file manifest tự đặt ở bất kỳ đâu (publish.bat tạo sẵn file này)
# Để trống = tắt tính năng tự cập nhật.
UPDATE_SOURCE = "github:Kuddingg/DubStudio"
