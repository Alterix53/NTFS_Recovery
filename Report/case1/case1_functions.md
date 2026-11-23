# Giải thích chi tiết hoạt động của các hàm liên quan đến Case 1 (Scenario 1)

Tài liệu này mô tả chi tiết luồng hoạt động, công thức tính toán và vai trò của toàn bộ các hàm trong [`src/bai_lam.py`](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py) tham gia vào việc chẩn đoán, trích xuất dữ liệu và sửa chữa ảnh đĩa NTFS bị hỏng Boot Sector (**Case 1**).

---

## 1. Tổng quan luồng gọi hàm trong Case 1

Khi chạy chương trình cho Case 1, hệ thống chia làm 3 giai đoạn chính:

```
[1. Chẩn đoán]                 [2. Trích xuất không sửa ảnh gốc]         [3. Sửa ảnh trên bản sao (--repair)]
chuan_doan_case1(img, log)     BaiLam.case1(img, out)                    BaiLam.repair(img, "1", anh_moi)
 ├── ap_dung_fixup()            ├── chuan_doan_case1()                    ├── chuan_doan_case1()
 ├── NTFS.attrs()               ├── NTFS(..., override_boot=boot_params)  ├── img.sao_chep(anh_moi)
 │    └── runlist()             │    └── _doc_mft0()                      ├── ghi đè 0x0D, 0x30, 0x40 (Sector 0 & Backup)
 ├── parse_key()                ├── BaiLam._duyet()                       └── Mở lại bằng NTFS(img_moi, log) chuẩn
 ├── NTFS.flags()               │    ├── fs.doc_record()                       để tự kiểm chứng
 └── ma_hoa_0x40()              │    └── fs.doc_thu_muc()
                                └── fs. thong_tin_record() & doc_data_attr()
```

---

## 2. Các hàm cốt lõi của Case 1

### 2.1. Hàm `chuan_doan_case1(img, log)` ([dòng 426–543](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L426-L543))
**Mục đích:** Tự động phát hiện các thông số Boot Sector đang bị sai và suy luận lại bộ tham số đúng (`bps`, `spc`, `cluster`, `mft_lcn`, `rec_size`, `rec_size_byte`, `tong_sector`) chỉ dựa vào cấu trúc thực tế của **Bản ghi 0 (`$MFT`)** trên đĩa.

**Các bước hoạt động chi tiết:**

1. **Đọc các trường còn nguyên vẹn từ Sector 0:**
   - Đọc `bps` (Bytes Per Sector) tại offset `0x0B` (2 byte). Nếu giá trị không phải lũy thừa của 2 trong đoạn `[512, 4096]`, hàm ghi cảnh báo và fallback về `512`.
   - Đọc `tong_sector` (Total Sectors) tại offset `0x28` (8 byte).

2. **Ghi nhận (log) các giá trị đang bị sửa sai để làm bằng chứng:**
   - Tại **Sector 0 (Primary Boot)**: đọc và log các giá trị sai tại `0x0D` (`spc = 1`), `0x30` (`mft_lcn = 2`), `0x40` (`rec_size_code = 2`).
   - Tính vị trí **Backup Boot Sector**: `backup_offset = tong_sector * bps` (với `case1.img` là `1,048,575 * 512 = 0x1FFFFE00`). Nếu nằm trong giới hạn ảnh, hàm đọc và log 3 trường tương ứng tại `backup_offset + 0x0D`, `+ 0x30`, `+ 0x40`.

