================================================================================
TEST DATA & KẾT QUẢ THỰC THI (NTFS RECOVERY)
Mã nhóm / Seed: qwertyqwertyqwerty
================================================================================

LƯU Ý QUAN TRỌNG:
Theo yêu cầu nộp bài của môn học, các tệp ảnh đĩa thực tế (*.img, dung lượng
32 MB – 512 MB mỗi tệp) KHÔNG được đính kèm trực tiếp trong gói nộp để tránh
vượt quá giới hạn dung lượng nộp bài. Toàn bộ ảnh đĩa gốc và ảnh đĩa sau khi
sửa/gây lỗi được lưu trữ trong thư mục anh/ trên Shared Drive của nhóm.


1. ĐƯỜNG DẪN THƯ MỤC DỮ LIỆU DÙNG CHUNG (SHARED DATA FOLDER LINK)
--------------------------------------------------------------------------------
Link Google Drive / OneDrive của nhóm (giữ hoạt động đến khi công bố điểm cuối kỳ):
-> [ĐIỀN_LINK_GOOGLE_DRIVE_HOẶC_ONEDRIVE_CỦA_NHÓM_TẠI_ĐÂY]

Danh sách các tệp trong thư mục anh/ trên Shared Drive:
  1. anh/clean.img                (32 MB)  - Ảnh NTFS nguyên vẹn dùng cho --info
  2. anh/case1.img                (512 MB) - Ảnh gốc Scenario 1 (sai Boot Sector)
  3. anh/case1_repaired.img       (512 MB) - Ảnh Scenario 1 sau khi chạy --repair
  4. anh/case2.img                (512 MB) - Ảnh gốc Scenario 2 (Orphan MFT Records)
  5. anh/case3.img                (512 MB) - Ảnh gốc Scenario 3 (Fragmented JPEG)
  6. anh/damaged.img              (65 MB)  - Ảnh whole-disk tự gây lỗi MBR tại 0x1BE (Bonus C)
  7. anh/damaged.img.changes.json (92 B)   - Vùng byte bị thay đổi do --corrupt sinh ra
  8. anh/mo_rong.json             (60 B)   - Đặc tả JSON cho Bonus C


2. CẤU TRÚC THƯ MỤC DỰ ÁN & KẾT QUẢ TRONG TEST DATA/
--------------------------------------------------------------------------------
Midterm/
├── Report/
│   ├── Report.pdf                          # Báo cáo kỹ thuật chính
│   ├── Work_Assignment.md                  # Bảng phân công công việc
│   └── case1/                              # Tài liệu & LaTeX của Scenario 1
│
├── src/
│   ├── bai_lam.py                          # Toàn bộ mã nguồn thuật toán NTFS
│   ├── binio.py
│   ├── recover.py
│   ├── selftest.py
│   ├── tienich.py
│   ├── nhom.json
│   ├── mo_rong.json
│   └── README.txt
│
├── Test Data/
│   ├── README.txt                          # Tệp hướng dẫn & đường dẫn Shared Drive này
│   ├── logs/                               # Nhật ký thực thi (--log) định dạng JSON/JSONL
│   │   ├── info_clean.json                 # Kết quả chạy --info --json trên anh/clean.img
│   │   ├── info_clean.jsonl                # Nhật ký đọc Boot Sector & $MFT trên anh/clean.img
│   │   ├── case1_run.jsonl                 # Nhật ký chẩn đoán, trích xuất & --repair cho Scenario 1
│   │   ├── case2_run.jsonl                 # Nhật ký phân loại entry & ghép cặp cho Scenario 2
│   │   ├── case3_run.jsonl                 # Nhật ký quét 64 cluster & ghép JPEG cho Scenario 3
│   │   ├── bonus_recovery.jsonl            # Nhật ký tìm NTFS volume & khôi phục cho Bonus C
│   │   └── damaged.img.changes.json        # Đặc tả vùng byte bị xóa (0x1BE, 16 byte) của Bonus C
│   │
│   └── recovered/                          # Tập tin khôi phục được & SHA256SUMS của từng tình huống
│       ├── case1/
│       │   ├── DATA/ (F11.TXT, H59.PDF, M13.PNG, M81.JPG, S16.JPG)
│       │   └── SHA256SUMS
│       ├── case2/
│       │   ├── DATA/ (C38.PNG, C68.TXT, O16.PDF, R69.JPG, X22.JPG)
│       │   └── SHA256SUMS
│       ├── case3/
│       │   ├── DATA/ (B79.JPG, D34.TXT, H30.JPG, R54.PNG, W77.PDF)
│       │   └── SHA256SUMS
│       └── case_ext/
│           ├── DATA/ (document.pdf, image.png, note.txt, photo1.jpg, photo2.jpg)
│           └── SHA256SUMS
│
└── anh/                                    # Thư mục chứa các file .img (tải về từ Shared Drive)
    ├── clean.img
    ├── case1.img
    ├── case1_repaired.img
    ├── case2.img
    ├── case3.img
    ├── damaged.img
    ├── damaged.img.changes.json
    └── mo_rong.json


3. DANH SÁCH LỆNH CHẠY TÁI LẬP KẾT QUẢ (Chạy từ thư mục gốc của dự án)
--------------------------------------------------------------------------------

# 1. Đọc thông tin hệ thống tập tin trên ảnh sạch (--info)
python src/recover.py --image anh/clean.img --info --json --log "Test Data/logs/info_clean.jsonl" > "Test Data/logs/info_clean.json"

# 2. Scenario 1: Khôi phục tập tin & sửa Boot Sector trên bản sao (--case 1 --repair)
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

# Kiểm chứng lại ảnh đã sửa của Scenario 1 bằng --info
python src/recover.py --image anh/case1_repaired.img --info --json

# 3. Scenario 2: Khôi phục tập tin từ các Orphan MFT Records (--case 2)
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

# 4. Scenario 3: Khôi phục tập tin JPEG bị phân mảnh (--case 3)
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"

# 5. Bonus C: Gây lỗi xóa MBR Partition Entry 0 (0x1BE) và khôi phục (--corrupt & --case ext)
python src/recover.py --image anh/clean-whole-disk.img --corrupt src/mo_rong.json --out anh/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"
python src/recover.py --image anh/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"

# 6. Tự kiểm thử tổng hợp (nếu thư mục anh/ có các file đáp án .json)
python src/selftest.py --mau anh
