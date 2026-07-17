#!/usr/bin/env python3
"""Archive hahababy product pages (official/snapshot, shopee, social) so the
evidence survives even if hahababy takes more listings down.

For every product in data/comparisons.csv, for each available target
(official product page or its snapshot fallback, Shopee page, social post),
this saves:
  - screenshot.png   full-page screenshot of the rendered page
  - page.mhtml       single-file offline snapshot (open with a Chromium
                      based browser: Chrome / Edge / Brave)
  - images/          product photos extracted from the page, best-effort
                      filtered to exclude logos/icons/UI chrome
  - meta.json         source url, capture time, and what was collected

Layout: archive/{product_name}/{official,shopee,social}/

Usage:
  python3 scripts/archive_products.py              # archive everything
  python3 scripts/archive_products.py --only "XXX" # only products whose
                                                      name contains XXX
  python3 scripts/archive_products.py --headed      # show the browser
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
ARCHIVE_ROOT = ROOT / "archive"

sys.path.insert(0, str(ROOT))
from build import group_into_cases, load_rows  # noqa: E402  (reuse existing CSV parsing/merge logic)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
ICON_HINTS = re.compile(
    r"(logo|icon|sprite|favicon|avatar|spinner|loading|badge|payment|visa|"
    r"mastercard|jcb|paypal|linepay|placeholder|blank\.gif|1x1|pixel|emoji)",
    re.I,
)
PLACEHOLDER_HINTS = re.compile(r"(placeholder|blank\.gif|lazy[-_]?load|1x1|spacer)", re.I)
MIN_DIM = 150  # px per side, minimum to be considered a real product photo
MAX_ASPECT_RATIO = 3.0  # site banners/dividers tend to be much wider (or taller) than product photos
EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
}


def safe_name(name, fallback):
    name = (name or "").strip() or fallback
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:120] or fallback


def target_list(case):
    """Decide which URL to use per target, matching build.py's removed/snapshot logic."""
    targets = []
    official_url = case["hahababy_product_url_official"]
    if case["removed"] or not official_url:
        if case["snapshot_url"]:
            targets.append(("official", case["snapshot_url"], True))
    else:
        targets.append(("official", official_url, False))
    if case["hahababy_product_url_shopee"]:
        targets.append(("shopee", case["hahababy_product_url_shopee"], False))
    if case["hahababy_product_url_social"]:
        targets.append(("social", case["hahababy_product_url_social"], False))
    return targets


def guess_ext(content_type, url):
    if content_type:
        ct = content_type.split(";")[0].strip().lower()
        if ct in EXT_BY_CONTENT_TYPE:
            return EXT_BY_CONTENT_TYPE[ct]
    ext = Path(urllib.parse.urlparse(url).path).suffix
    return ext if ext and len(ext) <= 5 else ".jpg"


def download(url, dest_stem, referer):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        ct = resp.headers.get("Content-Type", "")
    dest = dest_stem.with_suffix(guess_ext(ct, url))
    dest.write_bytes(data)
    return dest


MAX_LAZY_SCROLL = 8000  # px; enough to load a product hero/gallery without reaching
                         # unrelated "you may also like" carousels far down long pages


def trigger_lazy_load(page, viewport_height):
    """Scroll incrementally so intersection-observer based lazy images swap
    their real src in, then return to the top for the screenshot. Capped so
    we don't scroll deep into unrelated recommended-product sections."""
    try:
        step = max(viewport_height - 200, 400)
        y = 0
        for _ in range(50):
            height = min(page.evaluate("document.body.scrollHeight"), MAX_LAZY_SCROLL)
            if y >= height:
                break
            page.mouse.wheel(0, step)
            y += step
            page.wait_for_timeout(220)
        page.wait_for_timeout(600)
        page.mouse.wheel(0, -y - step)
        page.wait_for_timeout(300)
    except Exception:  # noqa: BLE001
        pass


def extract_image_candidates(page):
    """Read every plausible image URL straight from element attributes so we
    don't depend on whether the browser has actually finished loading it."""
    raw = page.eval_on_selector_all(
        "img",
        """els => els.map(e => {
            const srcset = e.getAttribute('srcset') || e.getAttribute('data-srcset') || '';
            const parts = srcset.split(',').map(s => s.trim().split(/\\s+/)[0]).filter(Boolean);
            return {
                src: e.currentSrc || e.getAttribute('src') || '',
                dataSrc: e.getAttribute('data-src') || e.getAttribute('data-original') || e.getAttribute('data-lazy-src') || '',
                srcsetBest: parts.length ? parts[parts.length - 1] : '',
                alt: e.alt || ''
            };
        })""",
    )
    candidates = []
    for im in raw:
        for key in ("src", "dataSrc", "srcsetBest"):
            u = (im.get(key) or "").strip()
            if not u or u.startswith("data:") or PLACEHOLDER_HINTS.search(u):
                continue
            candidates.append({"src": u, "alt": im.get("alt", "")})
            break  # one URL per <img>, prefer already-resolved src over lazy attrs
    return candidates


