#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone

# FIXED: Point to the root directory where index.html expects it
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "emulators.json")
GITHUB_API = "https://api.github.com"

def load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(db):
    db["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
    print(f"✅ Database saved — {DB_PATH}")

def github_get(endpoint):
    url = f"{GITHUB_API}{endpoint}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "EmuHub-Tracker/1.0")

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"token {token}")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️  GitHub API error {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"  ⚠️  Network error: {e.reason}")
        return None

def check_emulator(emu):
    repo = emu.get("github")
    if not repo:
        return None

    print(f"  Checking {emu['name']} ({repo})...", end=" ")
    data = github_get(f"/repos/{repo}/releases/latest")

    if not data or "tag_name" not in data:
        tags = github_get(f"/repos/{repo}/tags")
        if tags and len(tags) > 0:
            new_version = tags[0]["name"].lstrip("vV")
            if new_version != emu["latest_version"]:
                emu["latest_version"] = new_version
                emu["release_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                print(f"🆕 tag {new_version}")
                return emu
            print("(no change)")
            return None
        print("no releases found")
        return None

    new_version = data["tag_name"].lstrip("vV")
    release_date = data.get("published_at", "")[:10]

    if new_version != emu["latest_version"]:
        print(f"🆕 {emu['latest_version']} → {new_version}")
        emu["latest_version"] = new_version
        if release_date:
            emu["release_date"] = release_date
        return emu

    print("up to date")
    return None

def run_tracker(dry_run=False):
    db = load_db()
    updates =[]

    print(f"\n🔍 Emulator Version Tracker")
    print(f"   Checking {len(db['emulators'])} emulators...\n")

    for emu in db["emulators"]:
        updated_emu = check_emulator(emu)
        if updated_emu:
            updates.append(updated_emu["name"])
            
            # FIXED: Generate the Live Feed history
            if "feed" not in db:
                db["feed"] = []
            
            db["feed"].insert(0, {
                "emulator_id": updated_emu["id"],
                "version": updated_emu["latest_version"],
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "message": f"Version {updated_emu['latest_version']} released!"
            })

    if updates:
        print(f"\n📦 {len(updates)} update(s) found: {', '.join(updates)}")
        if not dry_run:
            # Keep feed trimmed to the last 50 updates so the file doesn't get huge
            db["feed"] = db["feed"][:50] 
            save_db(db)
    else:
        print("\n✨ Everything is up to date.")

    return len(updates)

if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        run_tracker(dry_run=True)
    else:
        updates = run_tracker()
        sys.exit(0 if updates == 0 else 1)
