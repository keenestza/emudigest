#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error
import re
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "emulators.json")
RSS_PATH = os.path.join(os.path.dirname(__file__), "..", "rss.xml")
GITHUB_API = "https://api.github.com"

def load_db():
    with open(DB_PATH, "r") as f:
        return json.load(f)

def save_db(db):
    db["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)
    print(f"✅ Database saved — {DB_PATH}")

def send_discord_alert(msg):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url: return
    data = json.dumps({"content": f"🚨 **EmuDigest Scraper Alert**\n{msg}"}).encode("utf-8")
    req = urllib.request.Request(webhook_url, method="POST", data=data)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0")
    try: urllib.request.urlopen(req, timeout=10)
    except: pass

def clean_changelog(text):
    if not text: return "New update available!"
    for line in text.split('\n'):
        line = re.sub(r'[#*`_]', '', line).strip()
        if len(line) > 15 and not line.startswith('http'):
            return line[:100] + ('...' if len(line) > 100 else '')
    return "New update available!"

def generate_rss(db):
    rss = '<?xml version="1.0" encoding="UTF-8" ?>\n<rss version="2.0">\n<channel>\n'
    rss += '  <title>EmuDigest - Latest Updates</title>\n'
    rss += '  <link>https://keenestza.github.io/emudigest/</link>\n'
    rss += '  <description>The latest emulator releases</description>\n'
    for item in db.get("feed", [])[:30]:
        rss += '  <item>\n'
        rss += f'    <title>{item["emulator_id"]} updated to v{item["version"]}</title>\n'
        rss += f'    <link>https://keenestza.github.io/emudigest/</link>\n'
        rss += f'    <description>{item.get("message", "")}</description>\n'
        rss += f'    <pubDate>{item["date"]}</pubDate>\n'
        rss += '  </item>\n'
    rss += '</channel>\n</rss>'
    with open(RSS_PATH, "w") as f: f.write(rss)
    print("✅ RSS Feed generated")

def github_get(endpoint):
    url = f"{GITHUB_API}{endpoint}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "EmuHub/1.0"})
    token = os.environ.get("GITHUB_TOKEN")
    if token: req.add_header("Authorization", f"token {token}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except: return None

def check_emulator(emu):
    if emu.get("github"):
        repo = emu.get("github")
        print(f"  Checking {emu['name']} (GitHub)...", end=" ")
        data = github_get(f"/repos/{repo}/releases/latest")
        if not data or "tag_name" not in data:
            tags = github_get(f"/repos/{repo}/tags")
            if tags:
                new_version = tags[0]["name"].lstrip("vV")
                if new_version != emu["latest_version"]:
                    emu["latest_version"] = new_version
                    emu["release_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    return emu, "New tag release created."
            print("up to date")
            return None, ""

        new_version = data["tag_name"].lstrip("vV")
        if new_version != emu["latest_version"]:
            print(f"🆕 v{new_version}")
            emu["latest_version"] = new_version
            emu["release_date"] = data.get("published_at", "")[:10]
            changelog = clean_changelog(data.get("body", ""))
            return emu, changelog
        print("up to date")
        return None, ""

    elif emu.get("scrape_url") and emu.get("scrape_regex"):
        print(f"  Checking {emu['name']} (Scrape)...", end=" ")
        try:
            req = urllib.request.Request(emu["scrape_url"], headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                match = re.search(emu["scrape_regex"], html)
                if match:
                    new_version = match.group(1).lstrip("vV")
                    if new_version != emu["latest_version"]:
                        print(f"🆕 v{new_version}")
                        emu["latest_version"] = new_version
                        emu["release_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        return emu, "New version detected on official website."
                    print("up to date")
                    return None, ""
                else:
                    print("⚠️ Failed")
                    send_discord_alert(f"Failed to find version for **{emu['name']}**.\nThe website may have changed its layout. Regex broken: `{emu['scrape_regex']}`")
                    return None, ""
        except Exception as e:
            print("⚠️ Error")
            send_discord_alert(f"Failed to load website for **{emu['name']}**.\nError: {e}")
            return None, ""
    return None, ""

def run_tracker(dry_run=False):
    db = load_db()
    updates =[]
    print(f"\n🔍 Emulator Version Tracker\n")
    for emu in db["emulators"]:
        updated_emu, changelog = check_emulator(emu)
        if updated_emu:
            updates.append(updated_emu["name"])
            if "feed" not in db: db["feed"] = []
            db["feed"].insert(0, {
                "emulator_id": updated_emu["id"],
                "version": updated_emu["latest_version"],
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "message": changelog
            })
    if updates:
        print(f"\n📦 {len(updates)} update(s) found.")
        if not dry_run:
            db["feed"] = db["feed"][:50] 
            save_db(db)
            generate_rss(db)
    else: print("\n✨ Up to date.")

if __name__ == "__main__":
    if "--dry-run" in sys.argv: run_tracker(dry_run=True)
    else: sys.exit(0 if run_tracker() == 0 else 1)
