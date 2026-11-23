# Brief viết Chương 2 (LaTeX) — Scenario 1: Sai tham số Boot Sector (NTFS)

> **Mục đích tệp này**: Dùng làm ngữ cảnh/prompt ngắn gọn đưa cho AI (ví dụ trên Prism/Overleaf) để sinh toàn bộ khung và bản nháp LaTeX cho **Chương 2**, đảm bảo khớp 100% với mã nguồn `src/bai_lam.py`, log chạy thật trên `case1.img`, văn phong Chương 1 & Chương 3 của `report.pdf`, và rubric chấm điểm.

---

## 1. Yêu cầu hình thức & ràng buộc chung

- **Ngôn ngữ & văn phong**: Tiếng Việt học thuật, ngắn gọn, súc tích, đồng bộ phong cách với Chương 3 (`Scenario 2: Sai directory entry (NTFS)`).
- **Độ dài mục tiêu**: **3–3.5 trang** (cả báo cáo có giới hạn tối đa 20 trang).
- **Không lặp lại Chương 1**: Các hàm/cấu trúc dùng chung (`runlist`, `parse_key`, `index_entries`, `fixup`/`ap_dung_fixup`, `attrs`, `_doc_mft0`, `doc_record`, `doc_data_attr`, `doc_thu_muc`, `_duyet`) đã trình bày ở Chương 1 $\rightarrow$ chỉ dẫn chiếu lại Chương 1, tập trung vào phần riêng của Scenario 1.
- **Tỷ trọng điểm lý thuyết cần phủ đủ**:
  - Chẩn đoán hư hỏng: **40%**
  - Cơ sở lý thuyết: **40%**
  - Thuật toán & Hạn chế: **20%**
  - Bằng chứng hex & log phải **khớp nhau tuyệt đối** (không được tự bịa số liệu hay offset).
- **Chừa placeholder hình ảnh rõ ràng** (ví dụ `\includegraphics` có comment mô tả) cho ảnh chụp hexdump và ảnh chụp log.

---

## 2. Dữ liệu thật từ ảnh nhóm (`case1.img`) & Log đối chiếu

- **Thông số ảnh**: Volume NTFS 512 MB (`536,870,912` byte), `bps = 512` (tại `0x0B`), `total_sectors = 1048575` (tại `0x28`, hex `FF FF 0F 00 00 00 00 00`).
- **Vị trí Backup Boot Sector**: `total_sectors × bps = 1048575 × 512 = 536,870,400 = 0x1FFFFE00`; có OEM ID `NTFS    ` tại `0x1FFFFE03`.

### Ba trường bị sửa sai (giống nhau ở cả Sector 0 và Backup Boot `0x1FFFFE00`)

| Trường | Offset Sector 0 | Offset Backup | Kích thước | Giá trị bị sai | Giá trị đúng |
| --- | --- | --- | --- | --- | --- |
| `Sectors per cluster` | `0x0D` | `0x1FFFFE0D` | 1 byte | `0x01` (`1`) | `0x08` (`8`) |
| `$MFT Starting Cluster (LCN)` | `0x30` | `0x1FFFFE30` | 8 byte LE | `2` (`02 00 ... 00`) | `4` (`04 00 ... 00`) |
| `Clusters per MFT record` | `0x40` | `0x1FFFFE40` | 1 byte có dấu | `0x02` (`+2`) | `0xF6` (`-10`) |

- **Hệ quả nếu dùng Boot Sector sai**: `cluster_size = 512 × 1 = 512` B; offset `$MFT = 2 × 512 = 0x400` (không có chữ ký `FILE`); trường `0x40 = +2` bị hiểu là `2 cluster` thay vì $2^{10} = 1024$ B.

### Bằng chứng hex tại Bản ghi 0 của `$MFT` (`0x00004000`)

