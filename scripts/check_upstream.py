#!/usr/bin/env python3
"""查上游 release 里 geolite2-city-ipv4.csv.7z 的 sha256，跟本地记录比对。

结果写进 $GITHUB_OUTPUT：changed / sha256 / url / upstream_published。
GitHub 的 release asset API 直接带 digest 字段，所以不用下整个 17MB 包。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/sapics/ip-location-db/releases/tags/latest"
ASSET_NAME = "geolite2-city-ipv4.csv.7z"
STATE_PATH = Path("state/upstream.json")


def emit(**kwargs: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        for key, value in kwargs.items():
            print(f"{key}={value}")
        return
    with open(target, "a", encoding="utf-8") as f:
        for key, value in kwargs.items():
            f.write(f"{key}={value}\n")


def fetch_release() -> dict:
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "Aodun-IP-DB-bot",
    })
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> None:
    force = os.environ.get("FORCE", "").lower() == "true"
    try:
        release = fetch_release()
    except urllib.error.HTTPError as exc:
        sys.exit(f"拉取上游 release 失败: HTTP {exc.code} {exc.reason}")

    asset = next((a for a in release.get("assets", []) if a["name"] == ASSET_NAME), None)
    if asset is None:
        sys.exit(f"上游 release 里找不到 {ASSET_NAME}")

    digest = (asset.get("digest") or "").removeprefix("sha256:")
    if not digest:
        sys.exit(f"{ASSET_NAME} 没有 digest 字段，无法比对")

    previous = ""
    if STATE_PATH.exists():
        previous = json.loads(STATE_PATH.read_text(encoding="utf-8")).get("sha256", "")

    changed = force or digest != previous
    print(f"上游 sha256 = {digest}")
    print(f"本地记录   = {previous or '(无)'}")
    print(f"强制重建   = {force}")
    print(f"需要重建   = {changed}")

    emit(
        changed=str(changed).lower(),
        sha256=digest,
        url=asset["browser_download_url"],
        upstream_published=release.get("published_at", ""),
        asset_size=str(asset.get("size", 0)),
    )


if __name__ == "__main__":
    main()
