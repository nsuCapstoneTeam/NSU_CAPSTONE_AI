"""Portable ordering/framing for the existing MSCLAP source identity."""

from collections.abc import Iterable
import hashlib
from pathlib import Path, PurePath


def package_source_files(package_root: Path) -> list[Path]:
    """Keep the existing rglob/is_file scope, including file-symlink behavior."""
    return [path for path in package_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".yml", ".yaml"}]


def _relative_path_key(path: PurePath) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if path.anchor or not path.parts or ".." in path.parts:
        raise ValueError("source identity paths must be root-relative file paths")
    # Preserve the recorded Windows component ordering without host Path rules.
    # Original components break case-fold ties; their spelling is never hashed folded.
    return tuple(part.casefold() for part in path.parts), path.parts


def canonical_source_identity(
        relative_file_hashes: Iterable[tuple[PurePath, str]],
) -> tuple[str, dict[str, str]]:
    """Hash relative POSIX names and raw file digests in a host-independent order.

    File bytes/newlines, path spelling, UTF-8 encoding and NUL/LF framing remain
    unchanged. Only ordering is explicit: case-folded components, then original
    components. Absolute paths, host drive names and parent traversal are invalid.
    """
    digest = hashlib.sha256()
    source_hashes = {}
    for relative_path, file_sha256 in sorted(
            relative_file_hashes, key=lambda item: _relative_path_key(item[0])):
        relative = relative_path.as_posix()
        if relative in source_hashes:
            raise ValueError("duplicate source identity path")
        source_hashes[relative] = file_sha256
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(file_sha256))
        digest.update(b"\n")
    return digest.hexdigest(), source_hashes