3. **Quét tìm Bản ghi số 0 của `$MFT` theo bước nhảy sector (`bps`):**
   - Dùng `img.tim(b"FILE", o, None, bps)` để nhảy theo từng sector (`512 B`) tìm chữ ký `"FILE"` (4 byte đầu của MFT Record).
   - Tại mỗi ứng viên ở offset `o`, thực hiện chuỗi **6 màng lọc nghiêm ngặt**:
     1. **Kiểm tra `alloc_sz` (`+0x1C`, 4 byte):** Kích thước cấp phát của MFT record phải là lũy thừa của 2 nằm trong `[bps, 65536]` (trên `case1.img` là `1024` byte).
     2. **Kiểm tra và khôi phục Fixup (`ap_dung_fixup`):** Đọc `alloc_sz` byte tại `o` và kiểm tra Update Sequence Array (USA). Nếu 2 byte cuối mỗi sector không khớp USN, loại ngay (giúp loại bỏ các chuỗi `"FILE"` ngẫu nhiên trong vùng dữ liệu).
     3. **Duyệt Attribute (`NTFS.attrs`) tìm tên `"$MFT"` và Runlist:**
        - Tìm thuộc tính `$FILE_NAME` (`0x30`, resident), giải mã bằng `parse_key()`. Tên tập tin phải khớp **chính xác** `"$MFT"` (loại bỏ Record 1 có tên `"$MFTMirr"` tại `0x4400`).
        - Tìm thuộc tính `$DATA` (`0x80`, không tên, non-resident) và trích xuất danh sách `cand_runs` (runlist).
     4. **Suy luận `cluster_size` và loại trừ bản sao trong `$MFTMirr`:**
        - Lấy cluster bắt đầu của `$MFT`: `cand_lcn = cand_runs[0][0]` (trên `case1.img`, run đầu là `(4, 19)` nên `cand_lcn = 4`).
        - Vì Bản ghi 0 nằm ngay đầu `$MFT`, vị trí byte `o` phải chia hết cho `cand_lcn`. Suy ra:
          $$\text{cand\_cluster} = \frac{o}{\text{cand\_lcn}}$$
          *(Tại `o = 0x4000 = 16384` và `cand_lcn = 4` $\Rightarrow$ `cand_cluster = 4096` byte).*
        - Kiểm tra `cand_cluster` phải là lũy thừa của 2 trong `[bps, 65536]`. Điều kiện này loại bỏ hoàn toàn bản sao của Record 0 nằm trong `$MFTMirr` ở giữa đĩa (`0x0FFFF000 / 4 = 67,107,840`, không phải lũy thừa của 2 và `> 65536`).
     5. **Xác thực chéo Bản ghi số 5 (`$Root`):**
        - Từ `cand_runs` và `cand_cluster`, tính offset của MFT Record 5 (`byte5 = 5 * alloc_sz`).
        - Đọc Record 5, kiểm tra chữ ký `"FILE"`, áp dụng Fixup và kiểm tra cờ thư mục (`NTFS.flags(rec5) & 2 != 0`). Vì `$MFTMirr` chỉ sao lưu 4 bản ghi đầu (`0..3`), bước này đảm bảo chắc chắn 100% ứng viên đang xét là `$MFT` gốc.
     6. **Tính toán các thông số còn lại:**
        - `spc = cluster // bps` (`4096 // 512 = 8`).
        - Mã hóa kích thước bản ghi MFT cho byte `0x40` bằng hàm `ma_hoa_0x40(rec_size, cluster)`.

---

### 2.2. Hàm `ma_hoa_0x40(rec_size, cluster)` ([dòng 125–129](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L125-L129))
**Mục đích:** Chuyển đổi kích thước bản ghi MFT (`rec_size` tính bằng byte) sang định dạng 1 byte có dấu lưu tại offset `0x40` của Boot Sector theo chuẩn NTFS:
- Nếu `rec_size >= cluster`: trả về số cluster trên mỗi record (`rec_size // cluster`, số nguyên dương).
- Nếu `rec_size < cluster`: trả về $-\log_2(\text{rec\_size})$ bằng công thức `-(rec_size.bit_length() - 1)`.
  - Với `rec_size = 1024 < 4096`: trả về `-10` (khi ghi ra 1 byte không dấu `& 0xFF` sẽ thành `0xF6`).

---

### 2.3. Hàm `BaiLam.case1(self, img, out)` ([dòng 683–700](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L683-L700))
**Mục đích:** Khôi phục và trích xuất toàn bộ tập tin người dùng từ ảnh đĩa bị lỗi Boot Sector **mà không sửa đổi ảnh đĩa gốc**.

