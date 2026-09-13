import zlib


def crc32_hex(data: bytes) -> str:
    """Return an 8-character CRC32 value for one upload chunk."""
    return f"{zlib.crc32(data) & 0xffffffff:08x}"


def crc32_update(value: int, data: bytes) -> int:
    """Update a running CRC32 value while a request body is being read."""
    return zlib.crc32(data, value)


def crc32_value_hex(value: int) -> str:
    return f"{value & 0xffffffff:08x}"