- `0x4000` (4 B): `46 49 4C 45` (`FILE`) — chữ ký MFT record.
- `0x401C` (4 B): `00 04 00 00` = `1024` B — **Allocated Size** của MFT record $\Rightarrow$ `rec_size = 1024`.
- `0x4098`: Attribute `$FILE_NAME` (`0x30`), độ dài tên `0x04` (tại `0x40F0`), tên UTF-16LE `24 00 4D 00 46 00 54 00` = `"$MFT"` (tại `0x40F2`–`0x40F9`).
- `0x4100`: Attribute `$DATA` không tên (`0x80`, non-resident), runlist tại `0x4140` là `11 13 04 00` $\Rightarrow$ 1 run gồm `0x13 = 19` cluster bắt đầu tại `LCN = 0x04 = 4`.
- **Suy luận số học**:
  - `cluster_size = 0x4000 / 4 = 16384 / 4 = 4096` B (lũy thừa của 2 trong `[512, 65536]`).
  - `spc = 4096 / 512 = 8` (`0x08`).
  - `byte 0x40 = ma_hoa_0x40(1024, 4096) = -10` (`0xF6`).

### Bằng chứng loại trừ `$MFTMirr` trên chính `case1.img`

- **Record 1 (`$MFTMirr`) tại `0x00004400`**: có `$FILE_NAME` = `"$MFTMirr"` $\ne$ `"$MFT"` $\Rightarrow$ bị loại khi so khớp chính xác tên trong `$FILE_NAME` (khắc phục lỗi nếu chỉ tìm chuỗi con UTF-16 `$\x00M\x00F\x00T\x00`).
- **Bản sao Record 0 trong vùng `$MFTMirr` tại `0x0FFFF000`**: có `$FILE_NAME` = `"$MFT"` và runlist vẫn chứa `mft_lcn = 4`; tuy `0x0FFFF000` chia hết cho `4`, nhưng thương số `0x0FFFF000 / 4 = 0x3FFFC00 = 67,107,840` B **không phải lũy thừa của 2** và **vượt quá 64 KiB** $\Rightarrow$ bị loại bởi ràng buộc `cluster`.

### Tập tin trích xuất được (5/5 đúng nội dung & đường dẫn theo `selftest.py`)

`DATA/F11.TXT` (143 B, offset `0x15000`), `DATA/H59.PDF` (307,151 B, `0x14c00`), `DATA/M13.PNG` (244,179 B, `0x14800`), `DATA/M81.JPG` (412,499 B, `0x15400`), `DATA/S16.JPG` (121,691 B, `0x14400`).

---

## 3. Khung mục lục cần sinh cho Chương 2

