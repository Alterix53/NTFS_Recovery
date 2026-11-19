"""PHẦN LÀM BÀI - NTFS: info(), case1(), case2() và repair(). Không hard-code offset/giá trị của ảnh."""
import struct
from binio import AnhDia

ATTR_SI = 0x10
ATTR_ATTRIBUTE_LIST = 0x20
ATTR_FN = 0x30
ATTR_DATA = 0x80
ATTR_INDEX_ROOT, ATTR_INDEX_ALLOC = 0x90, 0xA0
REC_ROOT = 5                      # record gốc luôn là số 5 theo quy ước NTFS
MASK48 = (1 << 48) - 1
FLAG_DIR_KEY = 0x10000000         # cờ "thư mục" trong key $FILE_NAME


# ============================ hàm cấu trúc NTFS ============================
def ap_dung_fixup(buf, bps=512, log=None):
    """Áp dụng Update Sequence Array (USA / Fixup) cho MFT record hoặc khối INDX.
    Trả về bytes đã khôi phục, hoặc None nếu không hợp lệ hoặc fixup sai lệch USN.
    """
    if len(buf) < 0x2A:
        return None
    b = bytearray(buf)
    usa_off, usa_cnt = struct.unpack_from("<HH", b, 4)
    if usa_off + usa_cnt * 2 > len(b):
        return None
    usn = bytes(b[usa_off:usa_off + 2])
    for k in range(1, usa_cnt):
        end = k * bps
        if end > len(b):
            break
        if bytes(b[end - 2:end]) != usn:
            if log:
                log.canh_bao("fixup: 2 byte cuối sector không khớp USN", sector=k)
            return None
        b[end - 2:end] = b[usa_off + 2 * k:usa_off + 2 * k + 2]
    return bytes(b)


def runlist(data):
    """Giải mã runlist -> [(lcn | None nếu sparse, số cluster)]"""
    runs, pos, lcn = [], 0, 0
    while pos < len(data) and data[pos] != 0:
        h = data[pos]; pos += 1
        ln, lo = h & 0xF, h >> 4
        length = int.from_bytes(data[pos:pos + ln], "little"); pos += ln
        if lo == 0:
            runs.append((None, length))
        else:
            lcn += int.from_bytes(data[pos:pos + lo], "little", signed=True)
            runs.append((lcn, length))
        pos += lo
    return runs


def parse_key(k):
    """Key $FILE_NAME (dùng cho cả index entry và attribute $FILE_NAME)."""
    if len(k) < 0x42:
        return None
    nl = k[0x40]
    raw = bytes(k[0x42:0x42 + 2 * nl])
    return {"parent": int.from_bytes(k[0:6], "little"),
            "times": struct.unpack_from("<4Q", k, 8),
            "alloc": struct.unpack_from("<Q", k, 0x28)[0],
            "real": struct.unpack_from("<Q", k, 0x30)[0],
            "flags": struct.unpack_from("<I", k, 0x38)[0],
            "name_len": nl, "ns": k[0x41], "name_raw": raw,
            "name": raw.decode("utf-16le", "replace")}


def index_entries(buf, start):
    """Duyệt index entry từ vị trí start -> [(mft_ref, key_dict, vị trí entry)]"""
    res, pos = [], start
    while pos + 16 <= len(buf):
        ref = int.from_bytes(buf[pos:pos + 6], "little")
        elen, klen, flags = struct.unpack_from("<HHH", buf, pos + 8)
        if klen:
            key = parse_key(buf[pos + 16:pos + 16 + klen])
            if key:
                res.append((ref, key, pos))
        if flags & 2 or elen == 0:
            break
        pos += elen
    return res


