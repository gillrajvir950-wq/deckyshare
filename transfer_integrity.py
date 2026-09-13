import zlib


def crc32_update(value: int, data: bytes) -> int:
    return zlib.crc32(data, value)


def crc32_value_hex(value: int) -> str:
    return f"{value & 0xffffffff:08x}"
