from __future__ import annotations

import hashlib

from file_hash_utils import sha256_file


def test_sha256_file_streams_file_digest(tmp_path):
    payload_path = tmp_path / "payload.bin"
    payload = b"abc" + (b"x" * (1024 * 1024 + 7))
    payload_path.write_bytes(payload)

    assert sha256_file(payload_path) == hashlib.sha256(payload).hexdigest()
