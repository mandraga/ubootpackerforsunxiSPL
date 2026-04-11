#!/usr/bin/env python3
import argparse
import struct
import sys

STAMP_VALUE = 0x5F0A6C39
CHECKSUM_OFFSET = 12
ALIGN_SIZE_OFFSET = 16
LENGTH_OFFSET = 20
UBOOT_LENGTH_OFFSET = 24
MAGIC_OFFSET = 4
MAGIC_SIZE = 8

def calculate_checksum(data: bytes, size: int) -> tuple[int, int]:
    """Calculate checksum with the same rule used by Sunxi SPL check_sum()."""
    if size % 4 != 0:
        raise ValueError("size must be a multiple of 4")
    if size > len(data):
        raise ValueError("size exceeds input length")

    buf = bytearray(data[:size])
    src_sum = struct.unpack_from("<I", buf, CHECKSUM_OFFSET)[0]
    struct.pack_into("<I", buf, CHECKSUM_OFFSET, STAMP_VALUE)

    count = size / 4
    pos = 0
    checksum = 0
    while count > 0:
        checksum = (checksum + struct.unpack_from("<I", buf, pos)[0]) & 0xFFFFFFFF
        pos += 4
        count -= 1
    return checksum, src_sum
    return src_sum, total

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify checksum of a Sunxi secondary SPL image"
    )
    parser.add_argument("image", help="Path to image (for example out.bin)")
    parser.add_argument(
        "--size",
        type=lambda x: int(x, 0),
        default=None,
        help="Checksum size in bytes (decimal or 0xHEX). Default: header length field.",
    )
    args = parser.parse_args()

    with open(args.image, "rb") as f:
        data = f.read()

    if len(data) < 32:
        print("ERROR: file too small", file=sys.stderr)
        return 2

    align_size = struct.unpack_from("<I", data, ALIGN_SIZE_OFFSET)[0]
    file_length = struct.unpack_from("<I", data, LENGTH_OFFSET)[0]
    uboot_length = struct.unpack_from("<I", data, UBOOT_LENGTH_OFFSET)[0]

    if len(data) % 4 != 0:
        raise ValueError("file size is not multiple of 4")

    magic = data[MAGIC_OFFSET:MAGIC_OFFSET + MAGIC_SIZE].rstrip(b"\x00")

    print(f"image: {args.image}")
    print(f"magic: {magic!r}")
    print(f"file_size: 0x{len(data):x} ({len(data)} bytes)")
    print(f"data_size: 0x{len(data):x} ({len(data)} bytes)")
    print(f"align_size: 0x{align_size:x} ({align_size} bytes)")
    print(f"file_length: 0x{file_length:x} ({file_length} bytes)")
    print(f"uboot_length: 0x{uboot_length:x} ({uboot_length} bytes)")

    src_sum, calc_sum = calculate_checksum(data, file_length)

    print(f"src_sum: 0x{src_sum:08x}")
    print(f"calc_sum: 0x{calc_sum:08x}")

    if src_sum == calc_sum:
        print("RESULT: CHECK_IS_CORRECT")
        return 0

    print("RESULT: CHECK_IS_WRONG")
    return 1


if __name__ == "__main__":
    sys.exit(main())