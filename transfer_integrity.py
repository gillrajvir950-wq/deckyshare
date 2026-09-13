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


def parse_nonnegative_int(value, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid {field}")
    if parsed < 0:
        raise ValueError(f"Invalid {field}")
    return parsed


def validate_upload_window(offset: int, total: int, length: int, current: int) -> None:
    offset = parse_nonnegative_int(offset, "offset")
    total = parse_nonnegative_int(total, "total")
    length = parse_nonnegative_int(length, "length")
    current = parse_nonnegative_int(current, "current")

    if offset != current:
        raise ValueError("Resume offset mismatch")
    if current > total:
        raise ValueError("Partial file exceeds declared total")
    if length > total - current:
        raise ValueError("Chunk exceeds declared total")
    if total == 0 and (offset != 0 or length != 0 or current != 0):
        raise ValueError("Invalid zero-byte upload")


def create_empty_file(path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=False)
    return target