```text
\chapter{Scenario 1: Sai tham số Boot Sector (NTFS)}
  (Đoạn dẫn nhập 2–3 câu)

  \section{Chẩn đoán hư hỏng}
    \subsection{Mô tả}
      - Bảng Bị sai / Còn nguyên / Hệ quả (tương tự Chương 3 mục 1.1)
      - Bảng 3 trường bị sửa ở Sector 0 và Backup Boot (0x0D, 0x30, 0x40)
    \subsection{Bằng chứng hex}
      - 3 khối hexdump / placeholder hình: Sector 0 (0x00), Backup Boot (0x1FFFFE00), MFT Record 0 (0x4000)
      - Giải thích ngắn gọn từng offset nổi bật

  \section{Cơ sở lý thuyết}
    \subsection{Suy luận 3 tham số từ bản ghi \$MFT số 0}
      - Xác định mft_offset, đọc rec_size từ Allocated Size (+0x1C), lấy mft_lcn từ runlist $DATA, tính cluster_size = mft_offset / mft_lcn và spc = cluster_size / bps
    \subsection{Loại trừ bản sao \$MFTMirr và nhận diện nhầm}
      - So khớp đúng $FILE_NAME == "$MFT" (loại Record 1 ở 0x4400)
      - Kiểm tra chia hết & cluster là lũy thừa của 2 trong [bps, 64 KiB] (loại bản sao mirror ở 0xFFFF000)
    \subsection{Mã hóa trường kích thước MFT record (byte 0x40)}
      - Công thức ma_hoa_0x40(rec_size, cluster): dương (rec_size // cluster) nếu rec_size >= cluster; âm (-log2(rec_size)) bù 2 nếu rec_size < cluster

  \section{Thuật toán phục hồi và sửa ảnh}
    \subsection{Chẩn đoán và trích xuất (chuan\_doan\_case1, case1)}
      - Quét toàn ảnh bằng img.tim(b"FILE", o, None, bps) (không giới hạn 128 MB)
      - Dùng hàm ap_dung_fixup duy nhất; lọc $FILE_NAME, $DATA runlist, kiểm tra cluster
      - Nạp NTFS(img, log, override_boot=boot_params) — không sửa ảnh gốc
      - Dùng chung _duyet từ Record 5 (dẫn chiếu Chương 1) và doc_data_attr để trích xuất & lưu bằng out.luu
    \subsection{Sửa Boot Sector trên bản sao (--repair)}
      - Tạo bản sao bằng img.sao_chep; tính backup_offset = total_sectors * bps
      - Kiểm tra OEM ID "NTFS    " ở sector cuối trước khi ghi; log các giá trị sai trước khi sửa
      - Ghi 0x0D, 0x30, 0x40 ở cả Sector 0 và Backup Boot
      - Mở lại ảnh mới bằng NTFS(img_moi, log) KHÔNG override_boot và duyệt lại cây thư mục để xác minh
    \subsection{Pseudocode}
      - Khối mã giả ngắn gọn (~25 dòng) cho chuan_doan_case1, case1 và repair
    \subsection{Kết quả log và kiểm chứng}
      - Placeholder hình/khối trích log JSON chạy case1 + --repair trên case1.img
      - Nêu kết quả selftest.py: 5/5 đúng nội dung, 5/5 đúng đường dẫn; xác minh ảnh sửa đọc bình thường bằng --info

  \section{Hạn chế}
    - Chưa hỗ trợ $ATTRIBUTE_LIST (0x20): chương trình phát hiện và ghi cảnh báo log.canh_bao thay vì theo tiếp bản ghi MFT phụ (giới hạn đã biết)
    - Phụ thuộc bps (0x0B) và total_sectors (0x28) còn nguyên vẹn (nếu bps bất thường chỉ fallback 512 kèm cảnh báo)
    - Không suy được mft_lcn nếu Record 0 của $MFT bị xóa/hỏng Fixup hoặc hỏng runlist $DATA
```

---

## 4. Tên hàm chính xác trong `src/bai_lam.py` (không đổi tên khi viết báo cáo)

- `ap_dung_fixup(buf, bps=512, log=None)` — hàm Fixup (USA) duy nhất dùng chung cho cả `NTFS` và `chuan_doan_case1`.
- `ma_hoa_0x40(rec_size, cluster)` — mã hóa byte `0x40`.
- `chuan_doan_case1(img, log)` — suy luận `bps`, `spc`, `cluster`, `mft_lcn`, `rec_size`, `rec_size_byte`, `tong_sector`.
- `NTFS(img, log, override_boot=None)` — cho phép truyền tham số suy luận mà không ghi vào ảnh gốc; `attrs` ghi cảnh báo khi gặp `ATTR_ATTRIBUTE_LIST = 0x20`.
- `BaiLam._duyet(fs, n, prefix, files, seen, depth)` — hàm duyệt đệ quy dùng chung cho `info`, `case1` và bước xác minh của `repair`.
- `BaiLam.case1(img, out)` và `BaiLam.repair(img, case, anh_moi)`.

---

## 5. Mẫu prompt gợi ý khi dán vào Prism / AI viết LaTeX

> Dựa trên toàn bộ thông số và khung mục lục trong tệp `BRIEF_CHUONG2_CASE1.md` này, hãy viết hoàn chỉnh **Chương 2** bằng LaTeX (cỡ 3–3.5 trang, dùng `\chapter`, `\section`, `\subsection`, `tabular`, `verbatim` cho pseudocode và log, chừa chỗ `\includegraphics` có chú thích cho các ảnh hexdump). Giữ đúng mọi offset, giá trị hex và tên hàm như trong brief, không bịa thêm số liệu và không lặp lại phần lý thuyết cơ bản đã có ở Chương 1.