**Các bước hoạt động:**
1. Gọi `boot_params = chuan_doan_case1(img, L)` để lấy bộ thông số đúng đã suy luận.
2. Khởi tạo đối tượng `fs = NTFS(img, L, override_boot=boot_params)`:
   - Khi có `override_boot`, lớp `NTFS` bỏ qua `_doc_boot()` (không đọc các byte sai ở Sector 0) mà nhận trực tiếp các thông số đúng từ `boot_params`, sau đó gọi `_doc_mft0()` để nạp runlist của toàn bộ bảng `$MFT`.
3. Gọi `self._duyet(fs, REC_ROOT, "", files, set(), 0)` bắt đầu từ Record 5 (`$Root`) để duyệt đệ quy toàn bộ cây thư mục và thu thập danh sách các tập tin hợp lệ vào `files`.
4. Duyệt qua từng tập tin `f` trong `files`:
   - Đọc MFT Record của tập tin bằng `fs.doc_record(f["ref"])`.
   - Lấy thuộc tính `$DATA` không tên thông qua `fs.thong_tin_record(rec)`.
   - Trích xuất dữ liệu thực bằng `fs.doc_data_attr(d)` (hỗ trợ cả file nhỏ dạng *Resident* như `F11.TXT` và file lớn dạng *Non-resident* như `JPG`, `PNG`, `PDF`).
   - Lưu tập tin ra thư mục đích qua `out.luu(f["path"], data)` và ghi log.

---

### 2.4. Hàm `BaiLam.repair(self, img, case, anh_moi)` ([dòng 867–915](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L867-L915))
**Mục đích:** Tạo một bản sao của ảnh đĩa (`anh_moi`), vá lại 3 tham số bị hỏng ở cả **Primary Boot Sector (Sector 0)** và **Backup Boot Sector (Sector cuối)**, sau đó tự kiểm chứng lại bản sao.

**Các bước hoạt động:**
1. Gọi `params = chuan_doan_case1(img, L)` để lấy các thông số đúng và tính `backup_offset = tong_sector * bps`.
2. Tạo bản sao ảnh đĩa bằng `ban_sua = img.sao_chep(anh_moi)` (đảm bảo ảnh gốc tuyệt đối không bị ghi đè).
3. **Kiểm tra an toàn trước khi ghi:**
   - Kiểm tra `backup_offset + bps <= ban_sua.kich_thuoc`.
   - Đọc 8 byte tại `backup_offset + 3` để xác nhận chữ ký OEM ID là `b"NTFS    "`.
4. **Ghi log giá trị trước khi sửa và ghi đè giá trị đúng:**
   - Tại **Sector 0**:
     - Ghi `params["spc"]` (1 byte: `0x08`) vào `0x0D`.
     - Ghi `params["mft_lcn"]` (8 byte little-endian: `4`) vào `0x30`.
     - Ghi `params["rec_size_byte"] & 0xFF` (1 byte bù hai: `0xF6` tức `-10`) vào `0x40`.
   - Tại **Backup Boot Sector (`backup_offset`)**:
     - Ghi đồng bộ 3 giá trị trên vào `backup_offset + 0x0D`, `backup_offset + 0x30` và `backup_offset + 0x40`.
5. Đóng file bản sao (`ban_sua.dong()`).
6. **Tự kiểm chứng (Self-verification):**
   - Mở lại `anh_moi` vừa sửa bằng `NTFS(img_moi, L)` **không truyền `override_boot`** (ép chương trình phải tự đọc Boot Sector vừa sửa bằng `_doc_boot()`).
   - Duyệt lại cây thư mục từ `REC_ROOT` (Record 5) bằng `self._duyet(...)` để xác nhận đọc được đầy đủ 5/5 tập tin.

---

## 3. Các hàm bổ trợ cấu trúc NTFS được Case 1 sử dụng

Để các hàm chính ở mục 2 hoạt động, chúng gọi tới các hàm xử lý cấu trúc cấp thấp của NTFS trong [`src/bai_lam.py`](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py):

