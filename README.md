# ⛏ OpenCraft Launcher

First AI generated, open source, cracked minecraft launcher.

![Python](https://img.shields.io/badge/Python-3.11+-0078d4?style=flat-square&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078d4?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-0078d4?style=flat-square)

---

## ✨ Features

- **Offline / Cracked** — play without a Microsoft account, just pick a username
- **Version selector** — fetches the full release list from Mojang automatically
- **Mod loader support** — Easy way to install mod loaders
- **Custom skins** — import any PNG skin with a live in-app character previewv (Currently on beta)
- **RAM control** — slider capped at 75% of system RAM, Aikar's JVM flags pre-loaded
- **Fluent UI** — Simple Minimalist UI

---

## 🚀 Getting Started

### Prerequisites

- [Python 3.11+](https://python.org/downloads) — make sure to check **"Add to PATH"** during install
- [Java](https://adoptium.net) — required to actually run Minecraft, add to PATH as well

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/OpenCraft-Launcher/Launcher.git
cd mclauncher

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

---

## 📦 Building a .exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name OpenCraft main.py
```

Output: `dist/OpenCraft.exe`

> **Note:** The first launch of a `--onefile` build is a few seconds slower as it unpacks itself. Use `--onedir` for faster startup at the cost of a folder instead of a single file.

---

## 🗂 Project Structure

```
mclauncher/
├── main.py              # Entry point
├── launcher.py          # Core launch logic (version install, mod loaders, skin injection)
├── requirements.txt
├── gui/
│   ├── app.py           # Main window, tab bar, Play tab, Skins tab
│   └── __init__.py
├── utils/
│   ├── versions.py      # Fetches Vanilla / Fabric / Forge version lists
│   ├── jvm.py           # JVM args builder and RAM slider logic
│   └── __init__.py
└── skins/               # Imported skin PNGs (auto-created on first run)
```

---

## 🎨 Skins

1. Go to the **Skins** tab
2. Click **+ Add** and select any 64×64 or 64×32 PNG skin
3. Click the skin in the list to preview it
4. Click **✓ Use this skin** to set it as active
5. Launch — the skin is injected into the local texture cache at startup

> Skins work in offline mode only (what you see locally). Other players in a multiplayer session won't see your skin since there's no skin server.

---

## ⚙️ Requirements

| Package | Version |
|---|---|
| `minecraft-launcher-lib` | `>=6.0` |
| `requests` | latest |

---

## ❓ FAQ

**Do I need a Minecraft account?**  
No. OpenCraft is offline-first. Just pick any username and play.

**Does it work on Linux / macOS?**  
The core launcher logic works on any OS, the GUI will open on other platforms but may look different.

**Why is the first launch slow?**  
Minecraft needs to be downloaded the first time you launch a version. This is normal — subsequent launches are instant.

**Can I use mods?**  
Yes. Select Fabric or Forge as your mod loader when creating a version, then drop `.jar` mod files into your `.minecraft/mods` folder.

---

## ⚠️ Disclaimer

MClauncher is an independent open-source project and is **not affiliated with Mojang Studios or Microsoft**. Use it to play games you own. The authors take no responsibility for misuse.

---

## 📄 License

MIT — do whatever you want, just keep the credit.
