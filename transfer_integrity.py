import zlib
from pathlib import Path


def crc32_update(value: int, data: bytes) -> int:
    return zlib.crc32(data, value)


def crc32_value_hex(value: int) -> str:
    return f"{value & 0xffffffff:08x}"


def resume_offset(part_path) -> int:
    path = Path(part_path)
    return path.stat().st_size if path.exists() else 0


def rollback_partial(part_path, offset: int) -> int:
    path = Path(part_path)
    safe_offset = max(0, int(offset))
    with path.open("r+b") as handle:
        handle.truncate(safe_offset)
    return safe_offset


def remove_partial(part_path) -> bool:
    path = Path(part_path)
    if not path.exists():
        return False
    path.unlink()
    return True
