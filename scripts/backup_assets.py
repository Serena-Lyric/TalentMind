"""Verify a compact private backup; optionally restore into a new directory."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath


def safe_path(base, name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe path')
    relative = PurePosixPath(name)
    if relative.is_absolute() or PureWindowsPath(name).drive or '..' in relative.parts:
        raise ValueError('Unsafe path')
    path = base / name
    if not path.resolve().is_relative_to(base.resolve()):
        raise ValueError('Unsafe path')
    return path


def verify(backup):
    manifest = json.loads((backup / 'backup-manifest.json').read_text(encoding='utf-8'))
    if manifest['schema_version'] != 1:
        raise ValueError('Unsupported backup schema')
    artifacts = manifest['artifacts']
    names = set()
    for artifact in artifacts:
        path = safe_path(backup, artifact['path'])
        names.add(artifact['path'])
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != artifact['sha256'] or path.stat().st_size != artifact['bytes']:
            raise ValueError('Artifact checksum mismatch')
    if not {'private-assets.zip', 'private-files.json'} <= names:
        raise ValueError('Private asset artifacts missing from manifest')
    entries = json.loads((backup / 'private-files.json').read_text(encoding='utf-8'))
    paths = set()
    objects = {}
    for entry in entries:
        safe_path(backup, entry['path'])
        normalized = str(PurePosixPath(entry['path'])).casefold()
        if normalized in paths:
            raise ValueError('Duplicate restore path')
        paths.add(normalized)
        digest = entry['sha256']
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid object hash')
        if digest in objects and objects[digest] != entry['bytes']:
            raise ValueError('Inconsistent object size')
        objects[digest] = entry['bytes']
    with zipfile.ZipFile(backup / 'private-assets.zip') as archive:
        if len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('Duplicate archive members')
        if set(archive.namelist()) != {'objects/' + digest for digest in objects}:
            raise ValueError('Archive object list mismatch')
        for digest, size in objects.items():
            member = 'objects/' + digest
            with archive.open(member) as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != digest or archive.getinfo(member).file_size != size:
                raise ValueError('Private object checksum mismatch')
    return entries, len(artifacts), len(objects)


def restore(backup, target, entries):
    if target.exists():
        raise ValueError('Restore target already exists')
    destinations = [(safe_path(target, entry['path']), entry) for entry in entries]
    target.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(backup / 'private-assets.zip') as archive:
        for path, entry in destinations:
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open('objects/' + entry['sha256']) as source, path.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != entry['sha256']:
                raise ValueError('Restored file checksum mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backup', required=True, type=Path)
    parser.add_argument('--restore-to', type=Path, help='New, nonexistent destination directory')
    args = parser.parse_args()
    try:
        entries, artifacts, objects = verify(args.backup.resolve())
        if args.restore_to is not None:
            restore(args.backup.resolve(), args.restore_to.resolve(), entries)
        print(json.dumps({'artifacts': artifacts, 'private_files': len(entries), 'unique_objects': objects, 'restored': args.restore_to is not None}))
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        print('Backup verification/restore failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
