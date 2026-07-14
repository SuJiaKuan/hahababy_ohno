#!/usr/bin/env python3
"""Generate index.html from data/comparisons.csv.

Usage: python3 build.py
Reads data/comparisons.csv and writes index.html at the project root.
Re-run this any time the CSV is updated.
"""
import csv
import html
from collections import defaultdict, Counter
from pathlib import Path

ROOT = Path(__file__).parent
CSV_PATH = ROOT / "data" / "comparisons.csv"
OUT_PATH = ROOT / "index.html"


def load_rows():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def esc(s):
    return html.escape((s or "").strip())


def pair_row(label, name, url, css_class):
    name = (name or "").strip()
    url = (url or "").strip()
    if not name and not url:
        return ""
    name_html = esc(name) if name else '<span class="pair-name--empty">（品名待補）</span>'
    link_html = (
        f'<a class="pair-link" href="{esc(url)}" target="_blank" rel="noopener">商品頁 ↗</a>'
        if url else ""
    )
    return f"""
          <div class="pair-row {css_class}">
            <span class="pair-label">{label}</span>
            <div class="pair-main">
              <span class="pair-name">{name_html}</span>
              {link_html}
            </div>
          </div>"""


def group_into_cases(rows):
    """Merge rows that describe the same real-world comparison (same brand,
    same hahababy item, same brand item) submitted by different sources.
    Rows with no item names on either side can't be reliably matched, so
    each stays its own case."""
    order = []
    cases = {}
    for row in rows:
        brand = (row.get("brand") or "").strip()
        haha_item = (row.get("hahababy_item_name") or "").strip()
        brand_item = (row.get("brand_item_name") or "").strip()
        key = (brand, haha_item, brand_item) if (haha_item or brand_item) else ("__unique__", row["image"])

        if key not in cases:
            cases[key] = {
                "brand": brand,
                "brand_item_name": brand_item,
                "brand_product_url": (row.get("brand_product_url") or "").strip(),
                "hahababy_item_name": haha_item,
                "hahababy_product_url": (row.get("hahababy_product_url") or "").strip(),
                "images": [],
                "sources": [],
            }
            order.append(key)

        case = cases[key]
        case["images"].append(row["image"])
        if not case["brand_product_url"]:
            case["brand_product_url"] = (row.get("brand_product_url") or "").strip()
        if not case["hahababy_product_url"]:
            case["hahababy_product_url"] = (row.get("hahababy_product_url") or "").strip()

        src = ((row.get("source") or "").strip(), (row.get("source_url") or "").strip())
        if (src[0] or src[1]) and src not in case["sources"]:
            case["sources"].append(src)

    return [cases[k] for k in order]


def card_html(case):
    images = case["images"]
    cover = esc(images[0])
    brand = case["brand"]
    brand_item = case["brand_item_name"]
    brand_url = case["brand_product_url"]
    haha_item = case["hahababy_item_name"]
    haha_url = case["hahababy_product_url"]

    alt = esc(f"{brand} vs hahababy：{haha_item or brand_item or ''}".strip())

    rows_html = pair_row("hahababy", haha_item, haha_url, "pair-haha") + \
        pair_row(esc(brand), brand_item, brand_url, "pair-brand")
    if not rows_html:
        rows_html = '\n          <p class="pair-empty">尚未找到商品名稱與連結</p>'

    thumbs_html = ""
    if len(images) > 1:
        thumbs = "".join(
            f'<button class="thumb" data-full="images/{esc(img)}" aria-label="放大檢視圖片">'
            f'<img src="images/{esc(img)}" loading="lazy" alt="{alt}"></button>'
            for img in images[1:]
        )
        thumbs_html = f'\n        <div class="thumb-row">{thumbs}</div>'

    sources_html = "、".join(
        (f'<a href="{esc(u)}" target="_blank" rel="noopener">@{esc(s)}</a>' if u else f"@{esc(s)}")
        for s, u in case["sources"]
    ) or "—"

    return f"""
      <article class="card" data-brand="{esc(brand)}">
        <button class="card-image" data-full="images/{cover}" aria-label="放大檢視圖片">
          <span class="brand-badge">{esc(brand)}</span>
          <img src="images/{cover}" loading="lazy" alt="{alt}">
        </button>{thumbs_html}
        <div class="card-body">
          <div class="card-pair">{rows_html}
          </div>
          <p class="card-provider">來源/提供者：{sources_html}</p>
        </div>
      </article>"""


