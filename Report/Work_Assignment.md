# BẢNG PHÂN CÔNG CÔNG VIỆC (WORK ASSIGNMENT)

**Môn học:** An toàn và Phục hồi dữ liệu (Data Safety and Recovery)  
**Đồ án giữa kỳ:** Phục hồi dữ liệu trên hệ thống tập tin NTFS  
**Mã nhóm / Seed:** `qwertyqwertyqwerty`  

---

## 1. Bảng phân công nhiệm vụ các thành viên

| STT | Họ và tên | MSSV | Phần phụ trách chính | Chi tiết công việc (Code & Báo cáo) | Tỷ lệ đóng góp |
| :-: | :--- | :---: | :--- | :--- | :---: |
| 1 | **NGUYỄN ĐẶNG MINH DUY** | `23127042` | **Scenario 1** & **`--repair`** | - Cài đặt hàm `ap_dung_fixup()`, `ma_hoa_0x40()`, `chuan_doan_case1()`, `BaiLam.case1()`, `BaiLam.repair()` trong `src/bai_lam.py`.<br>- Viết chương Báo cáo cho Scenario 1 (Chẩn đoán Boot Sector, suy luận từ Bản ghi 0 `$MFT`, bằng chứng Hexdump, Pseudocode, Hạn chế). | 25% |
| 2 | **NGUYỄN ANH KIỆT** | `23127005` | **`--info`** & **Scenario 2** | - Cài đặt bộ khung phân tích NTFS cơ sở (`NTFS`, `runlist`, `parse_key`, `index_entries`, `BaiLam.info()`, `BaiLam._duyet()`) và `BaiLam.case2()`, `khop_magic()`.<br>- Viết Chương 1 (Cấu trúc NTFS được sử dụng) và Chương Scenario 2 (Ghép nối Orphan MFT Records). | 25% |
| 3 | **NGUYỄN LÊ THIÊN LÝ** | *(Điền MSSV)* | **Scenario 3** | - Cài đặt hàm kiểm tra cấu trúc marker JPEG `jpeg_hop_le()` và thuật toán tìm mảnh phân mảnh thứ 2 trong cửa sổ 64 cluster `BaiLam.case3()`.<br>- Viết chương Báo cáo cho Scenario 3 (Khôi phục tập tin JPEG bị phân mảnh & đứt chuỗi vị trí). | 25% |
| 4 | **NGUYỄN TẤN PHƯỚC** | `23127536` | **Bonus C (`ext-mbr`)** | - Cài đặt lớp `AnhVolume`, hàm `tim_volume_ntfs()`, `BaiLam.corrupt()` và `BaiLam.case_ext()`, thiết kế đặc tả `src/mo_rong.json`.<br>- Viết phần Báo cáo cho Bonus C (Xóa và khôi phục MBR Partition Entry 0 tại `0x1BE`). | 25% |

---

## 2. Danh mục tệp trong thư mục `Report/`

- [`Report.pdf`](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/Report/Report.pdf): Báo cáo kỹ thuật chính của nhóm (tối đa 20 trang theo quy định).
- [`Work_Assignment.md`](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/Report/Work_Assignment.md): Bảng phân công công việc của các thành viên trong nhóm.
- [`case1/`](file:///e:/DISK_D/MDUY/Nam4/4.2%20Data%20Safety/Project/Midterm/Report/case1): Mã nguồn LaTeX (`case1.tex`) và tài liệu giải thích chi tiết các hàm của Scenario 1 (`case1_functions.md`, `BRIEF_CHUONG2_CASE1.md`, `HUONG_DAN_SCENARIO_1.md`).
