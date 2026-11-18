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

Chuyển vào thư mục `src`:

```bash
cd src
```

Đọc thông tin NTFS:

```bash
python recover.py --image clean.img --info --json
```

Khôi phục các tình huống chính:

```bash
python recover.py --image case1.img --case 1 --out recovered/
python recover.py --image case2.img --case 2 --out recovered/
python recover.py --image case3.img --case 3 --out recovered/
```

Ghi nhật ký bằng tham số `--log` khi cần.

Kết quả được lưu bằng `out.luu()` với đúng tên và đường dẫn gốc. Chương trình không sửa trực tiếp ảnh đầu vào.

## 3. Kiểm thử

Sử dụng bộ dữ liệu mẫu NTFS của giảng viên:

```bash
python selftest.py --mau /duong_dan_den/mau/ntfs
```

Chương trình kiểm tra thông tin hệ thống tập tin, nội dung và đường dẫn khôi phục của từng tình huống dựa trên đáp án mẫu.

Các thuật toán không cố định offset, số cluster hay thông tin riêng của ảnh mẫu.

## 4. Bonus C — Lost MBR Partition Table Entry

Nhóm lựa chọn tình huống mở rộng `ext-mbr` trên hệ thống NTFS.

**Mô tả:** Mục phân vùng đầu tiên trong bảng MBR bị xóa tại offset `0x1BE` (16 byte). Chương trình phải tìm lại NTFS volume và khôi phục dữ liệu.

### 4.1. Cấu hình

Trong `nhom.json`:

```json
"cong_diem": {
  "repair": [],
  "mo_rong": {
    "tinh_huong": "ext-mbr",
    "dac_ta": "mo_rong.json"
  }
}
```

File `mo_rong.json`:

```json
{
  "tinh_huong": "ext-mbr",
  "partition_index": 0
}
```

### 4.2. Gây lỗi

Sử dụng **whole-disk image có MBR**, không phải NTFS volume image:

```bash
python recover.py \
  --image clean-whole-disk.img \
  --corrupt mo_rong.json \
  --out damaged.img \
  --log bonus_corrupt.jsonl
```

Hàm `corrupt()` tạo ảnh sao chép và xóa 16 byte của MBR Partition Entry 0, đồng thời trả về vùng đã thay đổi để chương trình tạo file `damaged.img.changes.json`.

### 4.3. Khôi phục

```bash
python recover.py \
  --image damaged.img \
  --case ext \
  --out recovered/ \
  --log bonus_recovery.jsonl
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
| NGUYỄN ĐẶNG MINH DUY | 23127536 | Case 1 |
| NGUYỄN ANH KIỆT | 23127005 | `info()` và Case 2 |
| NGUYỄN LÊ THIÊN LÝ | [MSSV] | Case 3 |
| NGUYỄN TẤN PHƯỚC  | 23127042 | Bonus C: `corrupt()`, `case_ext()` |