def build():
    rows = load_rows()
    cases = group_into_cases(rows)

    by_brand = defaultdict(list)
    for case in cases:
        by_brand[case["brand"]].append(case)

    # sort brands by number of cases desc, then name
    brand_order = sorted(by_brand.keys(), key=lambda b: (-len(by_brand[b]), b))
    total = len(cases)
    brand_count = len(by_brand)

    chips = ['<button class="chip active" data-filter="all">全部（' + str(total) + '）</button>']
    for b in brand_order:
        chips.append(
            f'<button class="chip" data-filter="{esc(b)}">{esc(b)}（{len(by_brand[b])}）</button>'
        )

    # one continuous grid, same-brand cards kept adjacent via brand_order
    cards = "".join(card_html(c) for b in brand_order for c in by_brand[b])

    html_out = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>hahababy 對照牆</title>
<meta name="description" content="網友蒐集整理的 hahababy 與其他品牌相似設計對照圖">
<style>
{CSS}
</style>
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <h1>hahababy 對照牆</h1>
    <p class="subtitle">網友自主蒐集整理的設計對照案例，供社會大眾檢視與討論。資料持續更新中。</p>
    <p class="stats">共 <strong>{total}</strong> 筆案例・涉及 <strong>{brand_count}</strong> 個品牌</p>
  </div>
</header>

<nav class="brand-filter">
  <div class="wrap chip-row">{''.join(chips)}</div>
</nav>

<main class="wrap">
  <div class="cards-grid">{cards}
  </div>
</main>

<footer class="site-footer">
  <div class="wrap">
    <p>本頁內容由網友於 Threads 等公開社群自主蒐集、整理與提供，僅作為消費者知情與公共討論用途，不代表本站對任何品牌之侵權指控做出法律判斷。圖片著作權屬原拍攝者／品牌所有。如有錯誤或需下架，請聯繫更正。</p>
  </div>
</footer>

<div id="lightbox" class="lightbox" role="dialog" aria-modal="true">
  <img id="lightbox-img" src="" alt="">
</div>

<script>
{JS}
</script>
</body>
</html>
"""
    OUT_PATH.write_text(html_out, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({total} cases, {brand_count} brands)")


CSS = """
:root {
  color-scheme: light dark;
  --bg: #faf7f2;
  --bg-alt: #f1ece3;
  --text: #2b2622;
  --text-muted: #746b60;
  --border: #e2d9cb;
  --card-bg: #ffffff;
  --accent: #c0432e;
  --accent-soft: #f3dcd5;
  --chip-bg: #ffffff;
  --shadow: 0 1px 2px rgba(43,38,34,.06), 0 8px 24px rgba(43,38,34,.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1c1a18;
    --bg-alt: #242220;
    --text: #f1ece4;
    --text-muted: #a89e91;
    --border: #38332c;
    --card-bg: #262320;
    --accent: #e2725b;
    --accent-soft: #3a2620;
    --chip-bg: #262320;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, "PingFang TC", "Noto Sans TC", "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.6;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px; }

.site-header {
  padding: 56px 0 32px;
  text-align: center;
  border-bottom: 1px solid var(--border);
  background: var(--bg-alt);
}
.site-header h1 {
  margin: 0 0 12px;
  font-size: clamp(28px, 4vw, 40px);
  letter-spacing: .01em;
}
.site-header .subtitle {
  margin: 0 auto 16px;
  max-width: 620px;
  color: var(--text-muted);
  font-size: 15px;
}
.site-header .stats {
  font-size: 14px;
  color: var(--text-muted);
}
.site-header .stats strong { color: var(--accent); }

.brand-filter {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--bg);
  border-bottom: 1px solid var(--border);
  padding: 14px 0;
}
.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 1px solid var(--border);
  background: var(--chip-bg);
  color: var(--text);
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  transition: background .15s, color .15s, border-color .15s;
}
.chip:hover { border-color: var(--accent); }
.chip.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