SMALL_BANNER_AREA = 600_000   # px^2 below which a wide/tall strip is probably a logo or divider
HUGE_STRIP_AREA = 2_000_000   # px^2 above which even a very elongated image is likely a real
                               # long infographic-style product page section, not decoration


def is_product_like(d):
    if d.get("error") or not d.get("w") or not d.get("h"):
        return False
    w, h = d["w"], d["h"]
    if w < MIN_DIM or h < MIN_DIM:
        return False
    area = w * h
    ratio = max(w, h) / min(w, h)
    if ratio > 8 and area < HUGE_STRIP_AREA:
        return False
    if MAX_ASPECT_RATIO < ratio <= 8 and area < SMALL_BANNER_AREA:
        return False
    if ICON_HINTS.search(d["src"]) or ICON_HINTS.search(d.get("alt") or ""):
        return False
    return True


BOT_WALL_HINTS = re.compile(r"(/verify/traffic|/verify/captcha|checkpoint|/_sec/|antibot)", re.I)


def looks_like_homepage_redirect(original_url, final_url):
    """hahababy has been known to silently 404 -> redirect a delisted product's
    own URL back to the site root instead of returning an error status."""
    orig = urllib.parse.urlparse(original_url)
    final = urllib.parse.urlparse(final_url)
    if orig.netloc != final.netloc:
        return False
    return bool(orig.path.rstrip("/")) and final.path.rstrip("/") == ""


