from pathlib import Path

import pytest

from transfer_integrity import safe_upload_id, upload_part_path


def test_valid_upload_ids_are_accepted():
    assert safe_upload_id("abcdEFGH_1234-xyz") == "abcdEFGH_1234-xyz"


@pytest.mark.parametrize("value", [None, "", "short", "bad id spaces", "../escape123", "x" * 65])
def test_invalid_upload_ids_are_rejected(value):
    with pytest.raises(ValueError):
        safe_upload_id(value)


def test_same_filename_different_upload_ids_use_different_parts(tmp_path):
    first = upload_part_path(tmp_path, "upload_A123")
    second = upload_part_path(tmp_path, "upload_B123")
    assert first != second
    assert first.parent == Path(tmp_path)
    assert second.parent == Path(tmp_path)


def test_upload_part_path_cannot_escape_receive_directory(tmp_path):
    with pytest.raises(ValueError):
        upload_part_path(tmp_path, "../../escape")
