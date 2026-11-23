================================================================================
KHUNG CHUONG TRINH - DO AN PHUC HOI DU LIEU NTFS
Ma nhom / Seed: qwertyqwertyqwerty
================================================================================

Chuong trinh duoc xay dung tren skeleton cua giang vien, ho tro doc anh dia,
phan tich cau truc NTFS, phuc hoi du lieu va ghi nhat ky. Toan bo thuat toan
phan tich he thong tap tin va khoi phuc duoc trien khai trong src/bai_lam.py.

Yeu cau: Python 3.9 tro len, chi su dung thu vien chuan (Python Standard Library).
Khong dung thu vien phan tich he thong tap tin ben ngoai hoac goi cong cu he thong.


1. CAU TRUC THU MUC DU AN
--------------------------------------------------------------------------------
Midterm/
├── Report/                                 # Thu muc Bao cao & Phan cong
│   ├── Report.pdf                          # Bao cao ky thuat chinh (toi da 20 trang)
│   ├── Work_Assignment.md                  # Bang phan cong cong viec 4 thanh vien
│   └── case1/                              # Tai lieu & LaTeX nguon cua Scenario 1
│       ├── case1.tex
│       ├── case1_functions.md
│       ├── BRIEF_CHUONG2_CASE1.md
│       └── HUONG_DAN_SCENARIO_1.md
│
├── src/                                    # Thu muc Source Code
│   ├── bai_lam.py                          # Class BaiLam: info, case1, case2, case3, case_ext, repair, corrupt
│   ├── nhom.json                           # Thong tin nhom va dang ky phan cong diem
│   ├── mo_rong.json                        # Dac ta JSON cho Bonus C (ext-mbr)
│   ├── README.txt                          # Huong dan su dung & phan cong thanh vien
│   ├── recover.py                          # Giao dien dong lenh CLI (khong sua)
│   ├── binio.py                            # Doc byte, tim kiem va sao chep anh dia (khong sua)
│   ├── tienich.py                          # Nhat ky, luu du lieu va SHA256SUMS (khong sua)
│   └── selftest.py                         # Tu kiem thu bang bo anh mau (khong sua)
│
├── Test Data/                              # Thu muc Ket qua, Nhat ky & Link anh dia
│   ├── README.txt                          # Link Shared Drive chua file .img & lenh tai lap
│   ├── logs/                               # Nhat ky thuc thi (--log)
│   │   ├── info_clean.json
│   │   ├── info_clean.jsonl
│   │   ├── case1_run.jsonl
│   │   ├── case2_run.jsonl
│   │   ├── case3_run.jsonl
│   │   ├── bonus_recovery.jsonl
│   │   └── damaged.img.changes.json
│   └── recovered/                          # Tap tin khoi phuc & SHA256SUMS cua 4 tinh huong
│       ├── case1/    (DATA/... + SHA256SUMS)
│       ├── case2/    (DATA/... + SHA256SUMS)
│       ├── case3/    (DATA/... + SHA256SUMS)
│       └── case_ext/ (DATA/... + SHA256SUMS)
│
└── anh/                                    # Thu muc chua cac file anh dia (.img) tren may / Shared Drive
    ├── clean.img                           # Anh NTFS nguyen ven (kiem thu --info)
    ├── case1.img                           # Anh Scenario 1 (sai tham so Boot Sector)
    ├── case1_repaired.img                  # Anh Scenario 1 sau khi sua bang --repair
    ├── case2.img                           # Anh Scenario 2 (mat lien ket thu muc DATA -> Orphan MFT)
    ├── case3.img                           # Anh Scenario 3 (JPEG lon bi phan manh 2 doan)
    ├── damaged.img                         # Anh Bonus C (xoa 16B MBR Partition Entry 0 tai 0x1BE)
    ├── damaged.img.changes.json            # Vung byte bi thay doi khi chay --corrupt
    └── mo_rong.json                        # Ban sao dac ta Bonus C


2. DANH SACH LENH CHAY CHUONG TRINH (Chay tu thu muc goc cua du an)
--------------------------------------------------------------------------------

[2.1] Doc thong tin NTFS tren anh sach (--info):
python src/recover.py --image anh/clean.img --info --json --log "Test Data/logs/info_clean.jsonl" > "Test Data/logs/info_clean.json"

[2.2] Scenario 1: Khoi phuc tap tin & sua Boot Sector tren ban sao (--case 1 --repair):
python src/recover.py --image anh/case1.img --case 1 --out "Test Data/recovered/case1" --repair anh/case1_repaired.img --log "Test Data/logs/case1_run.jsonl"

Kiem chung lai anh da sua cua Case 1 bang --info:
python src/recover.py --image anh/case1_repaired.img --info --json

[2.3] Scenario 2: Khoi phuc tap tin bi mat lien ket thu muc (--case 2):
python src/recover.py --image anh/case2.img --case 2 --out "Test Data/recovered/case2" --log "Test Data/logs/case2_run.jsonl"

[2.4] Scenario 3: Khoi phuc tap tin JPEG bi phan manh (--case 3):
python src/recover.py --image anh/case3.img --case 3 --out "Test Data/recovered/case3" --log "Test Data/logs/case3_run.jsonl"

[2.5] Bonus C (ext-mbr): Gay loi xoa MBR Partition Entry 0 (0x1BE) va khoi phuc:
- Gay loi (--corrupt):
python src/recover.py --image anh/clean-whole-disk.img --corrupt src/mo_rong.json --out anh/damaged.img --log "Test Data/logs/bonus_corrupt.jsonl"

- Khoi phuc (--case ext):
python src/recover.py --image anh/damaged.img --case ext --out "Test Data/recovered/case_ext" --log "Test Data/logs/bonus_recovery.jsonl"

[2.6] Chay tu kiem thu tong the (selftest.py):
python src/selftest.py --mau anh


3. CAU HINH DIEM CONG (src/nhom.json & src/mo_rong.json)
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


4. PHAN CONG THANH VIEN
--------------------------------------------------------------------------------
- NGUYEN DANG MINH DUY  (23127042) : Case 1 va repair()
- NGUYEN ANH KIET       (23127005) : info() va Case 2
- NGUYEN LE THIEN LY    ([MSSV])   : Case 3
- NGUYEN TAN PHUOC      (23127536) : Bonus C: corrupt(), case_ext()
