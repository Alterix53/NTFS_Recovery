"""PHẦN LÀM BÀI - NTFS: info(), case1(), case2(), case3(), case_ext(), repair() và corrupt(). Không hard-code offset/giá trị của ảnh."""
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
    (Theo Project.pdf: ảnh NTFS tạo bằng mkntfs -Q -c 4096 -s 512, bước nhảy Fixup = 512B).
    """
    if len(buf) < 0x2A:
        return None
    b = bytearray(buf)
    usa_off, usa_cnt = struct.unpack_from("<HH", b, 4)  # +0x04: offset mảng USA (2B), +0x06: số phần tử n+1 (2B)
    # Chặn usa_cnt < 2 (tránh khối rác bắt đầu bằng "FILE" có usa_cnt=0/1 lọt qua vòng lặp fixup)
    if usa_off < 8 or usa_cnt < 2 or usa_off + usa_cnt * 2 > len(b):
        return None
    usn = bytes(b[usa_off:usa_off + 2])                 # 2 byte đầu tại usa_off: Update Sequence Number (USN)
    for k in range(1, usa_cnt):
        end = k * bps                                   # vị trí kết thúc của sector thứ k
        if end > len(b):
            break
        if bytes(b[end - 2:end]) != usn:                # 2 byte cuối mỗi sector (+0x1FE, +0x3FE...) phải khớp USN
            if log:
                log.canh_bao("fixup: 2 byte cuối sector không khớp USN", sector=k)
            return None
        b[end - 2:end] = b[usa_off + 2 * k:usa_off + 2 * k + 2]  # hoàn nguyên 2 byte gốc từ mảng USA
    return bytes(b)


def runlist(data):
    """Giải mã runlist -> [(lcn | None nếu sparse, số cluster)]"""
    runs, pos, lcn = [], 0, 0
    while pos < len(data) and data[pos] != 0:           # byte 0x00 đánh dấu kết thúc runlist
        h = data[pos]; pos += 1                         # byte header của run: 4 bit thấp = số byte length, 4 bit cao = số byte LCN offset
        ln, lo = h & 0xF, h >> 4
        length = int.from_bytes(data[pos:pos + ln], "little"); pos += ln  # đọc ln byte: số lượng cluster của run
        if lo == 0:
            runs.append((None, length))
        else:
            lcn += int.from_bytes(data[pos:pos + lo], "little", signed=True)  # đọc lo byte (có dấu): độ dời LCN bắt đầu
            runs.append((lcn, length))
        pos += lo
    return runs


def parse_key(k):
    """Key $FILE_NAME (dùng cho cả index entry và attribute $FILE_NAME)."""
    if len(k) < 0x42:
        return None
    nl = k[0x40]                                        # +0x40: độ dài tên file (số ký tự UTF-16LE, 1B)
    raw = bytes(k[0x42:0x42 + 2 * nl])                  # +0x42: chuỗi tên file mã hóa UTF-16LE (2 * nl byte)
    return {"parent": int.from_bytes(k[0:6], "little"), # +0x00: MFT record cha (6B đầu của 8B file reference)
            "times": struct.unpack_from("<4Q", k, 8),   # +0x08: 4 mốc thời gian tạo/sửa/MFT/truy cập (4 x 8B)
            "alloc": struct.unpack_from("<Q", k, 0x28)[0],  # +0x28: kích thước cấp phát (8B)
            "real": struct.unpack_from("<Q", k, 0x30)[0],   # +0x30: kích thước thực của file (8B)
            "flags": struct.unpack_from("<I", k, 0x38)[0],  # +0x38: cờ thuộc tính file/thư mục (4B)
            "name_len": nl, "ns": k[0x41],              # +0x41: namespace của tên file (1B, 2 = DOS 8.3)
            "name_raw": raw,
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


class AnhVolume:
    """Đọc NTFS bằng offset tương đối với đầu volume."""

    def __init__(self, img, volume_offset=0):
        if volume_offset < 0 or volume_offset >= img.kich_thuoc:
            raise ValueError("Volume offset không hợp lệ")

        self.img = img
        self.volume_offset = volume_offset
        self.kich_thuoc = img.kich_thuoc - volume_offset

    def doc(self, offset, length):
        if (offset < 0 or length < 0
                or offset + length > self.kich_thuoc):
            raise ValueError("Đọc vượt giới hạn volume")

        return self.img.doc(
            self.volume_offset + offset,
            length
        )

    def u8(self, offset):
        return int.from_bytes(self.doc(offset, 1), "little")

    def s8(self, offset):
        return int.from_bytes(
            self.doc(offset, 1), "little", signed=True
        )

    def u16(self, offset):
        return int.from_bytes(self.doc(offset, 2), "little")

    def u64(self, offset):
        return int.from_bytes(self.doc(offset, 8), "little")


def ma_hoa_0x40(rec_size, cluster):
    """Mã hóa kích thước bản ghi MFT vào trường 0x40 của Boot Sector."""
    if rec_size >= cluster:
        return rec_size // cluster
    return -(rec_size.bit_length() - 1)


class NTFS:
    def __init__(self, img, log, volume_offset=0, override_boot=None):
        self.img = AnhVolume(img, volume_offset)
        self.log = log
        self.volume_offset = volume_offset

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
        self.bps = i.u16(0x0B)                          # 0x0B: bytes per sector (2B)
        self.spc = i.u8(0x0D)                           # 0x0D: sectors per cluster (1B)
        self.cluster = self.bps * self.spc
        self.mft_lcn = i.u64(0x30)                      # 0x30: cluster bắt đầu của $MFT - LCN (8B)
        self.tong_sector = i.u64(0x28)                  # 0x28: tổng số sector của volume (8B)
        n = i.s8(0x40)                                  # 0x40: mã kích thước MFT record (1B có dấu: >0 là số cluster, <0 là 2^(-n) byte)
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
        pos = struct.unpack_from("<H", rec, 0x14)[0]    # +0x14: offset byte của attribute đầu tiên (sau mảng USA 2*(n+1) byte)
        while pos + 8 <= len(rec):
            t, ln = struct.unpack_from("<II", rec, pos) # +0x00: mã loại attribute (4B), +0x04: tổng độ dài attribute (4B)
            if t == 0xFFFFFFFF or ln == 0 or pos + ln > len(rec):  # 0xFFFFFFFF: dấu kết thúc danh sách attribute
                break
            if t == ATTR_ATTRIBUTE_LIST and log is not None:
                log.canh_bao("Phát hiện thuộc tính $ATTRIBUTE_LIST (0x20) - giới hạn đã biết chưa hỗ trợ bản ghi MFT phụ", offset=pos)
            nonres, name_len = rec[pos + 8], rec[pos + 9]  # +0x08: cờ non-resident (1B: 0=resident, 1=non-resident), +0x09: độ dài tên attribute (1B)
            a = {"type": t, "nonres": nonres, "name_len": name_len}
            if not nonres:
                size, off = struct.unpack_from("<IH", rec, pos + 0x10)  # Resident: +0x10 kích thước nội dung (4B), +0x14 offset nội dung (2B)
                a["content"] = bytes(rec[pos + off:pos + off + size])
                a["real"] = size
            else:
                ro = struct.unpack_from("<H", rec, pos + 0x20)[0]       # Non-resident: +0x20 offset bắt đầu chuỗi byte runlist (2B)
                a["real"] = struct.unpack_from("<Q", rec, pos + 0x30)[0]  # Non-resident: +0x30 kích thước thực (real size) của dữ liệu (8B)
                a["runs"] = runlist(rec[pos + ro:pos + ln])             # cắt từ pos + ro đến hết attribute để giải mã runlist
            yield a
            pos += ln                                   # nhảy sang attribute kế tiếp theo độ dài ln

    # ---------- MFT ----------
    def _doc_mft0(self):
        off = self.mft_lcn * self.cluster
        rec = self.fixup(self.img.doc(off, self.rec_size))
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
        # Project.pdf (Reduced dataset): file text < 600B nằm dạng Resident (nonres=0);
        # 2 JPEG, 1 PNG, 1 PDF nằm dạng Non-resident (nonres=1), không nén LZNT1 / mã hóa EFS.
        if not a["nonres"]:
            return a["content"]                         # Resident: nội dung nằm trực tiếp trong MFT record
        out = bytearray()
        for lcn, n in a["runs"]:
            out += bytes(n * self.cluster) if lcn is None \
                else self.img.doc(lcn * self.cluster, n * self.cluster)  # Non-resident: đọc từng run (hỗ trợ nhiều run & sparse)
        return bytes(out[:a["real"]])                   # cắt đúng theo real size (+0x30 của header $DATA)

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
        # Project.pdf (Reduced dataset): DATA chỉ dùng $INDEX_ROOT (0x90, không có khối INDX);
        # thư mục gốc $Root (Record 5) dùng thêm 1 khối INDX qua $INDEX_ALLOCATION (0xA0).
        # Ở Scenario 1 mọi cấu trúc thư mục đều nguyên vẹn (không xóa/co thư mục) nên không có khối INDX cũ cần lọc qua $BITMAP (0xB0).
        ents, blk = [], 4096
        for a in self.attrs(rec, self.log):
            if a["type"] == ATTR_INDEX_ROOT:            # 0x90 ($INDEX_ROOT): chứa entry nhỏ hoặc nút gốc B-tree
                c = a["content"]
                blk = struct.unpack_from("<I", c, 8)[0]     # +0x08 của $INDEX_ROOT: kích thước 1 khối INDX (4B, thường 4096)
                eo = struct.unpack_from("<I", c, 0x10)[0]   # +0x10 của $INDEX_ROOT: offset tới index entry đầu tiên (tính từ +0x10)
                ents += index_entries(c, 0x10 + eo)
            elif a["type"] == ATTR_INDEX_ALLOC:         # 0xA0 ($INDEX_ALLOCATION): chứa các khối INDX bên ngoài (dùng cho $Root)
                raw = self.doc_data_attr(a)
                for p in range(0, len(raw), blk):
                    b = raw[p:p + blk]
                    if b[:4] != b"INDX":                # +0x00 của khối INDX: chữ ký "INDX" (4B)
                        continue
                    b = self.fixup(b)                   # áp dụng Fixup (USA) cho khối INDX trước khi đọc entry
                    if b is None:
                        continue
                    eo = struct.unpack_from("<I", b, 0x18)[0]  # +0x18 của khối INDX: offset tới index entry đầu tiên (tính từ +0x18)
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


def jpeg_hop_le(data):
    """Kiểm tra cấu trúc JPEG và dữ liệu ảnh."""
    if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        return False

    pos = 2
    co_frame = co_scan = co_dqt = co_dht = False
    while pos < len(data):
        if data[pos] != 0xff:
            return False
        while pos < len(data) and data[pos] == 0xff:
            pos += 1
        if pos == len(data):
            return False

        marker = data[pos]
        pos += 1
        if marker == 0xd9:
            return (pos == len(data) and co_frame and co_scan
                    and co_dqt and co_dht)
        if marker == 0xd8 or marker == 0x00 or 0xd0 <= marker <= 0xd7:
            return False
        if marker == 0x01:
            continue

        # Độ dài đoạn bao gồm cả hai byte lưu độ dài.
        if pos + 2 > len(data):
            return False
        segment_size = int.from_bytes(data[pos:pos + 2], "big")
        segment_end = pos + segment_size
        if segment_size < 2 or segment_end > len(data):
            return False

        if marker in (0xc0, 0xc1, 0xc2):
            co_frame = True
        elif marker == 0xdb:
            co_dqt = True
        elif marker == 0xc4:
            co_dht = True
        elif not (0xe0 <= marker <= 0xef or marker in (
                0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd,
                0xce, 0xcf, 0xdd, 0xfe, 0xda)):
            return False

        if marker != 0xda:
            pos = segment_end
            continue

        co_scan = True
        pos = segment_end
        # Sau SOS, FF00 là dữ liệu; D0-D7 là mã tiếp tục.
        # Mã khác bắt đầu đoạn JPEG kế tiếp.
        while pos < len(data):
            if data[pos] != 0xff:
                pos += 1
                continue
            next_marker_start = pos
            next_pos = pos + 1
            while next_pos < len(data) and data[next_pos] == 0xff:
                next_pos += 1
            if next_pos == len(data):
                return False
            next_marker = data[next_pos]
            if next_marker == 0x00 or 0xd0 <= next_marker <= 0xd7:
                pos = next_pos + 1
                continue
            pos = next_marker_start
            break
    return False


def tim_volume_ntfs(img, log):
    """Tìm NTFS volume trong whole-disk image."""

    found = []
    start = 0

    while True:
        hit = img.tim(b"NTFS    ", start)

        if hit < 0:
            break

        start = hit + 1
        offset = hit - 3

        # NTFS Boot Sector phải nằm trên ranh giới sector.
        if offset < 512 or offset % 512 != 0:
            continue

        try:
            boot = img.doc(offset, 512)

            if boot[3:11] != b"NTFS    ":
                continue

            if boot[510:512] != b"\x55\xaa":
                continue

            bps = int.from_bytes(boot[11:13], "little")
            spc = boot[13]

            if bps not in (512, 1024, 2048, 4096):
                continue

            if spc not in (1, 2, 4, 8, 16, 32, 64, 128):
                continue

            cluster_size = bps * spc

            total_sectors = int.from_bytes(
                boot[40:48], "little"
            )

            total_bytes = total_sectors * bps

            if (total_bytes < cluster_size
                    or offset + total_bytes > img.kich_thuoc):
                continue

            mft_lcn = int.from_bytes(
                boot[48:56], "little"
            )

            code = int.from_bytes(
                boot[64:65], "little", signed=True
            )

            record_size = (
                code * cluster_size
                if code > 0 else 1 << (-code)
            )

            if (record_size < 512
                    or record_size > 65536
                    or record_size % bps):
                continue

            mft_offset = offset + mft_lcn * cluster_size

            if mft_offset + record_size > offset + total_bytes:
                continue

            raw = img.doc(mft_offset, record_size)

            if raw[:4] != b"FILE":
                continue

            # Kiểm tra USA/fixup của MFT record 0.
            usa_off = int.from_bytes(raw[4:6], "little")
            usa_count = int.from_bytes(raw[6:8], "little")

            if usa_count != record_size // bps + 1:
                continue

            if usa_off < 8 or usa_off + usa_count * 2 > record_size:
                continue

            usn = raw[usa_off:usa_off + 2]

            if any(
                raw[k * bps - 2:k * bps] != usn
                for k in range(1, usa_count)
            ):
                continue

            # Tái sử dụng parser NTFS của nhóm.
            volume = NTFS(img, log, volume_offset=offset)

            found.append(volume)

            log.buoc(
                "Tìm thấy ứng viên NTFS hợp lệ",
                offset=offset,
                gia_tri={
                    "cluster_size": volume.cluster,
                    "mft_record_size": volume.rec_size
                }
            )

        except (ValueError, IndexError, StopIteration,
                OverflowError, struct.error):
            continue

    if len(found) != 1:
        raise ValueError(
            f"Cần đúng 1 NTFS volume, tìm thấy {len(found)}"
        )

    volume = found[0]

    log.quyet_dinh(
        "Chọn NTFS volume",
        offset=volume.volume_offset,
        gia_tri={
            "start_lba": volume.volume_offset // 512
        }
    )

    return volume


def chuan_doan_case1(img, log):
    """Tự động suy luận các tham số Boot Sector bị hỏng cho Scenario 1."""
    log.buoc("Bắt đầu chẩn đoán Boot Sector bị sai (Scenario 1)", offset=0x00)

    bps = img.u16(0x0B)                                 # 0x0B: đọc bytes per sector (2B) từ Boot Sector
    if bps < 512 or bps > 4096 or (bps & (bps - 1)):
        log.canh_bao("bytes/sector bất thường, dùng 512", offset=0x0B, gia_tri=bps)
        bps = 512

    tong_sector = img.u64(0x28)                         # 0x28: tổng số sector của volume (8B)
    sai_sec0_spc = img.u8(0x0D)                         # 0x0D: sectors per cluster đang bị sai ở Sector 0 (1B)
    sai_sec0_lcn = img.u64(0x30)                        # 0x30: $MFT LCN đang bị sai ở Sector 0 (8B)
    sai_sec0_rec = img.u8(0x40)                         # 0x40: mã kích thước MFT record đang bị sai ở Sector 0 (1B)
    log.buoc("Sector 0 (Primary Boot): sectors/cluster đang sai", 0x0D, sai_sec0_spc)
    log.buoc("Sector 0 (Primary Boot): $MFT LCN đang sai", 0x30, sai_sec0_lcn)
    log.buoc("Sector 0 (Primary Boot): clusters/record đang sai", 0x40, sai_sec0_rec)

    backup_offset = tong_sector * bps                   # offset byte của Backup Boot Sector (sector cuối volume)
    if backup_offset + bps <= img.kich_thuoc:
        log.buoc("Sector cuối (Backup Boot): sectors/cluster đang sai",
                 backup_offset + 0x0D, img.u8(backup_offset + 0x0D))    # backup + 0x0D: spc ở Backup Boot (1B)
        log.buoc("Sector cuối (Backup Boot): $MFT LCN đang sai",
                 backup_offset + 0x30, img.u64(backup_offset + 0x30))   # backup + 0x30: $MFT LCN ở Backup Boot (8B)
        log.buoc("Sector cuối (Backup Boot): clusters/record đang sai",
                 backup_offset + 0x40, img.u8(backup_offset + 0x40))    # backup + 0x40: mã rec_size ở Backup Boot (1B)

    o = 0
    while True:
        o = img.tim(b"FILE", o, None, bps)              # +0x00: quét theo bước nhảy bps tìm chữ ký "FILE" (4B) của MFT record
        if o < 0:
            break
        if o + 0x42 > img.kich_thuoc:
            break

        alloc_sz = img.u32(o + 0x1C)                    # +0x1C: kích thước cấp phát (allocated size) của MFT record (4B, vd 1024)
        # Project.pdf dùng mkntfs -Q -c 4096 -s 512 (bps=512, rec_size=1024); chấp nhận lũy thừa 2 trong [bps, 64 KiB]
        if (alloc_sz < bps or alloc_sz > 65536
                or (alloc_sz & (alloc_sz - 1)) != 0
                or o + alloc_sz > img.kich_thuoc):
            o += bps
            continue

        rec = ap_dung_fixup(img.doc(o, alloc_sz), bps, log=None)  # kiểm tra USN và khôi phục 2 byte cuối mỗi sector
        if rec is None:
            o += bps
            continue

        has_mft_name = False
        cand_runs = None
        try:
            for a in NTFS.attrs(rec, log=None):         # nhảy từ +0x14 (offset attribute đầu tiên) duyệt từng attribute
                if a["type"] == ATTR_FN and not a["nonres"]:  # 0x30 ($FILE_NAME): đọc tên file tại +0x42 của nội dung attribute
                    k = parse_key(a["content"])
                    if k and k["name"] == "$MFT":       # khớp chính xác "$MFT" (loại "$MFTMirr" ở Record 1)
                        has_mft_name = True
                elif a["type"] == ATTR_DATA and a["name_len"] == 0 and a["nonres"]:  # 0x80 ($DATA không tên, non-resident)
                    cand_runs = a.get("runs")           # lấy runlist đã giải mã từ offset +0x20 của header $DATA
        except (struct.error, ValueError, IndexError):  # tránh crash nếu gặp khối dữ liệu rác chứa chữ ký "FILE" trước $MFT
            o += bps
            continue

        if not has_mft_name or not cand_runs:
            o += bps
            continue

        cand_lcn = cand_runs[0][0]                      # LCN bắt đầu của run đầu tiên trong runlist $MFT
        if cand_lcn is None or cand_lcn <= 0 or o % cand_lcn != 0:
            o += bps
            continue

        cand_cluster = o // cand_lcn                    # suy ra kích thước cluster = offset byte của Record 0 / mft_lcn
        # NTFS chuẩn (0x0D dương 1..128): cluster là lũy thừa của 2 trong [bps, 64 KiB] (loại bản sao trong $MFTMirr)
        if not (bps <= cand_cluster <= 65536
                and (cand_cluster & (cand_cluster - 1)) == 0):
            o += bps
            continue

        # Xác thực chéo Record 5 ($Root) theo cand_runs để loại trừ tuyệt đối $MFTMirr trong mọi bố cục đĩa
        # ($MFTMirr chỉ sao lưu 4 bản ghi 0..3 nên không có Record 5; ngoài ra mkntfs luôn đặt $MFT trước $MFTMirr).
        byte5, off5 = REC_ROOT * alloc_sz, None
        for r_lcn, r_cnt in cand_runs:
            if byte5 < r_cnt * cand_cluster:
                off5 = None if r_lcn is None else r_lcn * cand_cluster + byte5
                break
            byte5 -= r_cnt * cand_cluster
        if off5 is None or off5 + alloc_sz > img.kich_thuoc:
            o += bps
            continue
        raw5 = img.doc(off5, alloc_sz)
        rec5 = ap_dung_fixup(raw5, bps, log=None) if raw5[:4] == b"FILE" else None
        if rec5 is None or not (NTFS.flags(rec5) & 2):  # +0x16 của Record 5: bit 1 (0x02) xác nhận là thư mục $Root
            o += bps
            continue

        mft_lcn = cand_lcn
        rec_size = alloc_sz
        cluster = cand_cluster
        spc = cluster // bps                            # suy ra sectors per cluster = cluster_size / bytes_per_sector
        break
    else:
        raise RuntimeError("Không tìm thấy Bản ghi 0 của $MFT trên ảnh đĩa")

    log.quyet_dinh("Tìm thấy Bản ghi 0 của $MFT", offset=o)
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
##############

class BaiLam:
    def __init__(self, log):
        self.log = log

    # ------------------------------------------------------------ --info
    def info(self, img):
        fs = NTFS(img, self.log)
        files = []
        self._duyet(fs, REC_ROOT, "", files, set(), 0)
        files = [{"path": f["path"], "size": f["size"]} for f in files]
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

    # ----- các hàm của thành viên khác / bonus -----
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

    def case3(self, img, out):
        """Khôi phục 4 file nguyên vẹn rồi tìm mảnh còn thiếu của JPEG lớn."""
        fs = NTFS(img, self.log)

        # Tìm thư mục DATA trong thư mục gốc.
        root = fs.doc_record(REC_ROOT)
        data_ref = None
        for record_ref, key, _ in fs.doc_thu_muc(root):
            if key["name"].upper() == "DATA" and key["flags"] & FLAG_DIR_KEY:
                data_ref = record_ref
                break
        if data_ref is None:
            raise RuntimeError("Không tìm thấy thư mục DATA")

        # Lấy tên và dữ liệu của từng file trong DATA.
        files = []
        for record_ref, key, _ in fs.doc_thu_muc(fs.doc_record(data_ref)):
            if key["ns"] == 2 or key["name"] in ("", ".", ".."):
                continue
            if key["flags"] & FLAG_DIR_KEY:
                continue

            record = fs.doc_record(record_ref)
            if record is None:
                raise RuntimeError(f"Không đọc được MFT record {record_ref}")
            _, data_attr = fs.thong_tin_record(record)
            if data_attr is None:
                raise RuntimeError(f"File {key['name']} không có $DATA")
            files.append({"record": record_ref, "name": key["name"], "data": data_attr})

        jpegs = [f for f in files if f["name"].lower().endswith((".jpg", ".jpeg"))]
        if len(files) != 5 or len(jpegs) != 2:
            raise RuntimeError("DATA phải có 5 file, trong đó có 2 JPEG")
        target = max(jpegs, key=lambda f: f["data"]["real"])
        intact_files = [f for f in files if f != target]

        # Đánh dấu các cụm đã dùng để tránh ghi đè dữ liệu file khác.
        bitmap_record = fs.doc_record(6)
        _, bitmap_attr = fs.thong_tin_record(bitmap_record)
        if bitmap_attr is None:
            raise RuntimeError("Không đọc được $Bitmap")
        bitmap = fs.doc_data_attr(bitmap_attr)
        volume_clusters = fs.tong_sector // fs.spc
        used_clusters = set()
        for cluster in range(min(volume_clusters, len(bitmap) * 8)):
            if bitmap[cluster // 8] & (1 << (cluster % 8)):
                used_clusters.add(cluster)

        # Khôi phục các file nguyên vẹn và giữ chỗ cho cụm của chúng.
        for file_info in intact_files:
            data_attr = file_info["data"]
            for start_lcn, length in data_attr.get("runs", []):
                if start_lcn is not None:
                    used_clusters.update(range(start_lcn, start_lcn + length))
            content = fs.doc_data_attr(data_attr)
            path = f"DATA/{file_info['name']}"
            out.luu(path, content)
            self.log.buoc("Khôi phục file nguyên vẹn", fs.offset_record(file_info["record"]),
                          {"path": path, "size": len(content)})

        # MFT còn giữ cụm đầu tiên và kích thước gốc của JPEG.
        jpeg_attr = target["data"]
        if not jpeg_attr["nonres"] or not jpeg_attr.get("runs"):
            raise RuntimeError("JPEG mục tiêu không có runlist hợp lệ")
        first_lcn = jpeg_attr["runs"][0][0]
        if first_lcn is None:
            raise RuntimeError("Run đầu tiên của JPEG là sparse")

        file_size = jpeg_attr["real"]
        cluster_size = fs.cluster
        needed_clusters = (file_size + cluster_size - 1) // cluster_size
        end_in_cluster = file_size % cluster_size or cluster_size
        used_clusters.discard(first_lcn)
        self.log.buoc("Thông tin JPEG cần ghép", fs.offset_record(target["record"]),
                      {"name": target["name"], "first_LCN": first_lcn,
                       "size": file_size, "clusters": needed_clusters})

        def read_clusters(start_lcn, count):
            offset = start_lcn * cluster_size
            return fs.img.doc(offset, count * cluster_size)

        result = None
        for first_length in range(1, needed_clusters):
            # Kiểm tra mảnh đầu không đè lên file khác.
            first_fragment = range(first_lcn, first_lcn + first_length)
            if any(cluster in used_clusters for cluster in first_fragment):
                continue

            second_length = needed_clusters - first_length
            first_possible_lcn2 = first_lcn + first_length + 1
            last_possible_lcn2 = min(
                first_lcn + first_length + 64,
                volume_clusters - second_length,
            )
            for second_lcn in range(first_possible_lcn2, last_possible_lcn2 + 1):
                self.log.buoc("Thử vị trí mảnh 2", gia_tri={
                    "L1": first_length, "LCN_2": second_lcn, "L2": second_length,
                })
                second_fragment = range(second_lcn, second_lcn + second_length)
                if any(cluster in used_clusters for cluster in second_fragment):
                    continue

                # Kiểm tra dấu kết thúc JPEG trước khi ghép dữ liệu.
                last_cluster = read_clusters(second_lcn + second_length - 1, 1)
                if last_cluster[end_in_cluster - 2:end_in_cluster] != b"\xff\xd9":
                    continue

                content = (read_clusters(first_lcn, first_length)
                           + read_clusters(second_lcn, second_length))[:file_size]
                if not jpeg_hop_le(content):
                    continue
                result = (first_length, second_lcn, second_length, content)
                break
            if result is not None:
                break

        if result is None:
            raise RuntimeError("Không tìm thấy vị trí fragment 2 phù hợp")

        first_length, second_lcn, second_length, content = result
        path = f"DATA/{target['name']}"
        out.luu(path, content)
        self.log.quyet_dinh("Đã ghép lại JPEG", path=path,
                            runlist=[(first_lcn, first_length),
                                     (second_lcn, second_length)],
                            size=len(content))

    def case_ext(self, img, out):
        """Bonus C: Phục hồi NTFS khi mất MBR partition entry 0."""

        L = self.log

        # 1. Bắt đầu quá trình phục hồi.
        L.buoc(
            "Bonus C: Bắt đầu phục hồi",
            offset=0x1BE,
            gia_tri="Lost MBR partition entry 0"
        )

        # 2. Tìm lại NTFS volume trong whole-disk image.
        # Không sử dụng thông tin MBR entry đã bị xóa.
        fs = tim_volume_ntfs(img, L)

        # 3. Đọc MFT record 5 ($Root).
        root = fs.doc_record(REC_ROOT)

        if root is None:
            raise ValueError(
                "Không đọc được MFT record của root directory"
            )

        # 4. Tìm thư mục DATA trong root directory.
        data_ref = None
        data_name = None

        for ref, key, _ in fs.doc_thu_muc(root):

            if (
                key["name"].upper() == "DATA"
                and key["flags"] & FLAG_DIR_KEY
            ):
                data_ref = ref
                data_name = key["name"]
                break

        if data_ref is None:
            raise ValueError(
                "Không tìm thấy thư mục DATA trong root directory"
            )

        L.buoc(
            "Đã tìm thấy thư mục DATA",
            offset=fs.volume_offset,
            gia_tri={
                "mft_record": data_ref,
                "directory_name": data_name
            }
        )

        # 5. Đọc MFT record của thư mục DATA.
        data_record = fs.doc_record(data_ref)

        if data_record is None:
            raise ValueError(
                "Không đọc được MFT record của thư mục DATA"
            )

        # 6. Duyệt directory index để lấy danh sách file.
        recovered = 0
        seen = set()

        for ref, key, _ in fs.doc_thu_muc(data_record):

            # Bỏ qua tên DOS 8.3 để tránh khôi phục trùng.
            if key["ns"] == 2:
                continue

            name = key["name"]

            # Bỏ qua tên không hợp lệ.
            if name in ("", ".", ".."):
                continue

            # Bonus C chỉ khôi phục các file trong DATA.
            if key["flags"] & FLAG_DIR_KEY:
                continue

            # Ngăn tên file tạo đường dẫn ngoài thư mục kết quả.
            if "/" in name or "\\" in name:
                raise ValueError(
                    f"Tên tập tin không hợp lệ: {name}"
                )

            path = f"{data_name}/{name}"

            # Tránh xuất trùng tập tin.
            if path in seen:
                continue

            # 7. Đọc MFT record của file.
            rec = fs.doc_record(ref)

            if rec is None:
                raise ValueError(
                    f"Không đọc được MFT record: {name}"
                )

            if not fs.in_use(rec):
                raise ValueError(
                    f"MFT record không còn được sử dụng: {name}"
                )

            if fs.is_dir(rec):
                continue

            # 8. Tìm thuộc tính $DATA không tên.
            _, data_attr = fs.thong_tin_record(rec)

            if data_attr is None:
                raise ValueError(
                    f"Không tìm thấy thuộc tính $DATA: {name}"
                )

            # 9. Đọc nội dung tập tin.
            content = fs.doc_data_attr(data_attr)

            # Kiểm tra kích thước theo $DATA.
            expected_size = data_attr["real"]

            if len(content) != expected_size:
                raise ValueError(
                    f"Kích thước không khớp: {path}. "
                    f"Expected={expected_size}, "
                    f"Actual={len(content)}"
                )

            # 10. Lưu tập tin theo đường dẫn gốc.
            out.luu(path, content)

            seen.add(path)
            recovered += 1

            L.buoc(
                "Khôi phục file",
                offset=fs.volume_offset,
                gia_tri={
                    "path": path,
                    "mft_record": ref,
                    "size": len(content)
                }
            )

        # 11. Kiểm tra kết quả.
        if recovered == 0:
            raise ValueError(
                "Không có tập tin nào được phục hồi"
            )

        L.quyet_dinh(
            "Bonus C: Hoàn thành",
            gia_tri={
                "so_file": recovered,
                "volume_offset": fs.volume_offset,
                "cluster_size": fs.cluster,
                "mft_record_size": fs.rec_size
            }
        )


    def repair(self, img, case, anh_moi):
        if str(case) == "1":
            L = self.log
            params = chuan_doan_case1(img, L)
            bps = params["bps"]
            tong_sector = params["tong_sector"]
            backup_offset = tong_sector * bps

            ban_sua = img.sao_chep(anh_moi)
            try:
                if backup_offset + bps > ban_sua.kich_thuoc:
                    raise RuntimeError(
                        f"Vị trí Backup Boot Sector ({backup_offset:#x}) vượt quá kích thước ảnh ({ban_sua.kich_thuoc:#x})"
                    )

                oem_backup = ban_sua.doc(backup_offset + 3, 8)  # backup + 0x03: OEM ID "NTFS    " (8B) tại Backup Boot Sector
                if oem_backup != b"NTFS    ":
                    raise RuntimeError(
                        f"Sector cuối không phải Backup Boot Sector NTFS hợp lệ (OEM ID: {oem_backup!r})"
                    )

                L.buoc("Sector 0 trước khi sửa: sectors/cluster", 0x0D, ban_sua.u8(0x0D))
                L.buoc("Sector 0 trước khi sửa: $MFT LCN", 0x30, ban_sua.u64(0x30))
                L.buoc("Sector 0 trước khi sửa: clusters/record", 0x40, ban_sua.u8(0x40))

                L.buoc("Backup Sector trước khi sửa: sectors/cluster", backup_offset + 0x0D, ban_sua.u8(backup_offset + 0x0D))
                L.buoc("Backup Sector trước khi sửa: $MFT LCN", backup_offset + 0x30, ban_sua.u64(backup_offset + 0x30))
                L.buoc("Backup Sector trước khi sửa: clusters/record", backup_offset + 0x40, ban_sua.u8(backup_offset + 0x40))

                ban_sua.ghi_u8(0x0D, params["spc"])                         # 0x0D: ghi lại sectors per cluster đúng (1B) ở Sector 0
                ban_sua.ghi_u64(0x30, params["mft_lcn"])                    # 0x30: ghi lại $MFT LCN đúng (8B) ở Sector 0
                ban_sua.ghi_u8(0x40, params["rec_size_byte"] & 0xFF)        # 0x40: ghi lại mã kích thước MFT record đúng (1B) ở Sector 0

                ban_sua.ghi_u8(backup_offset + 0x0D, params["spc"])         # backup + 0x0D: ghi lại spc đúng (1B) ở Backup Boot
                ban_sua.ghi_u64(backup_offset + 0x30, params["mft_lcn"])    # backup + 0x30: ghi lại $MFT LCN đúng (8B) ở Backup Boot
                ban_sua.ghi_u8(backup_offset + 0x40, params["rec_size_byte"] & 0xFF)  # backup + 0x40: ghi lại mã rec_size đúng (1B) ở Backup Boot
            finally:
                ban_sua.dong()

            L.quyet_dinh("Đã sửa Boot Sector chính và dự phòng trên bản sao", anh_moi=anh_moi)

            with AnhDia(anh_moi) as img_moi:
                fs_moi = NTFS(img_moi, L)
                files_moi = []
                self._duyet(fs_moi, REC_ROOT, "", files_moi, set(), 0)
                L.quyet_dinh("Xác minh thành công: đọc ảnh đã sửa bằng Boot Sector chuẩn",
                             so_tap_tin=len(files_moi), cluster_size=fs_moi.cluster)
        else:
            raise NotImplementedError(f"repair chưa cài đặt cho case {case}")

    def corrupt(self, img, dac_ta, anh_hong):
        """Bonus C: Xóa MBR partition entry 0."""

        if dac_ta != {
            "tinh_huong": "ext-mbr",
            "partition_index": 0
        }:
            raise ValueError("JSON không đúng Bonus C")

        if img.kich_thuoc < 512:
            raise ValueError("Ảnh đĩa quá nhỏ")

        if img.doc(510, 2) != b"\x55\xaa":
            raise ValueError("MBR signature không hợp lệ")

        if img.doc(3, 8) == b"NTFS    ":
            raise ValueError(
                "Cần whole-disk image, không phải volume image"
            )

        entry = img.doc(0x1BE, 16)

        partition_type = entry[4]
        start_lba = int.from_bytes(entry[8:12], "little")
        sector_count = int.from_bytes(entry[12:16], "little")

        if entry[0] not in (0x00, 0x80):
            raise ValueError("MBR boot indicator không hợp lệ")

        if partition_type != 0x07:
            raise ValueError("Không phải NTFS partition type")

        if start_lba == 0 or sector_count == 0:
            raise ValueError("MBR partition entry không hợp lệ")

        if (start_lba + sector_count) * 512 > img.kich_thuoc:
            raise ValueError("Phân vùng vượt giới hạn ảnh đĩa")

        # Kiểm tra phân vùng trước khi gây lỗi.
        fs = NTFS(
            img,
            self.log,
            volume_offset=start_lba * 512
        )

        if fs.tong_sector > sector_count:
            raise ValueError("NTFS volume vượt MBR partition")

        # Chỉ sửa ảnh sao chép.
        with img.sao_chep(anh_hong) as copy:
            copy.ghi(0x1BE, bytes(16))

        self.log.buoc(
            "Bonus C: Đã xóa MBR partition entry 0",
            offset=0x1BE,
            gia_tri={
                "before": entry.hex(),
                "after": bytes(16).hex()
            }
        )

        return [
            {
                "offset": 0x1BE,
                "length": 16,
                "cau_truc": "MBR partition table entry 0"
            }
        ]
