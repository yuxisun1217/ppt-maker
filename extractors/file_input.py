"""Shared helper: let extractors accept either file bytes or a local path.

Web flow passes uploaded bytes; desktop flow keeps passing local paths.
Internal code always works on a real path, so bytes are materialized to a
temp file for the duration of the call.
"""
import os
import shutil
import tempfile
from contextlib import contextmanager


def _is_bytes_like(data):
    return isinstance(data, (bytes, bytearray))


@contextmanager
def materialize_file(data, suffix=''):
    """Yield a real local path for `data`.

    - str/Path: yielded as-is (desktop keeps passing local paths)
    - bytes: written to a temp file, deleted on exit (web uploads)
    """
    if isinstance(data, (str, os.PathLike)):
        yield str(data)
        return

    if not _is_bytes_like(data):
        raise TypeError(f'不支持的文件输入类型: {type(data).__name__}（应为 bytes 或本地路径）')

    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    try:
        with open(tmp.name, 'wb') as f:
            f.write(bytes(data))
        yield tmp.name
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
