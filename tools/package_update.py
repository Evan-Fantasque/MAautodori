"""Publish file-level updates from the actual Windows portable packages."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile


PREFIX = "MAautodori-win-x64-"
VERSION = re.compile(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?")
FILES = {"interface.json", "mxu.exe", "LICENSE", "README.md", "requirements.txt"}
DIRECTORIES = {"agent", "licenses", "maafw", "python", "resource", "share"}


def package_version(archive):
    version = archive.stem.removeprefix(PREFIX)
    if archive.name != f"{PREFIX}{version}.zip" or not VERSION.fullmatch(version):
        raise ValueError(f"Invalid portable archive name: {archive.name}")
    return version


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


def package_update(base, target, output):
    old_version, new_version = package_version(base), package_version(target)
    if old_version == new_version:
        raise ValueError("An update needs two different versions")
    with ZipFile(base) as before, ZipFile(target) as after:
        old_files, new_files = contents(before, old_version), contents(after, new_version)
        old_hashes, new_hashes = hashes(before, old_files), hashes(after, new_files)
        added = sorted(new_files.keys() - old_files.keys())
        deleted = sorted(old_files.keys() - new_files.keys())
        modified = sorted(name for name in new_files.keys() & old_files.keys() if old_hashes[name] != new_hashes[name])
        manifest = {
            "base_version": old_version, "target_version": new_version,
            "added": added, "deleted": deleted, "modified": modified,
            "base": old_hashes,
            "files": {name: new_hashes[name] for name in added + modified},
        }
        filename = f"{PREFIX}{old_version}-to-{new_version}.delta.zip"
        with TemporaryDirectory(dir=output) as temporary:
            delta = Path(temporary) / filename
            with ZipFile(delta, "w", ZIP_DEFLATED, compresslevel=4) as update:
                update.writestr("changes.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")))
                for name in added + modified:
                    with after.open(new_files[name]) as src, update.open(name, "w") as dest:
                        shutil.copyfileobj(src, dest)
            with ZipFile(delta) as update:
                if hashes(update, {name: name for name in manifest["files"]}) != manifest["files"]:
                    raise ValueError("Incremental archive failed verification")
            if delta.stat().st_size >= target.stat().st_size:
                print(f"Skipping {filename} because the full package is smaller")
                return
            destination = delta.replace(output / filename)
            print(f"{destination} ({destination.stat().st_size:,} bytes)")


def published_updates(repo, target, output):
    releases = json.loads(subprocess.check_output(
        ["gh", "api", f"repos/{repo}/releases?per_page=40"], encoding="utf-8",
    ))
    version = package_version(target)
    channels = set()
    with TemporaryDirectory() as temporary:
        for release in releases:
            tag = release["tag_name"]
            if release["draft"] or tag == version or not VERSION.fullmatch(tag):
                continue
            channel = release["prerelease"]
            if channel in channels:
                continue
            filename = f"{PREFIX}{tag}.zip"
            if not any(asset["name"] == filename and asset["state"] == "uploaded" for asset in release["assets"]):
                continue
            subprocess.run(
                ["gh", "release", "download", tag, "--repo", repo, "--pattern", filename, "--dir", temporary],
                check=True,
            )
            package_update(Path(temporary) / filename, target, output)
            channels.add(channel)
            if len(channels) == 2:
                break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", type=Path)
    source.add_argument("--repo")
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.base:
        package_update(args.base, args.target, args.output)
    else:
        published_updates(args.repo, args.target, args.output)
