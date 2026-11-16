"""PHẦN LÀM BÀI CỦA NHÓM.

Quy tắc:
  * Tự giải mã mọi cấu trúc từ byte (dùng binio.AnhDia). Cấm thư viện phân tích hệ thống tập tin
    (pytsk3, dfvfs, pyfatfs, libntfs, libext2fs...) và cấm gọi công cụ ngoài (subprocess, os.system).
  * Không cố định offset / số cluster / giá trị của ảnh nhóm: chương trình sẽ chạy trên ảnh ẩn.
  * Không ghi lên ảnh đầu vào; muốn sửa thì img.sao_chep(...).
  * Ghi nhật ký mọi bước quan trọng: self.log.buoc(...), self.log.quyet_dinh(...).
  * Có thể tách mã ra nhiều tệp (vd. ntfs.py, runlist.py) và import vào đây.
"""
from ntfs_mbr import NTFS, find_ntfs, corrupt_mbr

class BaiLam:
    def __init__(self, log):
        self.log = log

    # ------------------------------------------------------------------ --info
    def info(self, img):
        """Đọc ảnh NGUYÊN VẸN, trả về dict:
            {"fs": "fat32|exfat|ntfs|ext4",
             "cluster_size": 4096,                # kích thước cluster/block (byte)
             ...                                  # các tham số khác tuỳ hệ thống (không chấm)
             "files": [{"path": "DATA/A12.JPG", "size": 123456}, ...]}   # chỉ tập tin, không thư mục
        """
        raise NotImplementedError("info")

    # ------------------------------------------------------------- tình huống
    def case1(self, img, out):
        """Tình huống 1 — sai tham số boot sector / superblock.
        Suy ra giá trị đúng, rồi trích xuất MỌI tập tin: out.luu("DATA/A12.JPG", data)."""
        raise NotImplementedError("case1")

    def case2(self, img, out):
        """Tình huống 2 — sai directory entry. Ghép đúng tên với dữ liệu, lưu các tập tin bị ảnh hưởng
        (lưu thêm cả tập tin không bị ảnh hưởng cũng được)."""
        raise NotImplementedError("case2")

    def case3(self, img, out):
        """Tình huống 3 — sai chuỗi vị trí. Ghép mảnh theo nội dung, lưu tập tin JPEG mục tiêu."""
        raise NotImplementedError("case3")

               
    def case_ext(self, img, out):
        """
        Bonus C: Lost MBR Partition Table Entry.

        1. Tìm NTFS volume khi MBR entry bị xóa.
        2. Xác thực NTFS Boot Sector và MFT.
        3. Đọc danh sách file.
        4. Khôi phục nội dung file vào thư mục kết quả.
        """

        self.log.buoc(
            "Bonus C: Bắt đầu tìm NTFS volume bị mất MBR entry",
            offset=0,
            gia_tri="MBR partition entry 0"
        )

        # Tự động tìm phân vùng NTFS
        volume = find_ntfs(img, self.log)

        self.log.quyet_dinh(
        "Đã xác định NTFS volume",
        offset=volume.offset,
        gia_tri={
            "cluster_size": volume.cluster,
            "mft_record_size": volume.record_size
            }
        )

        # Đọc danh sách file từ MFT
        files = volume.files()

        if not files:
            raise ValueError("Không tìm thấy tập tin cần khôi phục")

        recovered = 0

        for path, size, data_attr in files:
            # Đọc dữ liệu từ $DATA attribute
            data = volume.value(data_attr)

            if len(data) != size:
                raise ValueError(
                    f"Kích thước không khớp: {path}"
                )

            # Lưu file qua API của skeleton
            out.luu(path, data)

            self.log.buoc(
                "Đã khôi phục tập tin",
                offset=volume.offset,
                gia_tri={
                    "path": path,
                    "size": size
                }
            )

            recovered += 1

        self.log.quyet_dinh(
            "Bonus C: Hoàn thành khôi phục",
            gia_tri={
                "so_file": recovered
            }
        )

    # --------------------------------------------------------------- cộng điểm
    def repair(self, img, case, anh_moi):
        """--repair: sửa trên BẢN SAO và ghi ra anh_moi.
            ban_sua = img.sao_chep(anh_moi)
            ban_sua.ghi_u16(..., ...)
            ban_sua.dong()
        """
        raise NotImplementedError("repair")

    def corrupt(self, img, dac_ta, anh_hong):
        """
        Bonus C: Gây lỗi mất MBR partition entry 0.
        Chỉ sửa trên bản sao ảnh đĩa.
        """
        self.log.buoc(
            "Bonus C: Bắt đầu gây lỗi MBR",
            offset=0x1BE,
            gia_tri=dac_ta
        )

        return corrupt_mbr(
            img,
            dac_ta,
            anh_hong,
            self.log
        )