def capture(page, context, url, out_dir, is_snapshot):
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "source_url": url,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "is_snapshot": is_snapshot,
    }

    for attempt in range(3):
        try:
            page.goto(url, wait_until="load", timeout=45000)
        except PWTimeout:
            meta["error"] = "goto timeout"
        except Exception as e:  # noqa: BLE001 - best-effort archiving, record and move on
            meta["error"] = f"goto failed: {e}"
        else:
            meta.pop("error", None)
        if meta.get("error"):
            break

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PWTimeout:
            pass

        # web.archive.org occasionally serves a transient "internal error" banner
        # for a real snapshot; a plain reload usually fixes it
        if is_snapshot and page.locator("text=cannot be displayed due to an internal error").count():
            page.wait_for_timeout(3000)
            continue
        break

    if meta.get("error"):
        (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return meta

    trigger_lazy_load(page, page.viewport_size["height"] if page.viewport_size else 1600)

    meta["final_url"] = page.url
    meta["title"] = page.title()
    meta["blocked"] = bool(BOT_WALL_HINTS.search(page.url))

    try:
        page.screenshot(path=str(out_dir / "screenshot.png"), full_page=True, timeout=30000)
    except Exception as e:  # noqa: BLE001
        meta["screenshot_error"] = str(e)

    try:
        cdp = context.new_cdp_session(page)
        result = cdp.send("Page.captureSnapshot", {"format": "mhtml"})
        (out_dir / "page.mhtml").write_text(result["data"], encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        meta["mhtml_error"] = str(e)

    try:
        raw_candidates = [] if meta["blocked"] else extract_image_candidates(page)
    except Exception:  # noqa: BLE001
        raw_candidates = []

    seen_urls = set()
    resolved = []
    for im in raw_candidates:
        u = urllib.parse.urljoin(page.url, im["src"])
        if u in seen_urls or u.lower().split("?")[0].endswith(".svg") or ICON_HINTS.search(u):
            continue
        seen_urls.add(u)
        resolved.append({"src": u, "alt": im["alt"]})

    images_dir = out_dir / "images"
    downloaded_all = []
    if resolved:
        images_dir.mkdir(exist_ok=True)
        for i, im in enumerate(resolved, 1):
            entry = {"src": im["src"], "alt": im["alt"]}
            try:
                path = download(im["src"], images_dir / f"tmp{i:03d}", page.url)
                entry["path"] = path
                entry["bytes"] = path.stat().st_size
                try:
                    with Image.open(path) as pic:
                        entry["w"], entry["h"] = pic.size
                except UnidentifiedImageError:
                    entry["w"], entry["h"] = None, None
            except Exception as e:  # noqa: BLE001
                entry["error"] = str(e)
            downloaded_all.append(entry)

    # real, downloaded dimensions decide product-photo vs. icon/banner noise -
    # DOM-reported naturalWidth is unreliable while lazy images are still loading
    likely = [d for d in downloaded_all if is_product_like(d)]
    if likely:
        meta["image_selection"] = "likely_product"
        likely_ids = {id(d) for d in likely}
        keep, drop = likely, [d for d in downloaded_all if id(d) not in likely_ids]
    elif downloaded_all:
        meta["image_selection"] = "all_images"
        keep, drop = downloaded_all, []
    else:
        meta["image_selection"] = "none"
        keep, drop = [], []

    for d in drop:
        if d.get("path"):
            try:
                d["path"].unlink()
            except OSError:
                pass

    images_meta = []
    for idx, d in enumerate(keep, 1):
        if d.get("error") or not d.get("path"):
            images_meta.append({"src": d["src"], "error": d.get("error", "download failed")})
            continue
        final_path = images_dir / f"{idx:03d}{d['path'].suffix}"
        d["path"].rename(final_path)
        images_meta.append({"file": final_path.name, "src": d["src"], "w": d["w"], "h": d["h"], "bytes": d["bytes"]})
    meta["images"] = images_meta
    if images_dir.exists() and not any(images_dir.iterdir()):
        images_dir.rmdir()

    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="only archive products whose name contains this substring")
    ap.add_argument("--headed", action="store_true", help="show the browser window")
    args = ap.parse_args()

    cases = group_into_cases(load_rows())
    ARCHIVE_ROOT.mkdir(exist_ok=True)

    summary = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 1600}, locale="zh-TW")
        page = context.new_page()

        for case in cases:
            name = case["hahababy_item_name"]
            if args.only and args.only not in (name or ""):
                continue
            folder = safe_name(name, f"未命名商品_{case['images'][0]}")
            targets = target_list(case)
            if not targets:
                continue

            print(f"== {folder} ==")
            for target_name, url, is_snapshot in targets:
                out_dir = ARCHIVE_ROOT / folder / target_name
                print(f"  [{target_name}] {url}")
                meta = capture(page, context, url, out_dir, is_snapshot)

                stale_csv = False
                if (
                    target_name == "official"
                    and not is_snapshot
                    and not meta.get("error")
                    and looks_like_homepage_redirect(url, meta.get("final_url", ""))
                ):
                    stale_csv = True
                    if case["snapshot_url"]:
                        print("    !! official URL now redirects to the homepage (delisted, CSV not yet marked removed)")
                        print(f"    -> retrying with snapshot_url instead: {case['snapshot_url']}")
                        meta = capture(page, context, case["snapshot_url"], out_dir, True)
                        url = case["snapshot_url"]
                    else:
                        print("    !! official URL now redirects to the homepage (delisted) and no snapshot_url is recorded")

                n_imgs = len(meta.get("images", []))
                if meta.get("error"):
                    status = f"FAIL: {meta['error']}"
                elif meta.get("blocked"):
                    status = "BLOCKED (bot wall - see screenshot for evidence)"
                else:
                    status = "OK"
                print(f"    -> {status}, images={n_imgs}")
                summary.append(
                    {
                        "product": folder,
                        "target": target_name,
                        "url": url,
                        "error": meta.get("error"),
                        "blocked": meta.get("blocked", False),
                        "stale_csv_not_marked_removed": stale_csv,
                        "screenshot_error": meta.get("screenshot_error"),
                        "mhtml_error": meta.get("mhtml_error"),
                        "n_images": n_imgs,
                    }
                )
                time.sleep(1)  # be polite between requests

        browser.close()

    (ARCHIVE_ROOT / "_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for s in summary if not s["error"] and not s["blocked"])
    blocked = sum(1 for s in summary if s["blocked"])
    stale = [s for s in summary if s["stale_csv_not_marked_removed"]]
    print(f"\nDone: {ok}/{len(summary)} targets succeeded, {blocked} blocked by anti-bot walls. See archive/_summary.json for details.")
    if stale:
        print(f"\n{len(stale)} product(s) redirect to the homepage but data/comparisons.csv still has removed blank - update it:")
        for s in stale:
            print(f"  - {s['product']}")


if __name__ == "__main__":
    main()
