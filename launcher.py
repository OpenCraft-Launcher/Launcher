import shutil
import subprocess
import uuid
from pathlib import Path

import minecraft_launcher_lib

DEFAULT_MC_DIR = Path(minecraft_launcher_lib.utils.get_minecraft_directory())


def _offline_uuid(username: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}"))



def _inject_skin(mc_dir: Path, username: str, skin_path: str):
    """Copy skin PNG into local texture cache so it shows in offline mode."""
    if not skin_path:
        return
    src = Path(skin_path)
    if not src.exists():
        return
    offline_id = str(uuid.uuid3(uuid.NAMESPACE_DNS, f"OfflinePlayer:{username}")).replace("-", "")
    dest_dir = mc_dir / "assets" / "skins"
    dest_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(src, dest_dir / f"{offline_id}.png")

def _ensure_installed(version_id: str, mc_dir: Path, cb=None):
    installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(mc_dir))]
    if version_id not in installed:
        if cb: cb(f"Downloading {version_id}…")
        callbacks = {
            "setStatus": lambda s: cb(s) if cb else None,
            "setProgress": lambda p: None,
            "setMax": lambda m: None,
        }
        minecraft_launcher_lib.install.install_minecraft_version(
            version_id, str(mc_dir), callback=callbacks
        )
        if cb: cb(f"{version_id} ready.")


def _install_fabric(mc_version: str, mc_dir: Path, cb=None):
    if cb: cb(f"Installing Fabric for {mc_version}…")
    minecraft_launcher_lib.fabric.install_fabric(mc_version, str(mc_dir))
    if cb: cb("Fabric installed.")


def _install_forge(mc_version: str, mc_dir: Path, cb=None):
    import requests, tempfile
    forge_versions = minecraft_launcher_lib.forge.list_forge_versions()
    target = next((v for v in forge_versions if v.startswith(mc_version)), None)
    if not target:
        if cb: cb(f"No Forge available for {mc_version}")
        return
    if cb: cb(f"Installing Forge {target}…")
    with tempfile.TemporaryDirectory() as tmp:
        installer = Path(tmp) / "forge-installer.jar"
        url = minecraft_launcher_lib.forge.find_forge_version(target)
        r = requests.get(url, stream=True, timeout=60)
        installer.write_bytes(r.content)
        subprocess.run(["java", "-jar", str(installer), "--installClient", str(mc_dir)], check=True)
    if cb: cb(f"Forge {target} installed.")


def launch(username: str, version: str, mod_loader: str, jvm_args: list,
           mc_dir: Path = None, skin_path: str = '', progress_cb=None, log_cb=None):
    if mc_dir is None:
        mc_dir = DEFAULT_MC_DIR
    mc_dir = Path(mc_dir)

    _ensure_installed(version, mc_dir, progress_cb)

    if mod_loader == "fabric":
        _install_fabric(version, mc_dir, progress_cb)
        installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(mc_dir))]
        version = next((v for v in installed if "fabric-loader" in v and version in v), version)
    elif mod_loader == "forge":
        _install_forge(version, mc_dir, progress_cb)
        installed = [v["id"] for v in minecraft_launcher_lib.utils.get_installed_versions(str(mc_dir))]
        version = next((v for v in installed if "forge" in v.lower() and version in v), version)

    _inject_skin(mc_dir, username, skin_path)

    options = {
        "username": username,
        "uuid": _offline_uuid(username),
        "token": "0",
        "jvmArguments": jvm_args,
    }

    cmd = minecraft_launcher_lib.command.get_minecraft_command(version, str(mc_dir), options)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if log_cb:
            for line in proc.stdout:
                log_cb(line.rstrip())
        proc.wait()
    except FileNotFoundError:
        raise RuntimeError("Java not found. Install from https://adoptium.net and add it to PATH.")
