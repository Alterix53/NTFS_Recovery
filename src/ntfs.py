"""Module giải mã và phục hồi hệ thống tập tin NTFS.
Tuân thủ chuẩn NTFS của Microsoft, không hardcode offset, hỗ trợ Fixup (USA) và giải mã Runlist động.
"""
import struct


def apply_fixup(raw_bytes: bytes, bytes_per_sec: int = 512) -> bytes:
    """Kiểm tra và khôi phục mảng Update Sequence Array (USA / Fixup) của bản ghi FILE hoặc khối INDX.
    Trả về bytes đã khôi phục, hoặc None nếu bản ghi không hợp lệ hoặc fixup sai lệch.
    """
    if len(raw_bytes) < 0x2A or raw_bytes[:4] not in (b"FILE", b"BAAD", b"INDX"):
        return None
    try:
        usa_off = struct.unpack_from("<H", raw_bytes, 0x04)[0]
        usa_cnt = struct.unpack_from("<H", raw_bytes, 0x06)[0]
        if usa_off + usa_cnt * 2 > len(raw_bytes):
            return None
        usn = raw_bytes[usa_off : usa_off + 2]
        buf = bytearray(raw_bytes)
        for i in range(1, usa_cnt):
            pos = i * bytes_per_sec - 2
            if pos + 2 > len(buf):
                return None
            if buf[pos : pos + 2] != usn:
                return None  # Fixup mismatch
            buf[pos : pos + 2] = raw_bytes[usa_off + i * 2 : usa_off + i * 2 + 2]
        return bytes(buf)
    except Exception:
        return None


def parse_runlist(data: bytes):
    """Giải mã chuỗi Data Runs (Runlist) của thuộc tính non-resident NTFS.
    Hỗ trợ delta LCN có dấu (signed), dải phân mảnh và vùng thưa (sparse).
    Trả về danh sách các tuple: [(lcn, cluster_count), ...]
    """
    runs = []
    p = 0
    cur_lcn = 0
    while p < len(data):
        b = data[p]
        p += 1
        if b == 0:
            break
        len_len = b & 0x0F
        off_len = (b >> 4) & 0x0F
        if p + len_len > len(data):
            break
        run_len = int.from_bytes(data[p : p + len_len], "little")
        p += len_len
        if off_len > 0:
            if p + off_len > len(data):
                break
            delta = int.from_bytes(data[p : p + off_len], "little", signed=True)
            p += off_len
            cur_lcn += delta
            runs.append((cur_lcn, run_len))
        else:
            runs.append((None, run_len))  # Vùng thưa (sparse / hole)
    return runs


def read_stream_data(img, runlist, cluster_size: int, real_size: int) -> bytes:
    """Đọc dữ liệu luồng từ Runlist, ghép các dải cluster và cắt đúng real_size."""
    data = bytearray()
    remaining = real_size
    for lcn, count in runlist:
        if remaining <= 0:
            break
        run_bytes = count * cluster_size
        read_len = min(run_bytes, remaining)
        if lcn is None:
            # Dải thưa điền byte 0
            data.extend(b"\x00" * read_len)
        else:
            chunk = img.doc(lcn * cluster_size, read_len)
            data.extend(chunk)
        remaining -= read_len
    return bytes(data[:real_size])


