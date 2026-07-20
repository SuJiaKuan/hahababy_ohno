#!/usr/bin/env python3
"""Convert browser-exported cookies (e.g. from the "Cookie-Editor" extension's
"Export as JSON" button) into a Playwright storage_state.json the archiver can
load, so it can capture pages as a logged-in user.

Usage:
  1. Log into shopee.tw / facebook.com / instagram.com in your normal browser.
  2. For each site, open Cookie-Editor -> Export -> Export as JSON, and save
     the file under scripts/auth/raw/ (any filename, e.g. shopee.json).
  3. Run: python3 scripts/build_storage_state.py
     -> writes scripts/auth/storage_state.json

Nothing under scripts/auth/ is committed to git (see .gitignore) - it only
ever lives on this machine.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "scripts" / "auth" / "raw"
OUT_PATH = ROOT / "scripts" / "auth" / "storage_state.json"

SAME_SITE_MAP = {
    "no_restriction": "None",
    "lax": "Lax",
    "strict": "Strict",
    "unspecified": "Lax",
}


def convert_cookie(c):
    return {
        "name": c["name"],
        "value": c["value"],
        "domain": c["domain"],
        "path": c.get("path", "/"),
        "expires": -1 if c.get("session") or not c.get("expirationDate") else int(c["expirationDate"]),
        "httpOnly": bool(c.get("httpOnly", False)),
        "secure": bool(c.get("secure", False)),
        "sameSite": SAME_SITE_MAP.get(str(c.get("sameSite", "")).lower(), "Lax"),
    }


def main():
    if not RAW_DIR.exists() or not any(RAW_DIR.glob("*.json")):
        print(f"No cookie exports found in {RAW_DIR}/ - nothing to do.")
        print("Export cookies with Cookie-Editor (Export as JSON) and place the file there.")
        return

    cookies = []
    seen = set()
    for f in sorted(RAW_DIR.glob("*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "cookies" in raw:
            raw = raw["cookies"]
        n = 0
        for c in raw:
            key = (c["name"], c["domain"], c.get("path", "/"))
            if key in seen:
                continue
            seen.add(key)
            cookies.append(convert_cookie(c))
            n += 1
        print(f"{f.name}: {n} cookies")

    OUT_PATH.write_text(json.dumps({"cookies": cookies, "origins": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT_PATH} ({len(cookies)} cookies total)")


if __name__ == "__main__":
    main()
