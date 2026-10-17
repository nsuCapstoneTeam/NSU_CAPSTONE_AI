"""Shared safe publication primitives for calibration manifest writers."""

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path


class ConcurrentManifestUpdateError(ValueError):
    """A manifest changed after a writer captured its input snapshot."""


def bytes_sha256(value):
    return hashlib.sha256(value).hexdigest()


@contextmanager
def exclusive_manifest_update(manifest_path, expected_sha256):
    """Serialize repository writers, then reject a stale manifest snapshot.

    The lock is acquired with O_EXCL, which is atomic on supported Windows and
    POSIX filesystems. A leftover lock after a process crash blocks writers
    safely and must be inspected rather than silently discarded.
    """
    manifest_path = Path(manifest_path)
    lock_path = manifest_path.with_name(f'.{manifest_path.name}.write.lock')
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ConcurrentManifestUpdateError(
            f'another calibration manifest writer holds {lock_path}; retry after it finishes'
        ) from exc

    try:
        with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
            stream.write(f'pid={os.getpid()}\n')
            stream.flush()
            os.fsync(stream.fileno())
        current = manifest_path.read_bytes()
        if bytes_sha256(current) != expected_sha256:
            raise ConcurrentManifestUpdateError(
                'manifest changed since this operation started; refusing stale publish'
            )
        yield current
    finally:
        lock_path.unlink(missing_ok=True)