def ma_hoa_0x40(rec_size, cluster):
    """Mã hóa kích thước bản ghi MFT vào trường 0x40 của Boot Sector (Clusters per MFT record).
    - Nếu rec_size >= cluster: lưu số nguyên dương (rec_size // cluster).
    - Nếu rec_size < cluster: lưu số nguyên âm có dấu c sao cho 2^(-c) = rec_size,
      tức c = -(rec_size.bit_length() - 1). Ví dụ 1024 -> -10 (0xF6).
    """
    if rec_size >= cluster:
        return rec_size // cluster
    return -(rec_size.bit_length() - 1)


class NTFS:
    def __init__(self, img, log, override_boot=None):
        self.img, self.log = img, log
        if override_boot:
            self.bps = override_boot["bps"]
            self.spc = override_boot["spc"]
            self.cluster = override_boot["cluster"]
            self.mft_lcn = override_boot["mft_lcn"]
            self.tong_sector = override_boot.get("tong_sector", img.u64(0x28))
            self.rec_size = override_boot["rec_size"]
            log.buoc("bytes/sector (suy luận)", 0x0B, self.bps)
            log.buoc("sectors/cluster (suy luận)", 0x0D, self.spc)
            log.buoc("$MFT LCN (suy luận)", 0x30, self.mft_lcn)
            log.buoc("kích thước MFT record (suy luận)", 0x40, self.rec_size)
        else:
            self._doc_boot()
        self._doc_mft0()

    # ---------- boot sector ----------
    def _doc_boot(self):
        i, L = self.img, self.log
        self.bps = i.u16(0x0B)
        self.spc = i.u8(0x0D)
        self.cluster = self.bps * self.spc
        self.mft_lcn = i.u64(0x30)
        self.tong_sector = i.u64(0x28)
        n = i.s8(0x40)
        self.rec_size = n * self.cluster if n > 0 else 1 << (-n)
        L.buoc("bytes/sector", 0x0B, self.bps)
        L.buoc("sectors/cluster", 0x0D, self.spc)
        L.buoc("$MFT LCN", 0x30, self.mft_lcn)
        L.buoc("kích thước MFT record (byte)", 0x40, self.rec_size)

    # ---------- fixup (Update Sequence Array) ----------
    def fixup(self, buf):
        return ap_dung_fixup(buf, self.bps, self.log)

    # ---------- attribute ----------
    @staticmethod
    def attrs(rec, log=None):
        pos = struct.unpack_from("<H", rec, 0x14)[0]
        while pos + 8 <= len(rec):
            t, ln = struct.unpack_from("<II", rec, pos)
            if t == 0xFFFFFFFF or ln == 0 or pos + ln > len(rec):
                break
            if t == ATTR_ATTRIBUTE_LIST and log is not None:
                log.canh_bao("Phát hiện thuộc tính $ATTRIBUTE_LIST (0x20) - giới hạn đã biết chưa hỗ trợ bản ghi MFT phụ", offset=pos)
            nonres, name_len = rec[pos + 8], rec[pos + 9]
            a = {"type": t, "nonres": nonres, "name_len": name_len}
            if not nonres:
                size, off = struct.unpack_from("<IH", rec, pos + 0x10)
                a["content"] = bytes(rec[pos + off:pos + off + size])
                a["real"] = size
            else:
                ro = struct.unpack_from("<H", rec, pos + 0x20)[0]
                a["real"] = struct.unpack_from("<Q", rec, pos + 0x30)[0]
                a["runs"] = runlist(rec[pos + ro:pos + ln])
            yield a
            pos += ln

    # ---------- MFT ----------
    def _doc_mft0(self):
        off = self.mft_lcn * self.cluster
        raw = self.img.doc(off, self.rec_size)
        rec = self.fixup(raw)
        if rec is None:
            raise RuntimeError("Lỗi fixup khi nạp Bản ghi 0 của $MFT")
        d = next(a for a in self.attrs(rec, self.log) if a["type"] == ATTR_DATA and a["name_len"] == 0)
        self.mft_runs, self.mft_real = d["runs"], d["real"]
        self.log.buoc("runlist của $MFT", off, self.mft_runs)

    def offset_record(self, n):
        byte = n * self.rec_size
        for lcn, cnt in self.mft_runs:
            if byte < cnt * self.cluster:
                return None if lcn is None else lcn * self.cluster + byte
            byte -= cnt * self.cluster
        return None

    def so_record(self):
        return self.mft_real // self.rec_size

    def doc_record(self, n):
        off = self.offset_record(n)
        if off is None or off + self.rec_size > self.img.kich_thuoc:
            return None
        raw = self.img.doc(off, self.rec_size)
        return self.fixup(raw) if raw[:4] == b"FILE" else None

    @staticmethod
    def flags(rec):
        return struct.unpack_from("<H", rec, 0x16)[0]

    def in_use(self, rec): return bool(self.flags(rec) & 1)
    def is_dir(self, rec): return bool(self.flags(rec) & 2)

    # ---------- dữ liệu của $DATA ----------
    def doc_data_attr(self, a):
        if not a["nonres"]:
            return a["content"]
        out = bytearray()
        for lcn, n in a["runs"]:
            out += bytes(n * self.cluster) if lcn is None \
                else self.img.doc(lcn * self.cluster, n * self.cluster)
        return bytes(out[:a["real"]])

    def thong_tin_record(self, rec):
        """Gom: danh sách $FILE_NAME, $DATA không tên."""
        fns, data = [], None
        for a in self.attrs(rec, self.log):
            if a["type"] == ATTR_FN and not a["nonres"]:
                k = parse_key(a["content"])
                if k:
                    fns.append(k)
            elif a["type"] == ATTR_DATA and a["name_len"] == 0:
                data = a
        return fns, data

    # ---------- thư mục ----------
    def doc_thu_muc(self, rec):
        ents, blk = [], 4096
        for a in self.attrs(rec, self.log):
            if a["type"] == ATTR_INDEX_ROOT:
                c = a["content"]
                blk = struct.unpack_from("<I", c, 8)[0]
                eo = struct.unpack_from("<I", c, 0x10)[0]
                ents += index_entries(c, 0x10 + eo)
            elif a["type"] == ATTR_INDEX_ALLOC:
                raw = self.doc_data_attr(a)
                for p in range(0, len(raw), blk):
                    b = raw[p:p + blk]
                    if b[:4] != b"INDX":
                        continue
                    b = self.fixup(b)
                    if b is None:
                        continue
                    eo = struct.unpack_from("<I", b, 0x18)[0]
                    ents += index_entries(b, 0x18 + eo)
        return ents


