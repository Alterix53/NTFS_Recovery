"""Đọc NTFS cơ bản và tìm volume khi mất MBR entry 0.

Chỉ dùng thư viện chuẩn. Không hỗ trợ compression, encryption hay ATTRIBUTE_LIST.
Các offset NTFS đều tính tương đối với đầu volume.
"""


def so(b, o, n):
    if o < 0 or o + n > len(b):
        raise ValueError('Trường nằm ngoài cấu trúc NTFS')
    return int.from_bytes(b[o:o + n], 'little')


class NTFS:
    def __init__(self, img, offset, log):
        self.img, self.offset, self.log = img, offset, log
        b = img.doc(offset, 512)
        if b[3:11] != b'NTFS    ' or b[510:512] != b'\x55\xaa':
            raise ValueError('Không phải boot sector NTFS')
        self.sector = so(b, 11, 2)
        spc = b[13]
        if self.sector not in (512, 1024, 2048, 4096) or spc not in (1, 2, 4, 8, 16, 32, 64, 128):
            raise ValueError('Kích thước sector/cluster không hợp lệ')
        self.cluster = self.sector * spc
        self.total = so(b, 40, 8) * self.sector
        if self.total < self.cluster or offset + self.total > img.kich_thuoc:
            raise ValueError('Volume vượt kích thước ảnh')
        code = int.from_bytes(b[64:65], 'little', signed=True)
        self.record_size = (1 << -code) if -16 <= code < 0 else code * self.cluster
        if not 512 <= self.record_size <= 65536 or self.record_size % self.sector:
            raise ValueError('Kích thước MFT record không hợp lệ')
        mft = so(b, 48, 8) * self.cluster
        r = self.fixup(self.read(mft, self.record_size))
        data = [a for a in self.attributes(r) if so(a, 0, 4) == 0x80 and a[9] == 0]
        if len(data) != 1 or not data[0][8]:
            raise ValueError('$MFT không có DATA non-resident duy nhất')
        self.mft_attr = data[0]
        self.mft_size = so(data[0], 48, 8)
        self.mft_runs = self.runlist(data[0])
        if not self.mft_size or self.mft_size > self.total or self.mft_size % self.record_size:
            raise ValueError('Kích thước $MFT không hợp lệ')
        if sum(n for _, n in self.mft_runs) * self.cluster < self.mft_size:
            raise ValueError('Runlist $MFT thiếu dữ liệu')

    def read(self, off, n):
        if off < 0 or n < 0 or off + n > self.total:
            raise ValueError('Đọc vượt volume NTFS')
        return self.img.doc(self.offset + off, n)

    def fixup(self, raw):
        r = bytearray(raw)
        if r[:4] != b'FILE':
            raise ValueError('MFT record thiếu chữ ký FILE')
        o, count = so(r, 4, 2), so(r, 6, 2)
        if count != len(r) // self.sector + 1 or o < 8 or o + count * 2 > len(r):
            raise ValueError('Update Sequence Array không hợp lệ')
        usn = r[o:o + 2]
        for i in range(1, count):
            end = i * self.sector - 2
            if r[end:end + 2] != usn:
                raise ValueError('MFT record sai fixup')
            r[end:end + 2] = r[o + i * 2:o + i * 2 + 2]
        return bytes(r)

    def attributes(self, r):
        p, used = so(r, 20, 2), so(r, 24, 4)
        if not 24 <= p < used <= len(r):
            raise ValueError('Biên attribute không hợp lệ')
        while p + 4 <= used:
            typ = so(r, p, 4)
            if typ == 0xffffffff:
                return
            size = so(r, p + 4, 4)
            if size < 24 or size % 8 or p + size > used:
                raise ValueError('Độ dài attribute không hợp lệ')
            a = r[p:p + size]
            if typ == 0x20:
                raise ValueError('Chưa hỗ trợ ATTRIBUTE_LIST')
            yield a
            p += size
        raise ValueError('Thiếu dấu kết thúc attribute')

    def runlist(self, a):
        if len(a) < 64 or so(a, 32, 2) & 0x4001:
            raise ValueError('Không hỗ trợ DATA nén/mã hóa')
        if so(a, 16, 8) != 0:
            raise ValueError('Chưa hỗ trợ DATA nhiều extent attribute')
        p, lcn, runs = so(a, 32 - 0, 2), 0, []
        # MappingPairsOffset tại 0x20; AttributeFlags tại 0x0C.
        if so(a, 12, 2) & 0x4001:
            raise ValueError('Không hỗ trợ DATA nén/mã hóa')
        if p < 64 or p >= len(a):
            raise ValueError('Offset runlist không hợp lệ')
        while p < len(a):
            head = a[p]
            p += 1
            if head == 0:
                return runs
            n, d = head & 15, head >> 4
            if not 1 <= n <= 8 or d > 8 or p + n + d > len(a):
                raise ValueError('Runlist không hợp lệ')
            count = so(a, p, n)
            p += n
            if count == 0:
                raise ValueError('Run rỗng')
            if d:
                lcn += int.from_bytes(a[p:p + d], 'little', signed=True)
                if lcn < 0 or (lcn + count) * self.cluster > self.total:
                    raise ValueError('Run vượt volume')
                runs.append((lcn, count))
            else:
                runs.append((None, count))
            p += d
        raise ValueError('Runlist thiếu byte kết thúc')

    def stream(self, runs, off, n):
        result = bytearray()
        for lcn, count in runs:
            length = count * self.cluster
            if off >= length:
                off -= length
                continue
            take = min(n, length - off)
            result.extend(bytes(take) if lcn is None else self.read(lcn * self.cluster + off, take))
            n -= take
            off = 0
            if n == 0:
                return bytes(result)
        raise ValueError('Runlist không đủ dữ liệu')

    def value(self, a):
        if not a[8]:
            n, o = so(a, 16, 4), so(a, 20, 2)
            if o < 24 or o + n > len(a):
                raise ValueError('Resident value vượt attribute')
            return a[o:o + n]
        size, initialized = so(a, 48, 8), so(a, 56, 8)
        if size > self.total or initialized > size:
            raise ValueError('Kích thước DATA không hợp lệ')
        return self.stream(self.runlist(a), 0, initialized) + bytes(size - initialized) if initialized else bytes(size)

    def files(self):
        records = {}
        for index in range(self.mft_size // self.record_size):
            raw = self.stream(self.mft_runs, index * self.record_size, self.record_size)
            if raw[:4] != b'FILE' or not so(raw, 22, 2) & 1:
                continue
            r = self.fixup(raw)
            if so(r, 32, 8):
                continue
            names, data = [], None
            for a in self.attributes(r):
                typ = so(a, 0, 4)
                if typ == 0x30:
                    v = self.value(a)
                    if len(v) < 66 or 66 + v[64] * 2 > len(v):
                        raise ValueError('$FILE_NAME không hợp lệ')
                    name = v[66:66 + v[64] * 2].decode('utf-16le')
                    if not name or name in ('.', '..') and index != 5 or any(c in name for c in '/\\\x00'):
                        raise ValueError('Tên file không hợp lệ')
                    names.append((v[65] == 2, name, so(v, 0, 6), so(v, 6, 2)))
                elif typ == 0x80 and a[9] == 0:
                    if data is not None:
                        raise ValueError('Nhiều DATA attribute chưa được hỗ trợ')
                    data = a
            if names:
                records[index] = (sorted(names)[0], bool(so(r, 22, 2) & 2), data, so(r, 16, 2))

        def path(index, seen):
            if index == 5:
                return ''
            if index in seen or index not in records:
                raise ValueError('Parent MFT thiếu hoặc tạo vòng lặp')
            (_, name, parent, seq), _, _, _ = records[index]
            if parent not in records or records[parent][3] != seq or not records[parent][1]:
                raise ValueError('Parent reference không hợp lệ')
            prefix = path(parent, seen | {index})
            return prefix + '/' + name if prefix else name

        result = []
        for index, (name, directory, data, _) in records.items():
            if index < 16 or directory or data is None:
                continue
            p = path(index, set())
            if p.split('/')[0].startswith('$'):
                continue
            size = so(data, 48, 8) if data[8] else so(data, 16, 4)
            result.append((p, size, data))
        return sorted(result)


def find_ntfs(img, log):
    """Quét chữ ký nhanh bằng mmap; xác nhận boot sector và MFT, không tin mỗi OEM ID."""
    found, start = [], 0
    while True:
        hit = img.tim(b'NTFS    ', start)
        if hit < 0:
            break
        start = hit + 1
        offset = hit - 3
        if offset < 0 or offset % 512:
            continue
        try:
            volume = NTFS(img, offset, log)
        except ValueError:
            continue
        log.buoc('Ứng viên NTFS đã xác nhận bằng boot sector và MFT', offset=offset,
                 gia_tri={'cluster_size': volume.cluster, 'record_size': volume.record_size})
        found.append(volume)
    if len(found) != 1:
        raise ValueError(f'Cần đúng một volume NTFS hợp lệ, tìm thấy {len(found)}')
    volume = found[0]
    log.quyet_dinh('Chọn đầu volume NTFS', offset=volume.offset,
                  lba_512=volume.offset // 512)
    return volume


def corrupt_mbr(img, spec, target, log):
    if spec != {'tinh_huong': 'ext-mbr', 'partition_index': 0}:
        raise ValueError('Đặc tả cần tinh_huong=ext-mbr và partition_index=0')
    if img.doc(510, 2) != b'\x55\xaa' or img.doc(3, 8) == b'NTFS    ':
        raise ValueError('Cần ảnh toàn đĩa có MBR, không phải ảnh volume')
    entry = img.doc(0x1be, 16)
    start, count = so(entry, 8, 4), so(entry, 12, 4)
    if entry[0] not in (0, 0x80) or entry[4] != 7 or not start or not count:
        raise ValueError('Entry MBR đầu không phải phân vùng NTFS hợp lệ')
    if (start + count) * 512 > img.kich_thuoc:
        raise ValueError('Phân vùng vượt ảnh')
    volume = NTFS(img, start * 512, log)
    if volume.total > count * 512:
        raise ValueError('Volume vượt phân vùng MBR')
    with img.sao_chep(target) as copy:
        copy.ghi(0x1be, bytes(16))
    log.buoc('Xóa entry MBR đầu trên bản sao', offset=0x1be, gia_tri=entry.hex())
    return [{'offset': 0x1be, 'length': 16, 'cau_truc': 'MBR partition table entry 0'}]