| Tên hàm / Phương thức | Vị trí | Vai trò trong Case 1 |
| :--- | :--- | :--- |
| `ap_dung_fixup(buf, bps, log)` | [Dòng 16–38](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L16-L38) | Kiểm tra mảng Update Sequence Array (USA). Đối chiếu 2 byte cuối mỗi sector (`512 B`) với Update Sequence Number (USN) và hoàn nguyên 2 byte dữ liệu gốc. Dùng khi quét tìm Record 0, đọc các MFT Record và đọc khối thư mục `INDX`. |
| `runlist(data)` | [Dòng 41–54](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L41-L54) | Giải mã chuỗi byte runlist của các thuộc tính Non-resident thành danh sách các cặp `(lcn, so_cluster)`. Trong Case 1, hàm này giúp đọc runlist `11 13 04 00` của Record 0 để tìm ra `mft_lcn = 4` (dài 19 cluster) và đọc dữ liệu của các file ảnh/PDF. |
| `parse_key(k)` | [Dòng 57–70](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L57-L70) | Giải mã cấu trúc chuẩn của `$FILE_NAME` (`0x30` và directory index entry): trích xuất MFT record cha (`parent`), kích thước thực (`real`), cờ thư mục (`flags`), namespace (`ns`) và chuỗi tên tập tin UTF-16LE (`name`). |
| `index_entries(buf, start)` | [Dòng 73–86](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L73-L86) | Duyệt tuần tự các mục chỉ mục (index entries) bên trong `$INDEX_ROOT` hoặc khối `INDX` cho tới khi gặp cờ kết thúc (`flags & 2`), trả về `(mft_ref, key_dict, pos)`. |
| `NTFS.attrs(rec, log)` | [Dòng 174–193](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L174-L193) | Bộ sinh (generator) nhảy từ offset `+0x14` của MFT Record qua từng attribute cho tới dấu kết thúc `0xFFFFFFFF`. Tự động tách nội dung trực tiếp nếu là *Resident* (`nonres == 0`) hoặc giải mã `runlist` nếu là *Non-resident* (`nonres == 1`). |
| `NTFS._doc_mft0()` | [Dòng 196–203](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L196-L203) | Đọc Bản ghi 0 tại `mft_lcn * cluster`, lấy runlist của chính bảng `$MFT` lưu vào `self.mft_runs` để ánh xạ mọi số thứ tự MFT Record `n` sang offset byte vật lý trên đĩa. |
| `NTFS.offset_record(n)` & `doc_record(n)` | [Dòng 205–221](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L205-L221) | Tính offset vật lý của bản ghi MFT thứ `n` dựa trên `self.mft_runs`, đọc `rec_size` byte, kiểm tra chữ ký `"FILE"` và áp dụng Fixup. |
| `NTFS.doc_thu_muc(rec)` | [Dòng 255–277](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L255-L277) | Đọc toàn bộ danh sách tập tin/thư mục con trong một MFT Record thư mục bằng cách kết hợp cả thuộc tính `$INDEX_ROOT` (`0x90`) và các khối `INDX` thuộc `$INDEX_ALLOCATION` (`0xA0`). |
| `NTFS.doc_data_attr(a)` | [Dòng 231–240](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L231-L240) | Trả về nội dung byte của thuộc tính `$DATA`: trả trực tiếp `a["content"]` nếu là Resident, hoặc ghép dữ liệu từ các cluster theo `a["runs"]` rồi cắt đúng theo kích thước thực `a["real"]` nếu là Non-resident. |
| `BaiLam._duyet(...)` | [Dòng 562–580](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py#L562-L580) | Duyệt cây thư mục đệ quy từ `$Root` (Record 5), tự động bỏ qua tên ngắn DOS 8.3 (`ns == 2`), các tập tin hệ thống bắt đầu bằng `"$"` ở thư mục gốc và mục `"."`, thu thập đường dẫn kèm số MFT Record của từng tập tin. |
