================================================================================
TEST DATA & KET QUA THUC THI (NTFS RECOVERY)
Ma nhom / Seed: qwertyqwertyqwerty
================================================================================

LUU Y QUAN TRONG:
Theo yeu cau nop bai cua mon hoc, cac tep anh dia thuc te (*.img, dung luong
32 MB - 512 MB moi tep) KHONG duoc dinh kem truc tiep trong goi nop de tranh
vuot qua gioi han dung luong nop bai. Toan bo anh dia goc va anh dia sau khi
sua/gay loi duoc luu tru trong thu muc anh/ tren Shared Drive cua nhom.


1. DUONG DAN THU MUC DU LIEU DUNG CHUNG (SHARED DATA FOLDER LINK)
--------------------------------------------------------------------------------
Link Google Drive / OneDrive cua nhom (giu hoat dong den khi cong bo diem cuoi ky):
-> [DIEN_LINK_GOOGLE_DRIVE_HOAC_ONEDRIVE_CUA_NHOM_TAI_DAY]

Danh sach cac tep trong thu muc anh/ tren Shared Drive:
  1. anh/clean.img                (32 MB)  - Anh NTFS nguyen ven dung cho --info
  2. anh/case1.img                (512 MB) - Anh goc Scenario 1 (sai Boot Sector)
  3. anh/case1_repaired.img       (512 MB) - Anh Scenario 1 sau khi chay --repair
  4. anh/case2.img                (512 MB) - Anh goc Scenario 2 (Orphan MFT Records)
  5. anh/case3.img                (512 MB) - Anh goc Scenario 3 (Fragmented JPEG)
  6. anh/damaged.img              (65 MB)  - Anh whole-disk tu gay loi MBR tai 0x1BE (Bonus C)
  7. anh/damaged.img.changes.json (92 B)   - Vung byte bi thay doi do --corrupt sinh ra
  8. anh/mo_rong.json             (60 B)   - Dac ta JSON cho Bonus C


2. CAU TRUC THU MUC DU AN & KET QUA TRONG TEST DATA/
--------------------------------------------------------------------------------
Midterm/
├── Report/
│   ├── Report.pdf                          # Bao cao ky thuat chinh
│   ├── Work_Assignment.md                  # Bang phan cong cong viec
│   └── case1/                              # Tai lieu & LaTeX cua Scenario 1
│
├── src/
│   ├── bai_lam.py                          # Toan bo ma nguon thuat toan NTFS
│   ├── binio.py
│   ├── recover.py
│   ├── selftest.py
│   ├── tienich.py
│   ├── nhom.json
│   ├── mo_rong.json
│   └── README.txt
│
├── Test Data/
│   ├── README.txt                          # Tep huong dan & duong dan Shared Drive nay
│   ├── logs/                               # Nhat ky thuc thi (--log) dinh dang JSON/JSONL
│   │   ├── info_clean.json                 # Ket qua chay --info --json tren anh/clean.img
│   │   ├── info_clean.jsonl                # Nhat ky doc Boot Sector & $MFT tren anh/clean.img
│   │   ├── case1_run.jsonl                 # Nhat ky chan doan, trich xuat & --repair cho Scenario 1
│   │   ├── case2_run.jsonl                 # Nhat ky phan loai entry & ghep cap cho Scenario 2
│   │   ├── case3_run.jsonl                 # Nhat ky quet 64 cluster & ghep JPEG cho Scenario 3
│   │   ├── bonus_recovery.jsonl            # Nhat ky tim NTFS volume & khoi phuc cho Bonus C
│   │   └── damaged.img.changes.json        # Dac ta vung byte bi xoa (0x1BE, 16 byte) cua Bonus C
│   │
│   └── recovered/                          # Tap tin khoi phuc duoc & SHA256SUMS cua tung tinh huong
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
└── anh/                                    # Thu muc chua cac file .img (tai ve tu Shared Drive)
    ├── clean.img
    ├── case1.img
    ├── case1_repaired.img
    ├── case2.img
    ├── case3.img
    ├── damaged.img
    ├── damaged.img.changes.json
    └── mo_rong.json


3. DANH SACH LENH CHAY TAI LAP KET QUA (Chay tu thu muc goc cua du an)
--------------------------------------------------------------------------------

# 1. Doc thong tin he thong tap tin tren anh sach (--info)
python src/recover.py --image anh/clean.img --info --json --log "Test Data/logs/info_clean.jsonl" > "Test Data/logs/info_clean.json"

# 2. Scenario 1: Khoi phuc tap tin & sua Boot Sector tren ban sao (--case 1 --repair)
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

# Kiem chung lai anh da sua cua Scenario 1 bang --info
python src/recover.py --image anh/case1_repaired.img --info --json

# 3. Scenario 2: Khoi phuc tap tin tu cac Orphan MFT Records (--case 2)
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

# 4. Scenario 3: Khoi phuc tap tin JPEG bi phan manh (--case 3)
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"

# 5. Bonus C: Gay loi xoa MBR Partition Entry 0 (0x1BE) va khoi phuc (--corrupt & --case ext)
python src/recover.py --image anh/clean-whole-disk.img --corrupt src/mo_rong.json --out anh/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"
python src/recover.py --image anh/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"

# 6. Tu kiem thu tong hop (neu thu muc anh/ co cac file dap an .json)
python src/selftest.py --mau anh
