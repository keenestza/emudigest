#!/usr/bin/env python3
"""Update the public game recompilation/decompilation feed from GitHub."""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_PATH = ROOT / "recomp-projects.json"
OUTPUT_PATH = ROOT / "recomp-updates.json"
API = "https://api.github.com"
MAX_UPDATES = 100


def get_json(path):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "EmuDigest-Game-Port-Tracker",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    request = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def summary(body, title):
    body = re.sub(r"<!--.*?-->", "", body or "", flags=re.DOTALL)
    body = re.sub(r"<[^>]+>", "", body)
    lines = body.splitlines()
    start = next((index + 1 for index, line in enumerate(lines) if re.search(r"(?:what.s new|^#+\s*changes\b)", line, re.IGNORECASE)), 0)
    for line in lines[start:]:
        line = line.strip().lstrip("#*- ").strip()
        line = re.sub(r"!?(\[([^]]+)\])\([^)]+\)", r"\2", line)
        line = re.sub(r"[`*_]", "", line).strip()
        if len(line) < 18 or line.lower().startswith(("full changelog:", "compare:", "download:", "http")):
            continue
        return line[:220] + ("…" if len(line) > 220 else "")
    return title if title and not re.fullmatch(r"v?\d+(?:\.\d+)+(?:[-.][\w]+)*", title.strip(), re.IGNORECASE) else "New release published."


def update_for_release(project, release):
    return {
        "id": f"release:{project['repo']}:{release['id']}",
        "repo": project["repo"],
        "type": "Release",
        "date": release.get("published_at") or release.get("created_at"),
        "version": release.get("tag_name") or "Release",
        "summary": summary(release.get("body"), release.get("name")),
        "url": release["html_url"],
    }


def update_for_commit(project, commit):
    message = commit["commit"]["message"].splitlines()[0].strip()
    return {
        "id": f"commit:{project['repo']}:{commit['sha']}",
        "repo": project["repo"],
        "type": "Development update",
        "date": commit["commit"]["committer"]["date"],
        "version": commit["sha"][:7],
        "summary": message[:220] or "Source code updated.",
        "url": commit["html_url"],
    }


def main():
    projects = json.loads(PROJECTS_PATH.read_text(encoding="utf-8"))["projects"]
    if OUTPUT_PATH.exists():
        output = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    else:
        output = {"last_checked": None, "state": {}, "updates": []}
    state = output.setdefault("state", {})
    updates = output.setdefault("updates", [])
    known = {entry["id"] for entry in updates}
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=7)
    failures = []
    successful = 0

    for project in projects:
        repo = project["repo"]
        prior = state.get(repo, {})
        try:
            releases = get_json(f"/repos/{repo}/releases?per_page=30")
            if releases:
                published = [release for release in releases if not release.get("draft")]
                if not published:
                    continue
                latest = published[0]
                previous_id = prior.get("release_id")
                if previous_id is None:
                    # A new project starts with one recent release, not its entire history.
                    candidates = [latest] if datetime.fromisoformat(latest["published_at"].replace("Z", "+00:00")) >= recent_cutoff else []
                else:
                    candidates = []
                    for release in published:
                        if release["id"] == previous_id:
                            break
                        candidates.append(release)
                if repo == "OpenCommunityEdition/OpenCE" and len(candidates) > 1:
                    highlights = [summary(item.get("body"), item.get("name")) for item in reversed(candidates)]
                    highlights = [item for item in highlights if not item.lower().startswith(("network version", "merge pull request"))]
                    entry = update_for_release(project, latest)
                    entry["summary"] = f"{len(candidates)} builds since the last check. " + ("Highlights: " + "; ".join(highlights[-3:]) if highlights else "See the latest build notes.")
                    candidates = []
                    if entry["id"] not in known:
                        updates.append(entry)
                        known.add(entry["id"])
                for release in reversed(candidates):
                    entry = update_for_release(project, release)
                    if entry["id"] not in known:
                        updates.append(entry)
                        known.add(entry["id"])
                state[repo] = {"release_id": latest["id"], "latest_version": latest.get("tag_name"), "latest_date": latest.get("published_at"), "latest_url": latest["html_url"]}
            else:
                # Release-less decompilations still show their latest source change.
                commits = get_json(f"/repos/{repo}/commits?per_page=10")
                if not commits:
                    continue
                latest = commits[0]
                previous_sha = prior.get("commit_sha")
                new_commits = []
                for commit in commits:
                    if commit["sha"] == previous_sha:
                        break
                    new_commits.append(commit)
                substantive = [commit for commit in new_commits if not commit["commit"]["message"].lower().startswith(("merge ", "chore:", "docs:", "ci:"))]
                chosen = substantive[0] if substantive else None
                date = chosen["commit"]["committer"]["date"] if chosen else None
                is_recent = chosen and datetime.fromisoformat(date.replace("Z", "+00:00")) >= recent_cutoff
                if chosen and (previous_sha is not None or is_recent):
                    entry = update_for_commit(project, chosen)
                    if entry["id"] not in known:
                        updates.append(entry)
                        known.add(entry["id"])
                state[repo] = {"commit_sha": latest["sha"], "latest_version": latest["sha"][:7], "latest_date": latest["commit"]["committer"]["date"], "latest_url": latest["html_url"]}
            successful += 1
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            failures.append(f"{repo}: {exc}")

    if successful == 0:
        print("No projects could be checked; preserving the previous feed.", file=sys.stderr)
        return 1
    output["last_checked"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    output["checked_projects"] = successful
    output["total_projects"] = len(projects)
    output["updates"] = sorted(updates, key=lambda item: item["date"] or "", reverse=True)[:MAX_UPDATES]
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Checked {successful}/{len(projects)} projects; {len(output['updates'])} feed entries.")
    for failure in failures:
        print(f"Warning: {failure}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
