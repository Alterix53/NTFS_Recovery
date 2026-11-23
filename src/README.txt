================================================================================
KHUNG CHƯƠNG TRÌNH — ĐỒ ÁN PHỤC HỒI DỮ LIỆU NTFS
Mã nhóm / Seed: qwertyqwertyqwerty
================================================================================

Chương trình được xây dựng trên skeleton của giảng viên, hỗ trợ đọc ảnh đĩa,
phân tích cấu trúc NTFS, phục hồi dữ liệu và ghi nhật ký. Toàn bộ thuật toán
phân tích hệ thống tập tin và khôi phục được triển khai trong src/bai_lam.py.

Yêu cầu: Python 3.9 trở lên, chỉ sử dụng thư viện chuẩn (Python Standard Library).
Không dùng thư viện phân tích hệ thống tập tin bên ngoài hoặc gọi công cụ hệ thống.


1. CẤU TRÚC THƯ MỤC DỰ ÁN
--------------------------------------------------------------------------------
Midterm/
├── Report/                                 # Thư mục Báo cáo & Phân công
│   ├── Report.pdf                          # Báo cáo kỹ thuật chính (tối đa 20 trang)
│   ├── Work_Assignment.md                  # Bảng phân công công việc 4 thành viên
│   └── case1/                              # Tài liệu & LaTeX nguồn của Scenario 1
│       ├── case1.tex
│       ├── case1_functions.md
│       ├── BRIEF_CHUONG2_CASE1.md
│       └── HUONG_DAN_SCENARIO_1.md
│
├── src/                                    # Thư mục Source Code
│   ├── bai_lam.py                          # Class BaiLam: info, case1, case2, case3, case_ext, repair, corrupt
│   ├── nhom.json                           # Thông tin nhóm và đăng ký phần cộng điểm
│   ├── mo_rong.json                        # Đặc tả JSON cho Bonus C (ext-mbr)
│   ├── README.txt                          # Hướng dẫn sử dụng & phân công thành viên
│   ├── recover.py                          # Giao diện dòng lệnh CLI (không sửa)
│   ├── binio.py                            # Đọc byte, tìm kiếm và sao chép ảnh đĩa (không sửa)
│   ├── tienich.py                          # Nhật ký, lưu dữ liệu và SHA256SUMS (không sửa)
│   └── selftest.py                         # Tự kiểm thử bằng bộ ảnh mẫu (không sửa)
│
├── Test Data/                              # Thư mục Kết quả, Nhật ký & Link ảnh đĩa
│   ├── README.txt                          # Link Shared Drive chứa file .img & lệnh tái lập
│   ├── logs/                               # Nhật ký thực thi (--log)
│   │   ├── case1_run.jsonl
│   │   ├── case2_run.jsonl
│   │   ├── case3_run.jsonl
│   │   ├── bonus_recovery.jsonl
│   │   └── damaged.img.changes.json
│   └── recovered/                          # Tập tin khôi phục & SHA256SUMS của 4 tình huống
│       ├── case1/    (DATA/... + SHA256SUMS)
│       ├── case2/    (DATA/... + SHA256SUMS)
│       ├── case3/    (DATA/... + SHA256SUMS)
│       └── case_ext/ (DATA/... + SHA256SUMS)
│
└── anh/                                    # Thư mục chứa các file ảnh đĩa (.img) trên máy / Shared Drive
    ├── clean.img                           # Ảnh NTFS nguyên vẹn (kiểm thử --info)
    ├── case1.img                           # Ảnh Scenario 1 (sai tham số Boot Sector)
    ├── case1_repaired.img                  # Ảnh Scenario 1 sau khi sửa bằng --repair
    ├── case2.img                           # Ảnh Scenario 2 (mất liên kết thư mục DATA -> Orphan MFT)
    ├── case3.img                           # Ảnh Scenario 3 (JPEG lớn bị phân mảnh 2 đoạn)
    ├── damaged.img                         # Ảnh Bonus C (xóa 16B MBR Partition Entry 0 tại 0x1BE)
    ├── damaged.img.changes.json            # Vùng byte bị thay đổi khi chạy --corrupt
    └── mo_rong.json                        # Bản sao đặc tả Bonus C


2. DANH SÁCH LỆNH CHẠY CHƯƠNG TRÌNH (Chạy từ thư mục gốc của dự án)
--------------------------------------------------------------------------------

[2.1] Đọc thông tin NTFS trên ảnh nguyên vẹn (--info):
python src/recover.py --image anh/clean.img --info --json

[2.2] Scenario 1: Khôi phục tập tin & sửa Boot Sector trên bản sao (--case 1 --repair):
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

Kiểm chứng lại ảnh đã sửa của Case 1 bằng --info:
python src/recover.py --image anh/case1_repaired.img --info --json

[2.3] Scenario 2: Khôi phục tập tin bị mất liên kết thư mục (--case 2):
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

[2.4] Scenario 3: Khôi phục tập tin JPEG bị phân mảnh (--case 3):
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"

[2.5] Bonus C (ext-mbr): Gây lỗi xóa MBR Partition Entry 0 (0x1BE) và khôi phục:
- Gây lỗi (--corrupt):
python src/recover.py --image anh/clean-whole-disk.img --corrupt src/mo_rong.json --out anh/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"

- Khôi phục (--case ext):
python src/recover.py --image anh/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"

[2.6] Chạy tự kiểm thử tổng thể (selftest.py):
python src/selftest.py --mau anh


3. CẤU HÌNH ĐIỂM CỘNG (src/nhom.json & src/mo_rong.json)
--------------------------------------------------------------------------------
Trong src/nhom.json:
  "cong_diem": {
    "repair": [1],
    "mo_rong": {
      "tinh_huong": "ext-mbr",
      "dac_ta": "mo_rong.json"
    }
  }

Trong src/mo_rong.json:
  {
    "tinh_huong": "ext-mbr",
    "partition_index": 0
  }


4. PHÂN CÔNG THÀNH VIÊN
--------------------------------------------------------------------------------
- NGUYỄN ĐẶNG MINH DUY  (23127042) : Case 1 và repair()
- NGUYỄN ANH KIỆT       (23127005) : info() và Case 2
- NGUYỄN LÊ THIÊN LÝ    ([MSSV])   : Case 3
- NGUYỄN TẤN PHƯỚC      (23127536) : Bonus C: corrupt(), case_ext()