main { padding: 40px 0 20px; }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap: 24px;
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
}
.card.is-hidden { display: none; }
.card-image {
  position: relative;
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: var(--bg-alt);
  cursor: zoom-in;
  aspect-ratio: 3 / 4;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  transition: transform .25s;
}
.card-image:hover img { transform: scale(1.03); }
.brand-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 1;
  background: rgba(28, 26, 24, .78);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .02em;
  padding: 5px 10px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0,0,0,.25);
  max-width: calc(100% - 20px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumb-row {
  display: flex;
  gap: 6px;
  padding: 10px 16px 0;
  overflow-x: auto;
}
.thumb {
  flex: 0 0 auto;
  width: 44px;
  aspect-ratio: 3 / 4;
  padding: 0;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
  background: var(--bg-alt);
  cursor: zoom-in;
}
.thumb:hover { border-color: var(--accent); }
.thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }

.card-body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 10px; flex: 1; }

.card-pair { display: flex; flex-direction: column; gap: 8px; }
.pair-empty { margin: 0; font-size: 12.5px; color: var(--text-muted); }
.pair-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 9px 11px;
  border-radius: 8px;
  background: var(--bg-alt);
  border: 1px solid var(--border);
}
.pair-row.pair-haha { border-color: var(--accent-soft); }
.pair-label {
  display: inline-block;
  align-self: flex-start;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .03em;
  text-transform: uppercase;
  color: var(--text-muted);
  background: var(--card-bg);
  border: 1px solid var(--border);
  border-radius: 5px;
  padding: 1px 6px;
}
.pair-haha .pair-label { color: var(--accent); border-color: var(--accent-soft); }
.pair-main {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  column-gap: 8px;
  row-gap: 2px;
}
.pair-name { font-size: 13.5px; line-height: 1.45; word-break: break-word; }
.pair-name--empty { color: var(--text-muted); font-style: italic; font-size: 12px; }
.pair-link {
  font-size: 12px;
  color: var(--accent);
  text-decoration: none;
  white-space: nowrap;
}
.pair-link:hover { text-decoration: underline; }

.card-provider { margin: 0; font-size: 12px; color: var(--text-muted); }
.card-provider a { color: var(--text-muted); }

.site-footer {
  border-top: 1px solid var(--border);
  padding: 28px 0 60px;
  color: var(--text-muted);
  font-size: 12.5px;
}

.lightbox {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.85);
  display: none;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 100;
  cursor: zoom-out;
}
.lightbox.is-open { display: flex; }
.lightbox img {
  max-width: 100%;
  max-height: 100%;
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
}
"""

JS = """
document.addEventListener('click', function (e) {
  var chip = e.target.closest('.chip');
  if (chip) {
    var filter = chip.getAttribute('data-filter');
    document.querySelectorAll('.chip').forEach(function (c) { c.classList.remove('active'); });
    chip.classList.add('active');
    document.querySelectorAll('.card').forEach(function (card) {
      card.classList.toggle('is-hidden', filter !== 'all' && card.getAttribute('data-brand') !== filter);
    });
    return;
  }
  var imgBtn = e.target.closest('.card-image, .thumb');
  if (imgBtn) {
    var full = imgBtn.getAttribute('data-full');
    var lb = document.getElementById('lightbox');
    var lbImg = document.getElementById('lightbox-img');
    lbImg.src = full;
    lb.classList.add('is-open');
    return;
  }
  if (e.target.closest('#lightbox')) {
    document.getElementById('lightbox').classList.remove('is-open');
  }
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') document.getElementById('lightbox').classList.remove('is-open');
});
"""

if __name__ == "__main__":
    build()
