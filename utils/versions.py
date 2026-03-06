import requests

_cache = {}

MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_META_URL = "https://meta.fabricmc.net/v2/versions/game"


def get_versions() -> dict:
    if _cache:
        return _cache

    _cache["vanilla"] = _fetch_vanilla()
    _cache["fabric"] = _fetch_fabric()
    _cache["forge"] = _fetch_vanilla()  # same MC versions, Forge installs on top
    return _cache


def _fetch_vanilla() -> list:
    try:
        r = requests.get(MANIFEST_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [v["id"] for v in data["versions"] if v["type"] == "release"]
    except Exception:
        return ["1.21.1", "1.20.4", "1.20.1", "1.19.4", "1.18.2", "1.17.1", "1.16.5"]


def _fetch_fabric() -> list:
    try:
        r = requests.get(FABRIC_META_URL, timeout=10)
        r.raise_for_status()
        data = r.json()
        return [v["version"] for v in data if v.get("stable")]
    except Exception:
        return ["1.21.1", "1.20.4", "1.20.1", "1.19.4"]
