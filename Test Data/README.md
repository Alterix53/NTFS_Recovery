# TEST DATA & KẾT QUẢ THỰC THI (NTFS RECOVERY)

> [!IMPORTANT]
> Theo yêu cầu nộp bài của môn học, các tệp ảnh đĩa thực tế (`*.img`, dung lượng 68 MB – 512 MB mỗi tệp) **không được đính kèm trực tiếp** trong gói nộp để tránh vượt quá giới hạn dung lượng nộp bài. Toàn bộ ảnh đĩa gốc và ảnh đĩa sau khi sửa/gây lỗi được lưu trữ trên thư mục dùng chung của nhóm ở đường dẫn bên dưới.

---

## 1. Đường dẫn Thư mục Dữ liệu Dùng chung (Shared Data Folder Link)

- **Link Google Drive / OneDrive của nhóm (giữ hoạt động đến khi công bố điểm cuối kỳ):**  
  👉 **`[ĐIỀN_LINK_GOOGLE_DRIVE_HOẶC_ONEDRIVE_CỦA_NHÓM_TẠI_ĐÂY]`**

### Danh sách các tệp ảnh đĩa (`.img`) trên Shared Drive:
1. `clean.img` — Ảnh đĩa NTFS nguyên vẹn dùng để kiểm thử `--info`.
2. `case1.img` — Ảnh đĩa NTFS của nhóm cho **Scenario 1** (Sai tham số Boot Sector ở cả Sector 0 và Backup Boot Sector).
3. `case1_repaired.img` — Ảnh đĩa kết quả sau khi chạy `--case 1 --repair case1_repaired.img`.
4. `case2.img` — Ảnh đĩa NTFS của nhóm cho **Scenario 2** (Mất liên kết thư mục `DATA` $\rightarrow$ Orphan MFT Records).
5. `case3.img` — Ảnh đĩa NTFS của nhóm cho **Scenario 3** (Tập tin JPEG lớn bị phân mảnh làm 2 đoạn và xóa runlist/bitmap đoạn 2).
6. `damaged.img` & `damaged.img.changes.json` — Ảnh đĩa whole-disk tự gây lỗi xóa 16 byte MBR Partition Entry 0 tại `0x1BE` cho **Bonus C (`ext-mbr`)**.

---

## 2. Cấu trúc Kết quả & Nhật ký đính kèm trong `Test Data/`

Thư mục `Test Data/` này chứa toàn bộ sản phẩm đầu ra (Deliverable 3) được sinh tự động bởi chương trình `src/recover.py` trên bộ ảnh đĩa của nhóm:

```text
Test Data/
├── README.md                         # Tệp thông tin & đường dẫn Shared Drive này
├── logs/                             # Nhật ký thực thi (--log) định dạng JSON/JSONL
│   ├── info_clean.json               # Kết quả chạy --info --json trên clean.img
│   ├── info_clean.jsonl              # Nhật ký đọc Boot Sector & $MFT trên clean.img
│   ├── case1_run.jsonl               # Nhật ký chẩn đoán, trích xuất & --repair cho Scenario 1
│   ├── case2_run.jsonl               # Nhật ký phân loại entry & chấm điểm ghép cặp cho Scenario 2
│   ├── case3_run.jsonl               # Nhật ký quét cửa sổ 64 cluster & ghép JPEG cho Scenario 3
│   ├── bonus_recovery.jsonl          # Nhật ký tìm NTFS volume & khôi phục dữ liệu cho Bonus C
│   └── damaged.img.changes.json      # Đặc tả vùng byte bị xóa (0x1BE, 16 byte) của Bonus C
│
└── recovered/                        # Tập tin khôi phục được & mã băm SHA256SUMS của từng tình huống
    ├── case1/
    │   ├── DATA/ (F11.TXT, H59.PDF, M13.PNG, M81.JPG, S16.JPG)
    │   └── SHA256SUMS
    ├── case2/
    │   ├── DATA/ (C38.PNG, C68.TXT, O16.PDF, R69.JPG, X22.JPG)
    │   └── SHA256SUMS
    ├── case3/
    │   ├── DATA/ (B79.JPG, D34.TXT, H30.JPG, R54.PNG, W77.PDF)
    │   └── SHA256SUMS
    └── case_ext/
        ├── DATA/ (document.pdf, image.png, note.txt, photo1.jpg, photo2.jpg)
        └── SHA256SUMS
```

---

## 3. Lệnh Tái lập Kết quả (Reproducibility Commands)

Từ thư mục gốc của dự án, chạy các lệnh sau (thay đường dẫn file `.img` bằng thư mục tải về từ Shared Drive):

```powershell
# 1. Đọc thông tin hệ thống tập tin trên ảnh sạch
python src/recover.py --image clean.img --info --json --log "Test Data/logs/info_clean.jsonl" > "Test Data/logs/info_clean.json"

# 2. Scenario 1: Khôi phục tập tin & sửa Boot Sector trên bản sao
python src/recover.py --image case1.img --case 1 --out "Test Data/recovered/case1" --repair case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

# 3. Scenario 2: Khôi phục tập tin từ các Orphan MFT Records
python src/recover.py --image case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

# 4. Scenario 3: Khôi phục tập tin JPEG bị phân mảnh
python src/recover.py --image case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"

# 5. Bonus C: Gây lỗi xóa MBR Partition Entry 0 (0x1BE) và khôi phục
python src/recover.py --image clean-whole-disk.img --corrupt src/mo_rong.json --out bonus/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"
python src/recover.py --image bonus/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"
```