def parse_mft_record(record_bytes: bytes):
    """Bóc tách các thuộc tính của một bản ghi FILE trong MFT.
    Trả về dict chứa thông tin bản ghi hoặc None nếu không hợp lệ.
    """
    if len(record_bytes) < 0x2A or record_bytes[:4] != b"FILE":
        return None

    flags = struct.unpack_from("<H", record_bytes, 0x16)[0]
    in_use = bool(flags & 0x01)
    is_dir = bool(flags & 0x02)

    attr_off = struct.unpack_from("<H", record_bytes, 0x14)[0]
    names = {}  # namespace -> (parent_ref, name)
    data_resident = None
    data_runs = None
    data_size = None

    while attr_off + 4 <= len(record_bytes):
        atype = struct.unpack_from("<I", record_bytes, attr_off)[0]
        if atype == 0xFFFFFFFF:
            break
        alen = struct.unpack_from("<I", record_bytes, attr_off + 4)[0]
        if alen <= 0:
            break

        non_res = record_bytes[attr_off + 8]
        name_len = record_bytes[attr_off + 9]

        if atype == 0x30:  # $FILE_NAME
            c_off = struct.unpack_from("<H", record_bytes, attr_off + 0x14)[0]
            val = record_bytes[attr_off + c_off :]
            if len(val) >= 66:
                parent_ref = struct.unpack_from("<Q", val, 0)[0] & 0xFFFFFFFFFFFF
                fn_len = val[64]
                ns = val[65]
                if len(val) >= 66 + fn_len * 2:
                    fname = val[66 : 66 + fn_len * 2].decode("utf-16le", errors="replace")
                    names[ns] = (parent_ref, fname)

        elif atype == 0x80 and name_len == 0:  # Thuộc tính $DATA không tên
            if non_res:
                data_size = struct.unpack_from("<Q", record_bytes, attr_off + 0x30)[0]
                r_off = struct.unpack_from("<H", record_bytes, attr_off + 0x20)[0]
                data_runs = parse_runlist(record_bytes[attr_off + r_off : attr_off + alen])
            else:
                data_size = struct.unpack_from("<I", record_bytes, attr_off + 0x10)[0]
                c_off = struct.unpack_from("<H", record_bytes, attr_off + 0x14)[0]
                data_resident = record_bytes[attr_off + c_off : attr_off + c_off + data_size]

        attr_off += alen

    # Ưu tiên namespace: Win32 (1), Win32 & DOS (3), POSIX (0), DOS (2)
    chosen_parent = None
    chosen_name = None
    for pref_ns in (1, 3, 0, 2):
        if pref_ns in names:
            chosen_parent, chosen_name = names[pref_ns]
            break

    return {
        "in_use": in_use,
        "is_dir": is_dir,
        "parent": chosen_parent,
        "name": chosen_name,
        "data_size": data_size,
        "data_resident": data_resident,
        "data_runs": data_runs,
    }


