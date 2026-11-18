# HƯỚNG DẪN TRIỂN KHAI TÌNH HUỐNG 1 (SCENARIO 1)
## ĐỒ ÁN AN TOÀN VÀ PHỤC HỒI DỮ LIỆU — DATA RECOVERY ON NTFS

---

## MỤC LỤC
1. [Tổng quan bài toán Tình huống 1](#1-tổng-quan-bài-toán-tình-huống-1)
2. [Chẩn đoán (Diagnosis)](#2-chẩn-đoán-diagnosis)
3. [Cơ sở lý thuyết & Bằng chứng Offset (Theoretical Basis & Offsets)](#3-cơ-sở-lý-thuyết--bằng-chứng-offset)
4. [Thuật toán & Mã giả (Algorithm & Pseudocode)](#4-thuật-toán--mã-giả-algorithm--pseudocode)
5. [Hướng dẫn cài đặt trong `bai_lam.py`](#5-hướng-dẫn-cài-đặt-trong-bai_lampy)
6. [Khai báo và triển khai phần cộng điểm `--repair` (Tùy chọn)](#6-khai-báo-và-triển-khai-phần-cộng-điểm---repair)
7. [Các lỗi thường gặp và lưu ý chấm điểm](#7-các-lỗi-thường-gặp-và-lưu-ý-chấm-điểm)

---

## 1. TỔNG QUAN BÀI TOÁN TÌNH HUỐNG 1

### 1.1. Mô tả đề bài (Trích xuất từ `Project.pdf`)
* **Tên tình huống**: *Scenario 1 — Wrong boot sector parameters* (Sai tham số boot sector).
* **Đặc điểm hỏng hóc**:
  * Ba trường tham số trọng yếu trong Boot Sector (Sector 0) bị ghi đè bằng các giá trị **sai nhưng hợp lệ về mặt hình thức** (formally valid).
  * Bản sao Boot Sector dự phòng (**Backup Boot Sector tại sector cuối cùng của volume**) cũng bị làm sai y hệt.
  * **Toàn bộ cấu trúc khác trên đĩa đều còn NGUYÊN VẸN 100%** (chuỗi bản ghi `$MFT`, các cluster dữ liệu, bảng chỉ mục thư mục `$INDEX_ROOT`,...).
* **Yêu cầu bắt buộc**:
  1. Trình bày lập luận dựa trên bằng chứng offset (hex evidence) để chứng minh giá trị đúng của 3 trường.
  2. Chương trình (`case1(img, out)`) phải **tự động suy luận (derive) các giá trị này từ ảnh đĩa**, tuyệt đối **không hardcode** bất kỳ giá trị cụ thể nào của ảnh nhóm/ảnh mẫu.
  3. Trích xuất thành công toàn bộ tập tin trong thư mục dữ liệu (`DATA/`) ra thư mục kết quả.

### 1.2. Ba trường bị làm sai đối với NTFS

| STT | Tên trường trong Boot Sector | Offset (Hex) | Kích thước | Mô tả & Tác động khi bị sai |
| :-: | :--- | :-: | :-: | :--- |
| **1** | **Sectors per cluster** | `0x0D` | 1 byte | Số sector trong một cluster. Nếu sai $\rightarrow$ tính sai kích thước cluster (`cluster_size`), dẫn đến đọc lệch hoàn toàn địa chỉ các cluster dữ liệu. |
| **2** | **$MFT Starting Cluster (LCN)** | `0x30` | 8 bytes | Số thứ tự cluster bắt đầu của bảng `$MFT`. Nếu sai $\rightarrow$ không định vị được bản ghi `$MFT 0`, hệ điều hành không thể nạp bảng quản lý tập tin. |
| **3** | **Clusters per MFT record** | `0x40` | 1 byte | Quy định kích thước của một bản ghi FILE trong `$MFT`. Nếu sai $\rightarrow$ nhảy sai bước giữa các bản ghi MFT kế tiếp. |

---

## 2. CHẨN ĐOÁN (DIAGNOSIS)

Khi phân tích báo cáo kỹ thuật và lập trình chẩn đoán:

1. **Dấu hiệu nhận diện Boot Sector bị hỏng**:
   * Khi mở ảnh volume bằng WinHex hoặc đọc Sector 0:
     - Giá trị tại `0x0D` (Sectors per cluster) có thể bị sửa thành `0x01`, `0x40`, hoặc giá trị bất hợp lý so với cấu trúc cluster thực tế.
     - Giá trị tại `0x30` ($MFT LCN) trỏ đến một cluster rác hoặc vùng không chứa chuỗi ký tự chữ ký `FILE`.
     - Giá trị tại `0x40` bị sửa thành giá trị không khớp với kích thước bản ghi 1024 byte thông thường (ví dụ không phải `0xF6`).
   * Kiểm tra sector cuối cùng của volume (Backup Boot Sector): Cũng chứa 3 giá trị sai tương tự, do đó **không thể dùng cơ chế phục hồi thụ động từ bản sao dự phòng**.

2. **Dấu vết kiến trúc còn nguyên vẹn để cứu vãn**:
   * Trường `Bytes per sector` tại offset `0x0B` (thường là 512 byte = `0x0200`) **không bị phá hoại**.
   * Chữ ký Boot Sector `0x55AA` tại offset `0x1FE` vẫn hợp lệ.
   * Toàn bộ chuỗi bản ghi `$MFT` thực sự vẫn nằm nguyên vẹn tại một vị trí nào đó trên đĩa. Bản ghi MFT đầu tiên (Record 0) luôn bắt đầu bằng chuỗi ký tự nhận diện `b"FILE"` (`46 49 4C 45`).
   * Bản ghi 0 của `$MFT` có thuộc tính `$DATA` không tên, chứa **Runlist** mô tả chính xác dải cluster của chính `$MFT`. Runlist này chứa **LCN bắt đầu thực sự** của `$MFT`!

---

## 3. CƠ SỞ LÝ THUYẾT & BẰNG CHỨNG OFFSET

### 3.1. Phương pháp suy luận 3 tham số đúng

```
               [ Sector 0: Boot Sector ]
                  BytesPerSec = 512 (OK)
                  SecPerClus  = SAI
                  $MFT LCN    = SAI
                  RecSizeByte = SAI
                         │
                         ▼ (Quét tìm signature "FILE" + "$MFT")
               ┌────────────────────────┐
               │    Bản ghi MFT 0       │ ◄── Nằm tại Offset: O_MFT (ví dụ: 0x4000)
               │ (Chứa $DATA Runlist)   │
               └───────────┬────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
[ Đo khoảng cách đến Record 1 ]        [ Đọc Runlist trong $DATA ]
Khoảng cách = 1024 bytes (0x400)       Run đầu tiên: LCN_start (ví dụ: 4)
  ==> Record size = 1024                 ==> $MFT LCN đúng = LCN_start
  ==> Byte 0x40 = -10 (0xF6)                   │
                                               ▼
                              [ Tính Cluster Size & SecPerClus ]
                              ClusterSize = O_MFT / LCN_start
                                          = 16384 / 4 = 4096 bytes
                              SecPerClus  = ClusterSize / BytesPerSec
                                          = 4096 / 512 = 8 sectors
```

#### Bước 1: Tìm vị trí thực tế của Bảng `$MFT` ($O_{MFT}$)
* Duyệt đĩa từ đầu volume theo bước nhảy `Bytes per sector` (512 byte).
* Tìm vị trí xuất hiện chữ ký `b"FILE"` (`46 49 4C 45`).
* Để xác thực đây chính xác là **Bản ghi 0 của `$MFT`** (tránh nhầm lẫn với các bản ghi FILE khác), kiểm tra 2 điều kiện:
  1. Trường số hiệu bản ghi tại offset `+0x2C` (4 byte) có giá trị bằng `0` (hoặc byte `0` của MFT).
  2. Bên trong bản ghi có chứa thuộc tính `$FILE_NAME` (`0x30`) với tên tập tin là `"$MFT"` (`24 00 4D 00 46 00 54 00` dạng UTF-16LE).
* Gọi byte offset tìm được là $O_{MFT}$ (Ví dụ: trong `ntfs.img`, $O_{MFT} = 0x4000 = 16\,384$ byte).

#### Bước 2: Suy ra Kích thước bản ghi MFT (`Clusters per MFT record` - `0x40`)
* Tại vị trí $O_{MFT}$, di chuyển tới vị trí $O_{MFT} + 1024$ byte (`0x400`) và kiểm tra:
  * Nếu tại $O_{MFT} + 1024$ cũng bắt đầu bằng `b"FILE"` (chính là Bản ghi 1: `$MFTMirr`), ta khẳng định kích thước một bản ghi MFT là $1\,024$ byte.
* **Quy tắc mã hóa trường `0x40` trong Boot Sector**:
  * Nếu kích thước bản ghi $< 1$ cluster: trường này lưu số nguyên có dấu $c < 0$, với kích thước bằng $2^{|c|}$ byte.
  * Vì $1024 = 2^{10}$, giá trị lưu trữ đúng là:
    $$c = -10 \equiv \mathbf{0xF6} \text{ (dạng bù 2 một byte hex)}$$

#### Bước 3: Suy ra `$MFT Starting Cluster (LCN)` (trường `0x30`)
* Áp dụng thuật toán Fixup (USA) cho Bản ghi 0 để khôi phục 2 byte cuối mỗi sector.
* Duyệt danh sách thuộc tính của Bản ghi 0, định vị thuộc tính `$DATA` không tên (mã loại `0x80`).
* Vì `$MFT` luôn là thuộc tính non-resident, thuộc tính `$DATA` lưu một cấu trúc **Data Runs (Runlist)** tại offset do trường `+0x20` chỉ định.
* Giải mã Run đầu tiên của Runlist:
  * Byte header đầu tiên của Run: `len_len = B & 0x0F`, `off_len = (B >> 4) & 0x0F`.
  * Bỏ qua `len_len` byte độ dài, đọc `off_len` byte tiếp theo (số nguyên có dấu little-endian). Giá trị này chính là **`start_lcn`** (LCN khởi đầu của `$MFT`).
  * Ví dụ trong ảnh chuẩn: Runlist là `11 13 04 00` $\rightarrow$ `off_len = 1`, giá trị delta LCN là `0x04`.
  * $\rightarrow$ **`$MFT LCN` đúng = `4`**.

#### Bước 4: Suy ra `Sectors per cluster` (trường `0x0D`)
* Theo quan hệ hình học đĩa:
  $$O_{MFT} = \text{start\_lcn} \times \text{cluster\_size}$$
  $$\Rightarrow \text{cluster\_size} = \frac{O_{MFT}}{\text{start\_lcn}}$$
* Ví dụ:
  $$\text{cluster\_size} = \frac{16\,384}{4} = 4\,096 \text{ bytes}$$
* Từ `cluster_size`, suy ra số sector trên mỗi cluster:
  $$\text{Sectors per cluster} = \frac{\text{cluster\_size}}{\text{Bytes per sector}} = \frac{4\,096}{512} = \mathbf{8}$$
* $\rightarrow$ **Giá trị đúng tại offset `0x0D` = `0x08`**.

---

## 4. THUẬT TOÁN & MÃ GIẢ (ALGORITHM & PSEUDOCODE)

### Mã giả thuật toán `case1(img, out)` (Dùng cho Báo cáo lý thuyết):

```text
Algorithm Recover_Scenario_1(img, out):
    Input:  img - đối tượng ảnh đĩa (AnhDia), out - thư mục kết quả (ThuMucKetQua)
    Output: Trích xuất toàn bộ tập tin ra out, phục hồi tham số đúng của Boot Sector

    // Bước 1: Đọc thông số hợp lệ từ Boot Sector
    bytes_per_sec ← Read_U16_LE(img, offset=0x0B)
    
    // Bước 2: Quét tìm Bản ghi 0 của $MFT
    mft_offset ← -1
    for offset from 0 to MAX_SEARCH_RANGE step bytes_per_sec:
        if img[offset : offset + 4] == "FILE":
            record_bytes ← img[offset : offset + 1024]
            if Is_MFT_Record_0(record_bytes):
                mft_offset ← offset
                break

    if mft_offset == -1:
        Raise Error("Không tìm thấy $MFT")

    // Bước 3: Xác định MFT Record Size
    if img[mft_offset + 1024 : mft_offset + 1028] == "FILE":
        record_size ← 1024
        rec_size_byte ← -10 (0xF6)

    // Bước 4: Đọc Runlist từ Record 0 để lấy mft_lcn
    rec0 ← Apply_Fixup(img[mft_offset : mft_offset + record_size], bytes_per_sec)
    data_attr ← Find_Attribute(rec0, type=0x80, name="")
    runlist ← Parse_Runlist(data_attr.runlist_bytes)
    mft_lcn ← runlist[0].lcn

    // Bước 5: Tính cluster_size và sectors_per_cluster
    cluster_size ← mft_offset / mft_lcn
    sec_per_clus ← cluster_size / bytes_per_sec

    Log_Decision("Derived Parameters:", sec_per_clus, mft_lcn, rec_size_byte)

    // Bước 6: Khôi phục danh sách tập tin và dữ liệu
    all_files ← Traverse_And_Extract_Files(img, runlist, cluster_size, record_size)
    for each file in all_files:
        out.luu(file.path, file.content)
```

---

## 5. HƯỚNG DẪN CÀI ĐẶT TRONG `bai_lam.py`

Khi triển khai vào phương thức `case1(self, img, out)` trong [bai_lam.py](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/bai_lam.py):

### 5.1. Cấu trúc các hàm bổ trợ khuyến nghị
Bạn có thể tách thành một module riêng (ví dụ `src/ntfs.py` hoặc viết trực tiếp trong `bai_lam.py`):

1. **`apply_fixup(raw_bytes, bytes_per_sec)`**:
   * Kiểm tra mảng USA ở offset `+0x04` và `+0x06`.
   * So khớp 2 byte USN với 2 byte cuối của mỗi sector 512B (`0x1FE`, `0x3FE`,...).
   * Thay thế bằng byte gốc lưu trong USA.
2. **`parse_runlist(data)`**:
   * Đọc từng run byte theo quy tắc giải mã độ dời và độ dài:
     ```python
     len_len = b & 0x0F
     off_len = (b >> 4) & 0x0F
     length = int.from_bytes(data[p : p + len_len], "little")
     delta = int.from_bytes(data[p + len_len : p + len_len + off_len], "little", signed=True)
     ```
3. **`extract_file_data(img, attr_data, cluster_size)`**:
   * Nếu thuộc tính `$DATA` là Resident: dữ liệu nằm ngay trong bản ghi MFT.
   * Nếu Non-resident: duyệt runlist của `$DATA`, đọc từng cluster từ ảnh đĩa và cắt đúng theo `real_size` (tại offset `+0x30`).

### 5.2. Mẫu ghi Log đúng chuẩn để đạt trọn điểm Code Quality
Quy định đồ án yêu cầu ghi log mọi bước và quyết định:
```python
self.log.buoc("Bắt đầu chẩn đoán Boot Sector bị sai", offset=0x00)
self.log.quyet_dinh(f"Tìm thấy Bản ghi 0 của $MFT tại offset", offset=mft_offset)
self.log.quyet_dinh(f"Đọc runlist từ Record 0, suy ra mft_lcn = {mft_lcn}")
self.log.quyet_dinh(f"Tính toán: cluster_size = {cluster_size}B, SecPerClus = {sec_per_clus}")
self.log.buoc(f"Đã trích xuất {rel_path}", gia_tri=len(file_data))
```

---

## 6. KHAI BÁO VÀ TRIỂN KHAI PHẦN CỘNG ĐIỂM `--repair` (TÙY CHỌN)

Theo mục 7 & 9 của `Project.pdf`, nếu làm thêm phần `--repair` cho Tình huống 1, nhóm được cộng thêm **tối đa 10 điểm thực hành**.

### 6.1. Khai báo trong `nhom.json`
Chỉnh sửa [nhom.json](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/src/nhom.json):
```json
{
  "cong_diem": {
    "repair": [1],
    "mo_rong": null
  }
}
```

### 6.2. Triển khai phương thức `repair` trong `bai_lam.py`
Nguyên tắc:
1. Tạo bản sao ghi được bằng `ban_sua = img.sao_chep(anh_moi)`.
2. Ghi đè 3 giá trị đúng đã suy ra vào **cả Sector 0 (Primary Boot Sector) và Sector cuối cùng (Backup Boot Sector)**:
   - Offset `0x0D`: ghi `sec_per_clus` (1 byte).
   - Offset `0x30`: ghi `mft_lcn` (8 bytes little-endian).
   - Offset `0x40`: ghi `0xF6` (-10) (1 byte).
3. Đóng bản sao bằng `ban_sua.dong()`.

---

## 7. CÁC LỖI THƯỜNG GẶP VÀ LƯU Ý CHẤM ĐIỂM

1. ❌ **Lỗi Hardcode Offset (Trừ 0 điểm ảnh ẩn)**:
   * **Tuyệt đối không viết**: `mft_offset = 0x4000` hoặc `cluster_size = 4096`.
   * Bộ ảnh ẩn của giảng viên có thể có kích thước volume khác, `$MFT` bắt đầu ở cluster khác (ví dụ LCN 16 hoặc 32). Mọi thông số phải tính động từ việc quét `FILE 0`.
2. ❌ **Lỗi quên áp dụng Fixup**:
   * Khi đọc thuộc tính của bất kỳ bản ghi MFT nào (đặc biệt là thuộc tính `$DATA` ở cuối bản ghi quanh offset `0x1FE` hoặc `0x3FE`), nếu không áp dụng Fixup, 2 byte cuối mỗi sector vẫn là chữ ký kiểm tra (USN), dẫn đến giải mã sai runlist hoặc làm hỏng dữ liệu file resident.
3. ❌ **Lỗi đường dẫn file trích xuất (`path`)**:
   * Đề bài yêu cầu trích xuất toàn bộ file trong thư mục dữ liệu (`DATA/`). Tên và đường dẫn phải chuẩn hóa (dùng dấu `/`, không chứa thư mục rỗng, đường dẫn tính từ gốc volume). Đường dẫn đúng chiếm **10% điểm số**.
4. ❌ **Thời gian thực thi quá 10 phút**:
   * Khi quét đĩa tìm chữ ký `FILE`, không nên quét từng byte đơn lẻ (`range(0, size, 1)`), mà phải quét theo bước nhảy sector `range(0, size, bytes_per_sec)` (bước 512 byte) vì cấu trúc bản ghi MFT luôn được căn chỉnh theo sector. Quét theo sector chỉ mất chưa đến 1 giây cho volume 512 MB.