# ============================ phần bài làm ============================
MAGIC = {"jpg": [b"\xFF\xD8\xFF"], "jpeg": [b"\xFF\xD8\xFF"],
         "png": [b"\x89PNG\r\n\x1a\n"], "pdf": [b"%PDF"]}


def khop_magic(ten, head):
    """+1 nếu đầu nội dung khớp đuôi tên; txt: toàn ký tự in được."""
    ext = ten.rsplit(".", 1)[-1].lower() if "." in ten else ""
    if ext in MAGIC:
        return any(head.startswith(m) for m in MAGIC[ext])
    if ext in ("txt", "text", "log", "md"):
        return len(head) > 0 and all(b in (9, 10, 13) or 32 <= b < 127 for b in head)
    return False


def chuan_doan_case1(img, log):
    """Tự động suy luận 3 tham số Boot Sector bị hỏng theo Scenario 1:
    - Sectors per cluster (0x0D)
    - $MFT Starting Cluster LCN (0x30)
    - Clusters per MFT record (0x40)

    Không hardcode bất kỳ giá trị mẫu hay offset cụ thể nào.
    """
    log.buoc("Bắt đầu chẩn đoán Boot Sector bị sai (Scenario 1)", offset=0x00)

    # Đọc Bytes per sector từ BPB (trường 0x0B không bị làm sai)
    bps_doc = img.u16(0x0B)
    if bps_doc < 512 or bps_doc > 4096 or (bps_doc & (bps_doc - 1)):
        log.canh_bao("bytes/sector bất thường, dùng 512", offset=0x0B, gia_tri=bps_doc)
        bps = 512
    else:
        bps = bps_doc

    tong_sector = img.u64(0x28)

    # Log giá trị đang sai ở 0x0D, 0x30, 0x40 của cả sector 0 lẫn sector cuối
    sai_sec0_spc = img.u8(0x0D)
    sai_sec0_lcn = img.u64(0x30)
    sai_sec0_rec = img.u8(0x40)
    log.buoc("Sector 0 (Primary Boot): sectors/cluster đang sai", 0x0D, sai_sec0_spc)
    log.buoc("Sector 0 (Primary Boot): $MFT LCN đang sai", 0x30, sai_sec0_lcn)
    log.buoc("Sector 0 (Primary Boot): clusters/record đang sai", 0x40, sai_sec0_rec)

    backup_offset = tong_sector * bps
    if backup_offset + bps <= img.kich_thuoc:
        sai_bak_spc = img.u8(backup_offset + 0x0D)
        sai_bak_lcn = img.u64(backup_offset + 0x30)
        sai_bak_rec = img.u8(backup_offset + 0x40)
        log.buoc("Sector cuối (Backup Boot): sectors/cluster đang sai", backup_offset + 0x0D, sai_bak_spc)
        log.buoc("Sector cuối (Backup Boot): $MFT LCN đang sai", backup_offset + 0x30, sai_bak_lcn)
        log.buoc("Sector cuối (Backup Boot): clusters/record đang sai", backup_offset + 0x40, sai_bak_rec)

    # 1. Quét toàn ảnh tìm Bản ghi 0 của $MFT bằng img.tim(b"FILE", o, None, bps)
    mft_offset = -1
    mft_lcn = None
    rec_size = None
    cluster = None
    spc = None

    o = 0
    while True:
        o = img.tim(b"FILE", o, None, bps)
        if o < 0:
            break

        if o + 0x42 > img.kich_thuoc:
            break

        # Đọc allocated size ở +0x1C
        alloc_sz = img.u32(o + 0x1C)
        if alloc_sz < bps or alloc_sz > 65536 or (alloc_sz & (alloc_sz - 1)) != 0:
            o += bps
            continue

        if o + alloc_sz > img.kich_thuoc:
            o += bps
            continue

        raw = img.doc(o, alloc_sz)
        rec = ap_dung_fixup(raw, bps, log=None)
        if rec is None:
            o += bps
            continue

        # Đọc thuộc tính $FILE_NAME và so đúng tên "$MFT"
        has_mft_name = False
        cand_runs = None
        for a in NTFS.attrs(rec, log=None):
            if a["type"] == ATTR_FN and not a["nonres"]:
                k = parse_key(a["content"])
                if k and k["name"] == "$MFT":
                    has_mft_name = True
            elif a["type"] == ATTR_DATA and a["name_len"] == 0 and a["nonres"]:
                cand_runs = a.get("runs")

        if not has_mft_name or not cand_runs:
            o += bps
            continue

        cand_lcn = cand_runs[0][0]
        if cand_lcn is None or cand_lcn <= 0:
            o += bps
            continue

        # Kiểm tra cluster = offset // mft_lcn
        if o % cand_lcn != 0:
            o += bps
            continue

        cand_cluster = o // cand_lcn

        # Kiểm tra cand_cluster là lũy thừa của 2 trong khoảng [bps, 64 KiB]
        if not (bps <= cand_cluster <= 65536 and (cand_cluster & (cand_cluster - 1)) == 0):
            o += bps
            continue

        # Khẳng định Bản ghi 0 của $MFT
        mft_offset = o
        mft_lcn = cand_lcn
        rec_size = alloc_sz
        cluster = cand_cluster
        spc = cluster // bps
        break

    if mft_offset < 0:
        raise RuntimeError("Không tìm thấy Bản ghi 0 của $MFT trên ảnh đĩa")

    log.quyet_dinh("Tìm thấy Bản ghi 0 của $MFT", offset=mft_offset)

    rec_size_byte = ma_hoa_0x40(rec_size, cluster)
    log.quyet_dinh("Xác định kích thước bản ghi MFT từ allocated size (+0x1C)",
                   rec_size=rec_size, byte_0x40=rec_size_byte)
    log.quyet_dinh("Suy ra $MFT LCN đúng từ Runlist của Bản ghi 0", mft_lcn=mft_lcn)
    log.quyet_dinh("Tính toán thông số đúng", cluster_size=cluster, sectors_per_cluster=spc)

    return {
        "bps": bps,
        "spc": spc,
        "cluster": cluster,
        "mft_lcn": mft_lcn,
        "rec_size": rec_size,
        "rec_size_byte": rec_size_byte,
        "tong_sector": tong_sector,
    }


