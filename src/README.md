# Khung chương trình — Đồ án phục hồi dữ liệu NTFS

Chương trình được xây dựng trên skeleton của giảng viên, hỗ trợ đọc ảnh đĩa, phân tích cấu trúc NTFS, phục hồi dữ liệu và ghi nhật ký. Toàn bộ thuật toán phân tích hệ thống tập tin và khôi phục được triển khai trong `bai_lam.py`.

## 1. Cấu trúc chương trình

| Tệp | Chức năng | Được sửa? |
|---|---|---|
| `bai_lam.py` | Class `BaiLam`: `info`, `case1`, `case2`, `case3`, `case_ext`, `repair`, `corrupt`; các hàm phân tích NTFS | Có |
| `nhom.json` | Thông tin nhóm và đăng ký phần cộng điểm | Có |
| `mo_rong.json` | Đặc tả Bonus C | Có |
| `recover.py` | Giao diện dòng lệnh (CLI) | Không |
| `binio.py` | Đọc byte, tìm kiếm và sao chép ảnh đĩa | Không |
| `tienich.py` | Nhật ký, lưu dữ liệu và checksum | Không |
| `selftest.py` | Tự kiểm thử bằng bộ ảnh mẫu | Không |

**Yêu cầu:** Python 3.9 trở lên, chỉ sử dụng thư viện chuẩn. Không dùng thư viện phân tích hệ thống tập tin hoặc gọi công cụ bên ngoài trong thuật toán.

## 2. Hướng dẫn chạy chương trình

Từ thư mục gốc của dự án (với các ảnh đĩa đặt trong thư mục `anh/`):

Đọc thông tin NTFS (`--info`):

```powershell
python src/recover.py --image anh/clean.img --info --json --log "Test Data/logs/info_clean.jsonl" > "Test Data/logs/info_clean.json"
```

Khôi phục 3 tình huống chính (`--case 1, 2, 3`) và sửa Boot Sector cho Case 1 (`--repair`):

```powershell
# Case 1 (kèm --repair tạo bản sao đã sửa Boot Sector)
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

# Kiểm chứng lại ảnh đã sửa của Case 1 bằng --info
python src/recover.py --image anh/case1_repaired.img --info --json

# Case 2
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

# Case 3
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"
```

Kết quả được lưu bằng `out.luu()` kèm tệp `SHA256SUMS` với đúng tên và đường dẫn gốc. Chương trình không sửa trực tiếp ảnh đầu vào.

## 3. Kiểm thử

Sử dụng bộ dữ liệu mẫu NTFS (nếu thư mục `anh/` chứa thêm các tệp đáp án `.json` của giảng viên):

```powershell
python src/selftest.py --mau anh
```

Chương trình kiểm tra thông tin hệ thống tập tin, nội dung và đường dẫn khôi phục của từng tình huống dựa trên đáp án mẫu.

Các thuật toán không cố định offset, số cluster hay thông tin riêng của ảnh mẫu.

## 4. Bonus C — Lost MBR Partition Table Entry

Nhóm lựa chọn tình huống mở rộng `ext-mbr` trên hệ thống NTFS (kết hợp với `--repair` cho Scenario 1).

**Mô tả:** Mục phân vùng đầu tiên trong bảng MBR bị xóa tại offset `0x1BE` (16 byte). Chương trình phải tìm lại NTFS volume và khôi phục dữ liệu.

### 4.1. Cấu hình

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

File `src/mo_rong.json`:

```json
{
  "tinh_huong": "ext-mbr",
  "partition_index": 0
}
```

### 4.2. Gây lỗi

Sử dụng **whole-disk image có MBR**, không phải NTFS volume image:

```powershell
python src/recover.py `
  --image anh/clean-whole-disk.img `
  --corrupt src/mo_rong.json `
  --out anh/damaged.img `
  --log "Test Data/logs/bonus_corrupt.jsonl"
```

Hàm `corrupt()` tạo ảnh sao chép và xóa 16 byte của MBR Partition Entry 0, đồng thời trả về vùng đã thay đổi để chương trình tạo file `anh/damaged.img.changes.json`.

### 4.3. Khôi phục

```powershell
python src/recover.py `
  --image anh/damaged.img `
  --case ext `
  --out "Test Data/recovered/case_ext" `
  --log "Test Data/logs/bonus_recovery.jsonl"
```

Hàm `case_ext()` tìm NTFS Boot Sector, xác thực MFT, xác định vị trí volume và khôi phục các tập tin trong thư mục `DATA`.

### 4.4. Kiểm tra kết quả

Kiểm tra 16 byte đã bị xóa:

```bash
xxd -s 0x1BE -l 16 damaged.img
```

Kiểm tra kết quả khôi phục:

```bash
find recovered/ -type f
```

Đối chiếu SHA-256 của các tập tin khôi phục với dữ liệu gốc để xác nhận tính toàn vẹn.

## 5. Sản phẩm nộp

- Báo cáo PDF tối đa 20 trang, gồm cấu trúc NTFS được sử dụng, chẩn đoán, cơ sở lý thuyết, mã giả và bằng chứng hex.
- Source code cùng thông tin phân công thực hiện.
- Thư mục `recovered/` có `SHA256SUMS` và nhật ký chạy trên ảnh của nhóm.
- Bonus C: `mo_rong.json` và ảnh tự gây hỏng `damaged.img`.

## 6. Phân công thành viên

| Thành viên | MSSV | Phụ trách |
|---|---|---|
| NGUYỄN ĐẶNG MINH DUY | 23127042 | Case 1 |
| NGUYỄN ANH KIỆT | 23127005 | `info()` và Case 2 |
| NGUYỄN LÊ THIÊN LÝ | [MSSV] | Case 3 |
| NGUYỄN TẤN PHƯỚC  | 23127536 | Bonus C: `corrupt()`, `case_ext()` |
