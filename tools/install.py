from pathlib import Path

import shutil
import sys

try:
    import jsonc
except ModuleNotFoundError as e:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments\n"
        "Or add it to your project's requirements."
    ) from e

from configure import configure_ocr_model


working_dir = Path(__file__).parent.parent.resolve()
install_path = working_dir / Path("install")
version = len(sys.argv) > 1 and sys.argv[1] or "v0.0.1"

# the first parameter is self name
if sys.argv.__len__() < 4:
    print("Usage: python install.py <version> <os> <arch> [--release]")
    print("Example: python install.py v1.0.0 win x86_64")
    sys.exit(1)

os_name = sys.argv[2]
arch = sys.argv[3]


mxu_entries = {"win": "mxu.exe", "linux": "mxu", "macos": "mxu.app"}


def install_deps():
    sdk_dir = working_dir / "deps"
    sdk_bin = sdk_dir / "bin"
    if not sdk_bin.is_dir():
        raise FileNotFoundError('Extract the MaaFramework release into "deps" first.')

    if os_name not in (*mxu_entries, "android") or arch not in ("aarch64", "x86_64"):
        raise ValueError(f"Unsupported OS or architecture: {os_name} {arch}")

    licenses_dir = install_path / "licenses"
    agent_binaries = sdk_dir / "share" / "MaaAgentBinary"

    if os_name == "android":
        shutil.copytree(sdk_bin, install_path, dirs_exist_ok=True)
        shutil.copytree(agent_binaries, install_path / "MaaAgentBinary", dirs_exist_ok=True)
    else:
        mxu_dir = sdk_dir / "mxu"
        frontend = mxu_dir / mxu_entries[os_name]
        if not frontend.exists():
            raise FileNotFoundError(f"Extract the MXU release into {mxu_dir} first.")
        install_path.mkdir(parents=True, exist_ok=True)
        if frontend.is_dir():
            shutil.copytree(frontend, install_path / frontend.name, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(frontend, install_path)

        shutil.copytree(
            sdk_bin,
            install_path / "maafw",
            ignore=shutil.ignore_patterns("*.node", "*.pdb"),
            dirs_exist_ok=True,
        )
        shutil.copytree(
            agent_binaries,
            install_path / "maafw" / "MaaAgentBinary",
            dirs_exist_ok=True,
        )
        licenses_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mxu_dir / "LICENSE", licenses_dir / "MXU.txt")

    licenses_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(sdk_dir / "LICENSE.md", licenses_dir / "MaaFramework.md")

def install_resource():

    configure_ocr_model()

    shutil.copytree(
        working_dir / "assets" / "resource",
        install_path / "resource",
        dirs_exist_ok=True,
    )
    shutil.copy2(
        working_dir / "assets" / "interface.json",
        install_path,
    )

    with open(install_path / "interface.json", "r", encoding="utf-8") as f:
        interface = jsonc.load(f)

    if "--release" in sys.argv[4:] and interface["version"] != version:
        raise ValueError(f"Release tag {version} does not match assets/interface.json.")
    interface["version"] = version
    if os_name == "win":
        interface["agent"]["child_exec"] = "./.venv/Scripts/python.exe"
    elif os_name != "android":
        interface["agent"]["child_exec"] = "./.venv/bin/python"
    else:
        interface["agent"]["child_exec"] = "python"
    interface["agent"]["child_args"] = ["./agent/main.py"]

    with open(install_path / "interface.json", "w", encoding="utf-8") as f:
        jsonc.dump(interface, f, ensure_ascii=False, indent=4)


def install_chores():
    shutil.copy2(
        working_dir / "README.md",
        install_path,
    )
    shutil.copy2(
        working_dir / "LICENSE",
        install_path,
    )


def install_agent():
    shutil.copytree(
        working_dir / "agent",
        install_path / "agent",
        ignore=shutil.ignore_patterns("__pycache__", "cache", ".version"),
        dirs_exist_ok=True,
    )
    shutil.copy2(working_dir / "requirements.txt", install_path)
    minitouch_assets = working_dir / "deps" / "minitouch_EvATive7"
    if minitouch_assets.is_dir():
        shutil.copytree(
            minitouch_assets,
            install_path / "share" / "MinitouchEvATive7",
            dirs_exist_ok=True,
        )


if __name__ == "__main__":
    install_deps()
    install_resource()
    install_chores()
    install_agent()

    print(f"Install to {install_path} successfully.")