class BaiLam:
    def __init__(self, log):
        self.log = log

    # ------------------------------------------------------------ --info
    def info(self, img):
        fs = NTFS(img, self.log)
        raw_files = []
        self._duyet(fs, REC_ROOT, "", raw_files, set(), 0)
        files = [{"path": f["path"], "size": f["size"]} for f in raw_files]
        return {"fs": "ntfs", "cluster_size": fs.cluster,
                "bytes_per_sector": fs.bps, "sectors_per_cluster": fs.spc,
                "total_sectors": fs.tong_sector, "mft_lcn": fs.mft_lcn,
                "mft_record_size": fs.rec_size, "so_record_mft": fs.so_record(),
                "files": files}

    def _duyet(self, fs, n, prefix, files, seen, depth):
        if n in seen or depth > 16:
            return
        seen.add(n)
        rec = fs.doc_record(n)
        if rec is None:
            return
        for ref, key, _ in fs.doc_thu_muc(rec):
            if key["ns"] == 2:                      # bản DOS 8.3 trùng lặp
                continue
            if n == REC_ROOT and key["name"].startswith("$"):
                continue                            # file hệ thống
            if key["name"] in (".", ""):
                continue
            path = prefix + key["name"]
            if key["flags"] & FLAG_DIR_KEY:
                self._duyet(fs, ref, path + "/", files, seen, depth + 1)
            else:
                files.append({"path": path, "size": key["real"], "ref": ref})

    # ------------------------------------------------------------ case 1
    def case1(self, img, out):
        L = self.log
        boot_params = chuan_doan_case1(img, L)
        fs = NTFS(img, L, override_boot=boot_params)

        files = []
        self._duyet(fs, REC_ROOT, "", files, set(), 0)
        L.quyet_dinh(f"Tìm thấy {len(files)} tập tin cần trích xuất", so_luong=len(files))

        for f in files:
            rec = fs.doc_record(f["ref"])
            if rec is None:
                continue
            _, d = fs.thong_tin_record(rec)
            if d is not None:
                data = fs.doc_data_attr(d)
                out.luu(f["path"], data)
                L.buoc(f"Đã trích xuất {f['path']}", fs.offset_record(f["ref"]), len(data))

    # ------------------------------------------------------------ case 2
    def case2(self, img, out):
        L = self.log
        fs = NTFS(img, L)

        # 1) Tìm thư mục DATA từ root
        root = fs.doc_record(REC_ROOT)
        data_ref, data_name = None, None
        for ref, key, _ in fs.doc_thu_muc(root):
            if key["name"].upper() == "DATA" and key["flags"] & FLAG_DIR_KEY:
                data_ref, data_name = ref, key["name"]
                break
        if data_ref is None:
            raise RuntimeError("không tìm thấy thư mục DATA trong root")
        L.buoc("Thư mục DATA: số MFT record", fs.offset_record(data_ref), data_ref)

        # 2) Đọc index entry của DATA
        entries = [(r, k, p) for r, k, p in fs.doc_thu_muc(fs.doc_record(data_ref))
                   if k["ns"] != 2 and k["name"] not in (".", "")]
        L.buoc("Số index entry trong DATA", None, len(entries))

        # 3) Phân loại entry: tốt (record khớp tên + parent) hay hỏng
        tot, hong, da_nhan = [], [], set()
        for ref, key, pos in entries:
            rec = fs.doc_record(ref)
            ok = False
            if rec and fs.in_use(rec) and not fs.is_dir(rec):
                fns, _ = fs.thong_tin_record(rec)
                ok = any(f["parent"] == data_ref and f["name_raw"] == key["name_raw"]
                         for f in fns)
            (tot if ok else hong).append((ref, key))
            if ok:
                da_nhan.add(ref)
            L.buoc(f"Entry '{key['name']}': ref={ref} -> {'TỐT' if ok else 'HỎNG'}",
                   fs.offset_record(ref), key["real"])

        # 4) Quét MFT tìm record mồ côi
        orphans = []
        for n in range(16, fs.so_record()):
            if n in da_nhan or n == data_ref:
                continue
            rec = fs.doc_record(n)
            if rec is None or not fs.in_use(rec) or fs.is_dir(rec):
                continue
            fns, d = fs.thong_tin_record(rec)
            if d is None or not fns:
                continue
            thuoc_data = any(f["parent"] == data_ref for f in fns)
            ten_zero = any(f["name_len"] > 0 and not any(f["name_raw"]) for f in fns)
            if thuoc_data or ten_zero:
                data = fs.doc_data_attr(d)
                orphans.append({"n": n, "fns": fns, "real": d["real"], "data": data})
                L.buoc(f"Orphan: record {n}, real size $DATA", fs.offset_record(n), d["real"])

        # 5) Ghép: chấm điểm mọi cặp (entry hỏng, orphan), chọn tham lam theo điểm cao nhất
        cap = []
        for i, (ref, key) in enumerate(hong):
            for o in orphans:
                diem, ly_do = 0, []
                if o["real"] == key["real"]:
                    diem += 100; ly_do.append("real size")
                if any(f["name_len"] == key["name_len"] for f in o["fns"]):
                    diem += 10; ly_do.append("độ dài tên")
                if any(f["times"] == key["times"] for f in o["fns"]):
                    diem += 30; ly_do.append("timestamp")
                if any(f["alloc"] == key["alloc"] for f in o["fns"]):
                    diem += 5; ly_do.append("allocated size")
                if khop_magic(key["name"], o["data"][:16]):
                    diem += 20; ly_do.append("magic/đuôi tên")
                cap.append((diem, i, o["n"], ly_do))
        cap.sort(key=lambda x: -x[0])

        entry_xong, orphan_xong = set(), set()
        for diem, i, n, ly_do in cap:
            if i in entry_xong or n in orphan_xong:
                continue
            if diem < 100:
                L.canh_bao("bỏ cặp điểm thấp (không khớp real size)", entry=hong[i][1]["name"],
                           record=n, diem=diem)
                continue
            ties = [c for c in cap if c[1] == i and c[0] == diem and c[2] not in orphan_xong]
            if len(ties) > 1:
                L.canh_bao("nhập nhằng: nhiều orphan cùng điểm", entry=hong[i][1]["name"],
                           ung_vien=[c[2] for c in ties])
            entry_xong.add(i); orphan_xong.add(n)
            name = hong[i][1]["name"]
            o = next(x for x in orphans if x["n"] == n)
            L.quyet_dinh(f"Ghép '{name}' với MFT record {n}", diem=diem, tieu_chi=ly_do)
            out.luu(f"{data_name}/{name}", o["data"])

        for i, (ref, key) in enumerate(hong):
            if i not in entry_xong:
                L.canh_bao("entry hỏng nhưng không ghép được", entry=key["name"])

        # 6) Lưu thêm các file không bị ảnh hưởng
        for ref, key in tot:
            _, d = fs.thong_tin_record(fs.doc_record(ref))
            if d is not None:
                out.luu(f"{data_name}/{key['name']}", fs.doc_data_attr(d))

    def case3(self, img, out):
        raise NotImplementedError("case3")

    def case_ext(self, img, out):
        raise NotImplementedError("case_ext")

    def repair(self, img, case, anh_moi):
        if str(case) == "1":
            L = self.log
            params = chuan_doan_case1(img, L)
            bps = params["bps"]
            tong_sector = params["tong_sector"]
            backup_offset = tong_sector * bps

            ban_sua = img.sao_chep(anh_moi)
            try:
                # Kiểm tra vị trí sector cuối trong giới hạn ảnh
                if backup_offset + bps > ban_sua.kich_thuoc:
                    raise RuntimeError(
                        f"Vị trí Backup Boot Sector ({backup_offset:#x}) vượt quá kích thước ảnh ({ban_sua.kich_thuoc:#x})"
                    )

                # Trước khi ghi: kiểm tra OEM ID NTFS ở sector cuối
                oem_backup = ban_sua.doc(backup_offset + 3, 8)
                if oem_backup != b"NTFS    ":
                    raise RuntimeError(
                        f"Sector cuối không phải Backup Boot Sector NTFS hợp lệ (OEM ID: {oem_backup!r})"
                    )

                # Log giá trị đang sai ở 0x0D, 0x30, 0x40 của cả sector 0 lẫn sector cuối
                L.buoc("Sector 0 trước khi sửa: sectors/cluster", 0x0D, ban_sua.u8(0x0D))
                L.buoc("Sector 0 trước khi sửa: $MFT LCN", 0x30, ban_sua.u64(0x30))
                L.buoc("Sector 0 trước khi sửa: clusters/record", 0x40, ban_sua.u8(0x40))

                L.buoc("Backup Sector trước khi sửa: sectors/cluster", backup_offset + 0x0D, ban_sua.u8(backup_offset + 0x0D))
                L.buoc("Backup Sector trước khi sửa: $MFT LCN", backup_offset + 0x30, ban_sua.u64(backup_offset + 0x30))
                L.buoc("Backup Sector trước khi sửa: clusters/record", backup_offset + 0x40, ban_sua.u8(backup_offset + 0x40))

                # Sửa Sector 0 (Primary Boot Sector)
                ban_sua.ghi_u8(0x0D, params["spc"])
                ban_sua.ghi_u64(0x30, params["mft_lcn"])
                ban_sua.ghi_u8(0x40, params["rec_size_byte"] & 0xFF)

                # Sửa Sector cuối cùng (Backup Boot Sector)
                ban_sua.ghi_u8(backup_offset + 0x0D, params["spc"])
                ban_sua.ghi_u64(backup_offset + 0x30, params["mft_lcn"])
                ban_sua.ghi_u8(backup_offset + 0x40, params["rec_size_byte"] & 0xFF)
            finally:
                ban_sua.dong()

            L.quyet_dinh("Đã sửa Boot Sector chính và dự phòng trên bản sao", anh_moi=anh_moi)

            # Sau khi ghi: mở lại ảnh mới để xác minh đọc được bằng đường boot sector bình thường
            with AnhDia(anh_moi) as img_moi:
                fs_moi = NTFS(img_moi, L)  # Đọc tự nhiên từ Boot Sector đã sửa, không override
                files_moi = []
                self._duyet(fs_moi, REC_ROOT, "", files_moi, set(), 0)
                L.quyet_dinh("Xác minh thành công: đọc ảnh đã sửa bằng Boot Sector chuẩn",
                             so_tap_tin=len(files_moi), cluster_size=fs_moi.cluster)
        else:
            raise NotImplementedError(f"repair chưa cài đặt cho case {case}")

    def corrupt(self, img, dac_ta, anh_hong):
        raise NotImplementedError("corrupt")
