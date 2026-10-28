"""Restore nine byte-exact evidence files from bounded-size publication parts."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile


def checked(data: bytes, record: dict) -> bytes:
    if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
        raise ValueError(f"Length or SHA-256 mismatch: {record.get('path', 'archive')}")
    return data


def restore(root: Path) -> None:
    source = Path(__file__).resolve().parent
    manifest = json.loads((source / 'MANIFEST.json').read_text())
    payload = b''.join(checked((source / part['path']).read_bytes(), part)
                       for part in manifest['parts'])
    checked(payload, {'bytes': manifest['archive_bytes'],
                      'sha256': manifest['archive_sha256']})
    expected = {record['path']: record for record in manifest['members']}
    root = root.resolve()
    pending = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:xz') as archive:
        members = archive.getmembers()
        if len(members) != len(expected) or {m.name for m in members} != set(expected):
            raise ValueError('Archive member inventory mismatch')
        for member in members:
            path = PurePosixPath(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts:
                raise ValueError(f'Unsafe member: {member.name}')
            target = root.joinpath(*path.parts).resolve()
            if not target.is_relative_to(root):
                raise ValueError(f'Destination escapes root: {member.name}')
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f'Missing member bytes: {member.name}')
            data = checked(stream.read(), expected[member.name])
            if target.exists() and (not target.is_file() or target.read_bytes() != data):
                raise ValueError(f'Refusing to overwrite different file: {target}')
            pending.append((target, data))
    # Validate every member and destination before writing any evidence file.
    for target, data in pending:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
    print(f'Verified and restored {len(pending)} unchanged evidence files under {root}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[5],
                        help='Repository root, or an empty destination for verification')
    restore(parser.parse_args().root)
