# Đồ án Giữa kỳ — Phục hồi Dữ liệu NTFS

**Mã nhóm / Seed:** `qwertyqwertyqwerty`

Chương trình được xây dựng trên skeleton của giảng viên, hỗ trợ đọc ảnh đĩa, phân tích cấu trúc NTFS, phục hồi dữ liệu và ghi nhật ký. Toàn bộ thuật toán phân tích hệ thống tập tin và khôi phục được triển khai trong `src/bai_lam.py`.

**Yêu cầu môi trường:** Python 3.9 trở lên, chỉ sử dụng thư viện chuẩn (*Python Standard Library*). Không dùng thư viện phân tích hệ thống tập tin bên ngoài và không gọi công cụ hệ thống.

---

## 1. Cấu trúc Thư mục Dự án

```text
Midterm/
├── Report/                                 # Thư mục Báo cáo & Phân công
│   ├── Report.pdf                          # Báo cáo kỹ thuật chính (tối đa 20 trang)
│   └── Work_Assignment.txt                 # Bảng phân công công việc 4 thành viên
│
├── src/                                    # Thư mục Source Code
│   ├── bai_lam.py                          # Class BaiLam: info, case1, case2, case3, case_ext, repair, corrupt
│   ├── nhom.json                           # Thông tin nhóm và đăng ký phần cộng điểm
│   ├── mo_rong.json                        # Đặc tả JSON cho Bonus C (ext-mbr)
│   ├── README.md                           # Hướng dẫn sử dụng & phân công thành viên
│   ├── recover.py                          # Giao diện dòng lệnh CLI (không sửa)
│   ├── binio.py                            # Đọc byte, tìm kiếm và sao chép ảnh đĩa (không sửa)
│   ├── tienich.py                          # Nhật ký, lưu dữ liệu và SHA256SUMS (không sửa)
│   └── selftest.py                         # Tự kiểm thử bằng bộ ảnh mẫu (không sửa)
│
├── Test Data/                              # Thư mục Dữ liệu Kiểm thử & Kết quả
│   ├── Link Test Data.txt                  # Link Shared Drive chứa ảnh đĩa (.img) & kết quả
│   ├── logs/                               # Nhật ký thực thi (--log)
│   │   ├── case1_run.jsonl
│   │   ├── case2_run.jsonl
│   │   ├── case3_run.jsonl
│   │   ├── bonus_recovery.jsonl
│   │   └── damaged.img.changes.json
│   └── recovered/                          # Tập tin khôi phục & SHA256SUMS của 3 case + Bonus
│       ├── case1/    (DATA/... + SHA256SUMS)
│       ├── case2/    (DATA/... + SHA256SUMS)
│       ├── case3/    (DATA/... + SHA256SUMS)
│       └── case_ext/ (DATA/... + SHA256SUMS)
│
└── anh/                                    # Thư mục chứa bộ ảnh đĩa (.img) tải từ Shared Drive
    ├── case1.img                           # Ảnh Scenario 1 (sai tham số Boot Sector)
    ├── case1_repaired.img                  # Ảnh Scenario 1 sau khi sửa bằng --repair
    ├── case2.img                           # Ảnh Scenario 2 (mất liên kết thư mục DATA -> Orphan MFT)
    ├── case3.img                           # Ảnh Scenario 3 (JPEG lớn bị phân mảnh 2 đoạn)
    ├── damaged.img                         # Ảnh Bonus C (xóa 16B MBR Partition Entry 0 tại 0x1BE)
    ├── damaged.img.changes.json            # Vùng byte bị thay đổi khi chạy --corrupt
    └── mo_rong.json                        # Bản sao đặc tả Bonus C
```

---

## 2. Danh sách Lệnh Chạy Chương trình (3 Case + Bonus)

Chạy từ thư mục gốc của dự án (với các ảnh đĩa đặt trong thư mục `anh/`):

### 2.1. Scenario 1 — Sai tham số Boot Sector (`--case 1` kèm `--repair`)

Khôi phục tập tin không sửa ảnh gốc, đồng thời tạo bản sao `anh/case1_repaired.img` đã sửa Boot Sector (cả Sector 0 và Backup Boot Sector):

```powershell
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"
```

Kiểm chứng lại ảnh sau khi sửa bằng `--info`:

```powershell
python src/recover.py --image anh/case1_repaired.img --info --json
```

### 2.2. Scenario 2 — Sai mục thư mục / Orphan MFT Records (`--case 2`)

```powershell
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"
```

### 2.3. Scenario 3 — Đứt chuỗi vị trí / Fragmented JPEG (`--case 3`)

```powershell
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"
```

### 2.4. Bonus C (`ext-mbr`) — Mất MBR Partition Table Entry 0 (`--corrupt` & `--case ext`)

- **Gây lỗi trên ảnh whole-disk sạch (`--corrupt`):** Xóa 16 byte tại `0x1BE` và tạo tệp `anh/damaged.img.changes.json`:

```powershell
python src/recover.py --image anh/clean-whole-disk.img --corrupt src/mo_rong.json --out anh/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"
```

- **Khôi phục dữ liệu từ ảnh mất MBR (`--case ext`):**

```powershell
python src/recover.py --image anh/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"
```

---

## 3. Cấu hình Điểm cộng (`src/nhom.json` & `src/mo_rong.json`)

Trong `src/nhom.json`:

```json
"cong_diem": {
  "repair": [1],
  "mo_rong": {
    "tinh_huong": "ext-mbr",
    "dac_ta": "mo_rong.json"
  }
}
```

Trong `src/mo_rong.json`:

```json
{
  "tinh_huong": "ext-mbr",
  "partition_index": 0
}
```

---

## 4. Phân công Thành viên

| Thành viên | MSSV | Phụ trách |
| :--- | :---: | :--- |
| NGUYỄN ĐẶNG MINH DUY | 23127042 | Case 1 và `repair()` |
| NGUYỄN ANH KIỆT | 23127005 | `info()` và Case 2 |
| NGUYỄN LÊ THIÊN LÝ | 23127223 | Case 3 |
| NGUYỄN TẤN PHƯỚC | 23127536 | Bonus C: `corrupt()`, `case_ext()` |