def diagnose_scenario_1(img, log=None):
    """Tự động phát hiện và suy luận 3 tham số Boot Sector bị hỏng theo Scenario 1:
    - Sectors per cluster (0x0D)
    - $MFT Starting Cluster LCN (0x30)
    - Clusters per MFT record (0x40)

    Không hardcode bất kỳ giá trị mẫu hay offset cụ thể nào.
    Trả về dict chứa đầy đủ tham số đã suy luận cùng các run của $MFT.
    """
    if log:
        log.buoc("Bắt đầu chẩn đoán Boot Sector bị sai", offset=0x00)

    # Đọc Bytes per sector từ BPB (trường 0x0B không bị làm sai)
    bytes_per_sec = img.u16(0x0B)
    if bytes_per_sec == 0 or bytes_per_sec > 4096 or bytes_per_sec % 512 != 0:
        bytes_per_sec = 512

    # 1. Quét tìm Bản ghi 0 của $MFT
    # Quét theo bước nhảy sector (512B) trên vùng đầu đĩa
    mft_offset = -1
    scan_limit = min(img.kich_thuoc, 128 * 1024 * 1024)  # 128 MB đầu
    for o in range(0, scan_limit, bytes_per_sec):
        if img.doc(o, 4) == b"FILE":
            raw_rec = img.doc(o, 1024)
            fixed_rec = apply_fixup(raw_rec, bytes_per_sec)
            if not fixed_rec:
                continue
            rec_info = parse_mft_record(fixed_rec)
            if rec_info and rec_info.get("name") == "$MFT":
                mft_offset = o
                break

    if mft_offset < 0:
        raise RuntimeError("Không thể tìm thấy Bản ghi 0 của $MFT trên ảnh đĩa")

    if log:
        log.quyet_dinh(f"Tìm thấy Bản ghi 0 của $MFT", offset=mft_offset)

    # 2. Suy ra MFT Record Size
    # Đo khoảng cách tới Record 1 ($MFTMirr)
    record_size = 1024
    if mft_offset + 1024 + 4 <= img.kich_thuoc and img.doc(mft_offset + 1024, 4) == b"FILE":
        record_size = 1024
    else:
        # Fallback từ allocated size trong header nếu cần
        alloc_sz = img.u32(mft_offset + 0x1C)
        if alloc_sz in (1024, 2048, 4096):
            record_size = alloc_sz

    # Giá trị byte có dấu tại trường 0x40:
    # Nếu record_size < cluster_size thì lưu c < 0 sao cho 2^|c| = record_size
    # 1024 = 2^10 => c = -10 (0xF6)
    rec_size_byte = -10 if record_size == 1024 else (record_size // 512)

    if log:
        log.quyet_dinh(
            f"Xác định kích thước bản ghi MFT: {record_size}B (trường 0x40 = {rec_size_byte:#x})"
        )

    # 3. Đọc Bản ghi 0 để giải mã Runlist của $DATA -> lấy mft_lcn
    rec0 = apply_fixup(img.doc(mft_offset, record_size), bytes_per_sec)
    rec0_info = parse_mft_record(rec0)
    if not rec0_info or not rec0_info.get("data_runs"):
        raise RuntimeError("Không đọc được Runlist của $MFT từ Bản ghi 0")

    mft_runs = rec0_info["data_runs"]
    mft_lcn = mft_runs[0][0]
    if mft_lcn is None or mft_lcn <= 0:
        raise RuntimeError(f"LCN của $MFT không hợp lệ: {mft_lcn}")

    if log:
        log.quyet_dinh(f"Suy ra $MFT LCN đúng từ Runlist: {mft_lcn}")

    # 4. Tính toán cluster_size và sectors_per_cluster
    cluster_size = mft_offset // mft_lcn
    sec_per_clus = cluster_size // bytes_per_sec

    if log:
        log.quyet_dinh(
            f"Tính toán: cluster_size = {cluster_size}B, SecPerClus (0x0D) = {sec_per_clus}"
        )

    total_sec = img.u64(0x28)

    return {
        "bytes_per_sec": bytes_per_sec,
        "sec_per_clus": sec_per_clus,
        "cluster_size": cluster_size,
        "mft_lcn": mft_lcn,
        "mft_offset": mft_offset,
        "record_size": record_size,
        "rec_size_byte": rec_size_byte,
        "mft_runs": mft_runs,
        "mft_real_size": rec0_info.get("data_size", 0),
        "total_sec": total_sec,
    }


def extract_all_files(img, params, log=None):
    """Trích xuất toàn bộ tập tin từ các bản ghi MFT theo tham số đã giải mã.
    Lần vết thư mục cha để xây dựng đường dẫn tương đối chuẩn.
    Trả về danh sách các dict: [{"path": "DATA/A12.JPG", "size": 123, "data": bytes}, ...]
    """
    cluster_size = params["cluster_size"]
    record_size = params["record_size"]
    bytes_per_sec = params["bytes_per_sec"]
    mft_runs = params["mft_runs"]
    mft_real_size = params["mft_real_size"]

    # Hàm đọc bản ghi thứ i của MFT qua chuỗi Runlist
    def read_record(rec_num):
        byte_pos = rec_num * record_size
        cur_pos = 0
        for lcn, run_len in mft_runs:
            run_bytes = run_len * cluster_size
            if cur_pos <= byte_pos < cur_pos + run_bytes:
                if lcn is None:
                    return None
                offset_in_run = byte_pos - cur_pos
                actual_offset = lcn * cluster_size + offset_in_run
                raw = img.doc(actual_offset, record_size)
                return apply_fixup(raw, bytes_per_sec)
            cur_pos += run_bytes
        return None

    total_records = mft_real_size // record_size
    records = {}

    for i in range(total_records):
        rec_bytes = read_record(i)
        if not rec_bytes:
            continue
        info = parse_mft_record(rec_bytes)
        if not info or not info["in_use"] or not info["name"]:
            continue
        records[i] = info

    # Xây dựng đường dẫn từ Thư mục gốc (Record 5)
    def get_path(r_id):
        parts = []
        curr = r_id
        visited = set()
        while curr != 5 and curr in records and curr not in visited:
            visited.add(curr)
            parts.append(records[curr]["name"])
            curr = records[curr]["parent"]
        return "/".join(reversed(parts))

    files = []
    for r_id, r_info in records.items():
        # Bỏ qua thư mục và siêu dữ liệu hệ thống (Record < 16 hoặc tên bắt đầu bằng $)
        if r_info["is_dir"] or r_id < 16 or r_info["name"].startswith("$"):
            continue

        file_path = get_path(r_id)
        file_size = r_info["data_size"] or 0

        # Trích xuất dữ liệu tập tin
        if r_info["data_resident"] is not None:
            content = r_info["data_resident"][:file_size]
        elif r_info["data_runs"] is not None:
            content = read_stream_data(img, r_info["data_runs"], cluster_size, file_size)
        else:
            content = b""

        files.append({
            "path": file_path,
            "size": file_size,
            "data": content,
        })

    files.sort(key=lambda x: x["path"])
    if log:
        log.quyet_dinh(f"Trích xuất thành công {len(files)} tập tin từ ảnh đĩa")

    return files
