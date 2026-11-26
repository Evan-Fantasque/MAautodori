"""Index the exact bytes of a Windows portable ZIP for HTTP range updates."""

import argparse
import gzip
from hashlib import file_digest
import json
from pathlib import Path, PurePosixPath
import re
from struct import unpack
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


PREFIX = "MAautodori-win-x64-"
VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?")
FILES = {"interface.json", "mxu.exe", "LICENSE", "README.md", "requirements.txt"}
DIRECTORIES = {"agent", "licenses", "maafw", "python", "resource", "share"}
INSTALLED_MANIFEST = "share/MAautodori-update-files.json"


def write_installed_manifest(stage, version):
    manifest = stage / INSTALLED_MANIFEST
    if manifest.exists():
        raise ValueError(f"Reserved package file already exists: {INSTALLED_MANIFEST}")
    files = {}
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            with path.open("rb") as data:
                files[path.relative_to(stage).as_posix()] = file_digest(data, "sha256").hexdigest()
    manifest.parent.mkdir(exist_ok=True)
    manifest.write_text(json.dumps({"version": version, "files": files}, separators=(",", ":")), encoding="utf-8")


def contents(archive, version):
    prefix = f"{PREFIX}{version}/"
    files = {}
    names = set()
    for member in archive.infolist():
        if member.is_dir():
            continue
        name = member.filename.removeprefix(prefix)
        path = PurePosixPath(name)
        if (
            name == member.filename or path.as_posix() != name or path.is_absolute()
            or ".." in path.parts or "\\" in name or ":" in name
            or not (name in FILES or (len(path.parts) > 1 and path.parts[0] in DIRECTORIES))
            or name.casefold() in names
        ):
            raise ValueError(f"Invalid portable member: {member.filename}")
        names.add(name.casefold())
        files[name] = member
    if not FILES <= files.keys() or json.loads(archive.read(files["interface.json"]))["version"] != version:
        raise ValueError("Portable archive metadata does not match its name")
    return files


def hashes(archive, files):
    result = {}
    for name, member in files.items():
        with archive.open(member) as data:
            result[name] = file_digest(data, "sha256").hexdigest()
    return result


def write_update_index(target, output):
    version = target.stem.removeprefix(PREFIX)
    if target.name != f"{PREFIX}{version}.zip" or not VERSION.fullmatch(version):
        raise ValueError(f"Invalid portable archive name: {target.name}")
    with ZipFile(target) as archive, target.open("rb") as raw:
        members = contents(archive, version)
        digests = hashes(archive, members)
        installed = json.loads(archive.read(members[INSTALLED_MANIFEST]))
        if installed != {"version": version, "files": {k: v for k, v in digests.items() if k != INSTALLED_MANIFEST}}:
            raise ValueError("The installed file list does not match the portable ZIP")
        files = {}
        for name, member in members.items():
            raw.seek(member.header_offset)
            signature, name_length, extra_length = unpack("<4s22xHH", raw.read(30))
            if (
                signature != b"PK\x03\x04" or member.flag_bits & 1 or not member.compress_size
                or member.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
            ):
                raise ValueError(f"Unsupported ZIP member: {member.filename}")
            offset = member.header_offset + 30 + name_length + extra_length
            if offset + member.compress_size > archive.start_dir:
                raise ValueError(f"Invalid ZIP data range: {member.filename}")
            files[name] = {
                "offset": offset, "packed": member.compress_size, "size": member.file_size,
                "compression": member.compress_type, "sha256": digests[name],
            }
        raw.seek(0)
        index = {
            "format": 1, "version": version, "archive_size": target.stat().st_size,
            "archive_sha256": file_digest(raw, "sha256").hexdigest(), "files": files,
        }

    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"{PREFIX}{version}.update-index.json.gz"
    destination.write_bytes(gzip.compress(json.dumps(index, separators=(",", ":")).encode(), mtime=0))
    print(f"{destination} ({len(files):,} files, {destination.stat().st_size:,} bytes)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    write_update_index(args.target, args.output)
