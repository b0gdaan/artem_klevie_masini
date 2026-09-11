"""Hashing and atomic file writes.

Every file the pipeline produces goes through ``atomic_write_bytes``: the data is
written to a temporary file in the same directory, optionally validated, flushed
to disk and only then renamed over the target. A crash therefore never leaves a
half-written artefact under the final name.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

import pandas as pd


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def sha256_json(obj) -> str:
    return sha256_bytes(canonical_json(obj).encode("utf-8"))


def atomic_write_bytes(path: str | Path, data: bytes,
                       validate: Callable[[Path], None] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if validate is not None:
            validate(tmp)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return path


def atomic_write_text(path: str | Path, text: str, **kwargs) -> Path:
    return atomic_write_bytes(path, text.replace("\r\n", "\n").encode("utf-8"), **kwargs)


def write_json(path: str | Path, obj) -> Path:
    text = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n"
    return atomic_write_text(path, text)


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_csv(path: str | Path, frame: pd.DataFrame) -> Path:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n", float_format="%.12g")
    return atomic_write_text(path, buffer.getvalue())


def read_csv(path: str | Path, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, keep_default_na=True, **kwargs)


def tree_sha256(root: str | Path, exclude: tuple[str, ...] = ("SHA256SUMS",)) -> tuple[str, dict[str, str]]:
    """Hash every file under ``root``; the combined hash covers names and contents."""
    root = Path(root)
    files = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in exclude or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        files[rel] = sha256_file(path)
    listing = "".join(f"{sha}  {rel}\n" for rel, sha in files.items())
    return sha256_bytes(listing.encode("utf-8")), files


def format_sha256sums(files: dict[str, str]) -> str:
    return "".join(f"{sha}  {rel}\n" for rel, sha in sorted(files.items()))


def read_sha256sums(path: str | Path) -> dict[str, str]:
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            sha, rel = line.split("  ", 1)
            result[rel] = sha
    return result
