import struct
import sys
import subprocess

# Constants
CHECKSUM_STAMP_VALUE = 0x5F0A6C39
STAMP_VALUE = 0x4A000000
MAGIC = b"uboot"
VERSION = b"1.1.0\x00\x00\x00"
PLATFORM = b"1.0.0\x00\x00\x00"
ALIGN_SIZE = 0x4000  # 16KB
# Offset of boot_head.check_sum in uboot_file_head.
CHECKSUM_OFFSET = 12

def calculate_checksum(mem_base: bytes | bytearray, size: int) -> int: 
    if size % 4 != 0:
        raise ValueError("size must be a multiple of 4 bytes")
    if size > len(mem_base):
        raise ValueError("size exceeds buffer length")
    # Need mutable buffer because C code writes/restores check_sum field
    buf = bytearray(mem_base)
    count = size >> 2
    pos = 0
    checksum = 0
    # while(count-- > 0) sum += *buf++
    while count > 0:
        checksum = (checksum + struct.unpack_from("<I", buf, pos)[0]) & 0xFFFFFFFF
        pos += 4
        count -= 1
    return checksum

def embed_uboot(uboot_file, output_file):
    """Embed u-boot.bin in spare_boot_ctrl_head format."""
    
    # Read u-boot binary
    with open(uboot_file, 'rb') as f:
        uboot_data = f.read()
    
    uboot_length = len(uboot_data)
    
    # Pad uboot_data to align_size multiple
    padded_length = ((uboot_length + ALIGN_SIZE - 1) // ALIGN_SIZE) * ALIGN_SIZE
    uboot_data += b'\x00' * (padded_length - uboot_length)
    
    # Create header (64 bytes)
    header = struct.pack('<I', 0xEA00013E)  # jump_instruction
    header += MAGIC + b'\x00' * (8 - len(MAGIC))  # magic[8]
    header += struct.pack('<I', CHECKSUM_STAMP_VALUE)  # check_sum (placeholder)
    header += struct.pack('<I', ALIGN_SIZE)  # align_size
    header += struct.pack('<I', padded_length)  # length
    header += struct.pack('<I', uboot_length)  # uboot_length
    header += VERSION  # version[8]
    header += PLATFORM  # platform[8]
    header += struct.pack('<i', STAMP_VALUE)  # reserved[1]
    
    # Create spare_boot_data_head (512 bytes)
    spare_data = bytearray(1232)
    # dram_para[32] - all zeros (already initialized)
    # run_clock (offset 0x80): 1008 MHz
    struct.pack_into('<I', spare_data, 0x80, 0x3F0)
    # run_core_vol (offset 0x84): 1200 mV
    struct.pack_into('<I', spare_data, 0x84, 0x4B0)
    # uart_port (offset 0x88): UART0
    struct.pack_into('<I', spare_data, 0x88, 0)
    # uart_gpio[0] (offset 0x8C)
    struct.pack_into('BBBBBBBB', spare_data, 0x8C, 6, 2, 3, 1, 0xFF, 0xFF, 0, 0)
    # uart_gpio[1] (offset 0x94)
    struct.pack_into('BBBBBBBB', spare_data, 0x94, 6, 4, 3, 1, 0xFF, 0xFF, 0, 0)
    # twi_port (offset 0x9C): TWI0
    struct.pack_into('<I', spare_data, 0x9C, 0)
    # twi_gpio[0] (offset 0xA0)
    struct.pack_into('BBBBBBBB', spare_data, 0xA0, 8, 2, 2, 0xFF, 0xFF, 0xFF, 0, 0)
    # twi_gpio[1] (offset 0xA8)
    struct.pack_into('BBBBBBBB', spare_data, 0xA8, 8, 3, 2, 0xFF, 0xFF, 0xFF, 0, 0)
    # work_mode (offset 0xB0): 0
    struct.pack_into('<I', spare_data, 0xB0, 0)
    # storage_type (offset 0xB4): NAND
    struct.pack_into('<I', spare_data, 0xB4, 0)
    # Reserved field (offset 0x3B0): 0xFFFFFFFFFFFFFFFF
    struct.pack_into('<Q', spare_data, 0x3B8, 0xFFFFFFFFFFFFFFFF)

    header += bytes(spare_data)
    
    # Combine header and uboot
    combined = header + uboot_data
    
    # Calculate checksum
    checksum = calculate_checksum(combined, len(combined))
    
    # Update checksum in header
    combined_with_checksum = bytearray(combined)
    # Store the checksum field instead of the stamp
    struct.pack_into('<I', combined_with_checksum, CHECKSUM_OFFSET, checksum)
    
    # Write output
    with open(output_file, 'wb') as f:
        f.write(combined_with_checksum)

    print(f"Successfully embedded u-boot.bin into {output_file}")
    print(f"U-Boot length: {uboot_length} bytes")
    print(f"Checksum: 0x{checksum:08x}")


def warn_if_unshifted_entry_point(uboot_binary_path: str) -> None:
    """Warn if the ELF entry point is not shifted by 0x500."""
    try:
        result = subprocess.run(
            ['readelf', '-h', uboot_binary_path],
            capture_output=True,
            text=True,
            check=False
        )
        #print(result.stdout)
        entry_line = next((line for line in result.stdout.splitlines() if 'Entry point' in line), '')
        if entry_line and '500' not in entry_line:
            print("Warning: u-boot entry point is not shifted at 0x500.\nYou may brick your board with that.\nU-boot must be at 0x4a000500 in order to begin after the sunxi header. Use CONFIG_TEXT_BASE=0x4a000500 in your defconfig.")
            sys.exit(0)
        else:
            print("Entry point looks correct (shifted at 0x500).")
    except FileNotFoundError:
        pass  # readelf not available

if __name__ == "__main__":
    if len(sys.argv) != 4:
            print("Tool to insert a mainline u-boot-dtb.bin into a legacy Sunxi second stage bootloader image.")
            print("Usage: python sunxisecondstagetool.py <u-boot> <u-boot-dtb.bin> <output.bin>")
            print("<u-boot> is only here to make sure that the entry point is correct, the actual u-boot binary is read from <u-boot-dtb.bin> and embedded in the output file.")
            sys.exit(0)
    # Check u-boot entry point with the provided input binary.
    warn_if_unshifted_entry_point(sys.argv[1])
    
    embed_uboot(sys.argv[1], sys.argv[2])