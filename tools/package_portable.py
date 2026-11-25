"""Turn a Windows x64 install tree into a portable release ZIP."""

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from zipfile import ZIP_DEFLATED, ZipFile
import argparse
import json
import re
import shutil
import subprocess
import sys
import sysconfig


PYTHON_VERSION = "3.14.4"
PYTHON_ARCHIVE = f"python-{PYTHON_VERSION}-embed-amd64.zip"
PYTHON_SHA256 = "cda80a9b1e75c0f1b4f9872ca1b417f0d19bce32facc811aea9180e70fad5fb9"

README = """# MAautodori Windows x64 便携包

完整解压 ZIP，双击 `mxu.exe`。包内已包含 Python、Agent 依赖、OCR 和触控组件。
请自行安装 MuMu 和游戏，先在游戏中登录，再在 MXU 选择对应的 MuMu 设备和「简中服」。
若系统缺少 Edge WebView2 或 Visual C++ x64 运行库，请从微软安装。

一键每日的配置步骤见[项目说明](https://github.com/Evan-Fantasque/MAautodori#从-mumu-启动到单人演出准备)。
打歌会自动下载并解析简中服 BMS。手动谱面放在 `mxu.exe` 同级的 `charts/`，例如 `charts/792-expert.bms`。详见[本地谱面](https://github.com/Evan-Fantasque/MAautodori#本地谱面)。

本项目为第三方工具。使用本工具产生的后果由使用者自行承担。
"""

SMOKE_TEST = """
import json
from pathlib import Path
import subprocess
import sys

import cv2
from maa.agent_client import AgentClient
from maa.resource import Resource
from maa.toolkit import Toolkit

root = Path.cwd().resolve()
assert all(Path(p).resolve().is_relative_to(root) for p in sys.path)
assert Toolkit.init_option(root)
resource = Resource()
assert resource.post_bundle(root / "resource").wait().succeeded
interface = json.loads((root / "interface.json").read_text(encoding="utf-8"))
agent = interface["agent"]
client = AgentClient()
assert client.bind(resource) and client.set_timeout(20000)
with subprocess.Popen([agent["child_exec"], *agent["child_args"], client.identifier]) as process:
    try:
        assert client.connect() and client.alive, "Packaged Agent failed to connect"
        assert (root / "agent/deploy/.version").read_text() == interface["version"]
    finally:
        if client.connected:
            client.disconnect()
        if process.poll() is None:
            process.terminate()
print("Packaged Python, resource loading and Agent handshake passed.")
"""


def install_python(stage, scratch):
    archive = scratch / PYTHON_ARCHIVE
    url = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_ARCHIVE}"
    with urlopen(url, timeout=60) as download, archive.open("wb") as output:
        shutil.copyfileobj(download, output)
    if sha256(archive.read_bytes()).hexdigest() != PYTHON_SHA256:
        raise ValueError("Embedded Python archive checksum mismatch.")

    runtime = stage / "python"
    with ZipFile(archive) as payload:
        for member in payload.namelist():
            if not member.lower().startswith("vcruntime"):
                payload.extract(member, runtime)

    python_tag = f"python{sys.version_info.major}{sys.version_info.minor}"
    (runtime / f"{python_tag}._pth").write_text(
        f"{python_tag}.zip\n.\nLib/site-packages\n", encoding="ascii"
    )
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
            "--no-compile", "--target", str(runtime / "Lib/site-packages"),
            "-r", str(stage / "requirements.txt"),
        ],
        check=True,
    )


def package_portable(install, output_dir):
    if sysconfig.get_platform() != "win-amd64" or sys.version.split()[0] != PYTHON_VERSION:
        raise RuntimeError(f"Use Windows x64 Python {PYTHON_VERSION} to build this package.")

    interface = json.loads((install / "interface.json").read_text(encoding="utf-8"))
    version = interface["version"]
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?", version):
        raise ValueError(f"Invalid package version: {version}")
    name = f"MAautodori-win-x64-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="portable-", dir=output_dir) as temporary:
        scratch = Path(temporary)
        stage = scratch / name
        stage.mkdir()
        for directory in ("agent", "maafw", "resource", "licenses", "share"):
            source = install / directory
            if directory == "share" and not source.exists():
                continue
            shutil.copytree(
                source, stage / directory,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".version", "debug", "cache"),
            )
        for filename in ("mxu.exe", "LICENSE", "requirements.txt"):
            shutil.copy2(install / filename, stage / filename)

        install_python(stage, scratch)
        interface["agent"]["child_exec"] = "./python/python.exe"
        (stage / "interface.json").write_text(
            json.dumps(interface, ensure_ascii=False, indent=4) + "\n", encoding="utf-8"
        )
        (stage / "README.md").write_text(README, encoding="utf-8")

        archive = scratch / f"{name}.zip"
        with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=4) as bundle:
            for file in sorted(stage.rglob("*")):
                if file.is_file():
                    bundle.write(file, Path(name) / file.relative_to(stage))

        # Run the shipped Agent after archiving so its logs stay out of the ZIP.
        subprocess.run(
            [str(stage / "python/python.exe"), "-B", "-c", SMOKE_TEST],
            cwd=stage,
            check=True,
            timeout=90,
        )
        target = output_dir / archive.name
        archive.replace(target)
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", type=Path, default=Path("install"))
    parser.add_argument("--output-dir", type=Path, default=Path("build/portable"))
    args = parser.parse_args()
    package_portable(args.install.resolve(), args.output_dir.resolve())
