# 🎮 EmuVault — Emulator Aggregator

A self-updating static site that tracks emulator releases from GitHub and presents them in a categorized, searchable interface.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  GitHub Actions (runs every 6 hours)             │
│  ┌────────────────────────────────────────────┐  │
│  │  tracker.py                                │  │
│  │  • Checks GitHub Releases API              │  │
│  │  • Compares versions in emulators.json     │  │
│  │  • Updates JSON + feed if new release      │  │
│  │  • Commits changes back to repo            │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────┘
                       │ git push
                       ▼
┌──────────────────────────────────────────────────┐
│  GitHub Pages                                    │
│  ┌────────────────┐   ┌───────────────────────┐  │
│  │  index.html    │◄──│  emulators.json       │  │
│  │  (static site) │   │  (database)           │  │
│  └────────────────┘   └───────────────────────┘  │
└──────────────────────────────────────────────────┘
```

## Quick Start

### 1. Create a GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/emulator-aggregator.git
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo → **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Choose **main** branch, **/ (root)** folder
4. Click **Save**

Your site will be live at `https://YOUR_USERNAME.github.io/emulator-aggregator/`

### 3. Enable the Tracker

The GitHub Actions workflow at `.github/workflows/track-releases.yml` will automatically:
- Run every 6 hours
- Check all tracked emulators for new GitHub releases
- Update `emulators.json` if new versions are found
- Commit and push changes (which triggers a Pages rebuild)

You can also trigger it manually: **Actions** → **Track Emulator Releases** → **Run workflow**

## Project Structure

```
├── index.html                          # The website (single-file, no build step)
├── emulators.json                      # Emulator database (auto-updated)
├── scripts/
│   └── tracker.py                      # Release checker (Python, no dependencies)
├── .github/
│   └── workflows/
│       └── track-releases.yml          # Automation schedule
└── README.md
```

## Adding a New Emulator

Edit `emulators.json` and add an entry to the `emulators` array:

```json
{
  "id": "my-emulator",
  "name": "My Emulator",
  "category": "SNES",
  "description": "A great SNES emulator.",
  "latest_version": "1.0.0",
  "release_date": "2024-01-01",
  "website": "https://example.com",
  "github": "owner/repo",
  "download_url": "https://example.com/download",
  "icon": "🎮",
  "platforms": ["Windows", "Linux", "macOS"]
}
```

The tracker will automatically pick it up on the next run.

## Running the Tracker Locally

```bash
# Check all emulators
python scripts/tracker.py

# Dry run (no changes saved)
python scripts/tracker.py --dry-run

# Check a specific emulator
python scripts/tracker.py --emulator dolphin
```

Set `GITHUB_TOKEN` environment variable for higher API rate limits:

```bash
export GITHUB_TOKEN=ghp_your_token_here
python scripts/tracker.py
```

## Tracked Emulators

| Emulator     | Category        | GitHub Repo                              |
|-------------|-----------------|------------------------------------------|
| Mesen       | NES             | SourMesen/Mesen2                         |
| FCEUX       | NES             | TASEmulators/fceux                       |
| mGBA        | GBA             | mgba-emu/mgba                            |
| VBA-M       | GBA             | visualboyadvance-m/visualboyadvance-m    |
| MAME        | MAME            | mamedev/mame                             |
| Dolphin     | GameCube / Wii  | dolphin-emu/dolphin                      |
| PCSX2       | PlayStation     | PCSX2/pcsx2                              |
| DuckStation | PlayStation     | stenzek/duckstation                      |
| Snes9x      | SNES            | snes9xgit/snes9x                         |
| bsnes       | SNES            | bsnes-emu/bsnes                          |
| RetroArch   | Multi-System    | libretro/RetroArch                       |
| Ryujinx     | Nintendo Switch | ryujinx-mirror/ryujinx                   |
| PPSSPP      | PSP             | hrydgard/ppsspp                          |
| Cemu        | Wii U           | cemu-project/Cemu                        |
| Citra       | Nintendo 3DS    | PabloMK7/citra                           |
| DeSmuME     | Nintendo DS     | TASEmulators/desmume                     |
| Project64   | N64             | project64/project64                      |
| xemu        | Xbox            | xemu-project/xemu                        |

## License

MIT
