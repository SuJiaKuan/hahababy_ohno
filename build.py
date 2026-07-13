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


def card_html(row):
    img = esc(row["image"])
    item = esc(row["item"])
    brand_url = row.get("brand_product_url", "").strip()
    haha_url = row.get("hahababy_product_url", "").strip()
    provider = esc(row.get("provider", ""))
    note = row.get("note", "").strip()

    links = []
    if brand_url:
        links.append(
            f'<a class="card-link" href="{esc(brand_url)}" target="_blank" rel="noopener">品牌商品頁 ↗</a>'
        )
    if haha_url:
        links.append(
            f'<a class="card-link" href="{esc(haha_url)}" target="_blank" rel="noopener">hahababy 商品頁 ↗</a>'
        )
    links_html = "".join(links) if links else '<span class="card-link card-link--muted">尚未找到商品連結</span>'

    provider_html = f'<a href="{esc(note)}" target="_blank" rel="noopener">@{provider}</a>' if note else f"@{provider}"

    return f"""
      <article class="card" data-brand="{esc(row['brand'])}">
        <button class="card-image" data-full="images/{img}" aria-label="放大檢視圖片">
          <img src="images/{img}" loading="lazy" alt="{item}">
        </button>
        <div class="card-body">
          <p class="card-item">{item}</p>
          <div class="card-links">{links_html}</div>
          <p class="card-provider">提供者：{provider_html}</p>
        </div>
      </article>"""


def build():
    rows = load_rows()
    by_brand = defaultdict(list)
    for row in rows:
        by_brand[row["brand"]].append(row)

    # sort brands by number of cases desc, then name
    brand_order = sorted(by_brand.keys(), key=lambda b: (-len(by_brand[b]), b))
    total = len(rows)
    brand_count = len(by_brand)

    chips = ['<button class="chip active" data-filter="all">全部（' + str(total) + '）</button>']
    for b in brand_order:
        chips.append(
            f'<button class="chip" data-filter="{esc(b)}">{esc(b)}（{len(by_brand[b])}）</button>'
        )

    sections = []
    for b in brand_order:
        items = by_brand[b]
        cards = "".join(card_html(r) for r in items)
        sections.append(f"""
    <section class="brand-group" data-brand="{esc(b)}">
      <h2 class="brand-title">{esc(b)} <span class="count">{len(items)}</span></h2>
      <div class="cards-grid">{cards}
      </div>
    </section>""")

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

<main class="wrap">{''.join(sections)}
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

.brand-group { margin-bottom: 48px; }
.brand-group.is-hidden { display: none; }
.brand-title {
  font-size: 20px;
  margin: 0 0 18px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--accent);
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.brand-title .count {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-muted);
}

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 20px;
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
.card-body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 10px; flex: 1; }
.card-item { margin: 0; font-size: 14px; }
.card-links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: auto; }
.card-link {
  font-size: 12.5px;
  color: var(--accent);
  text-decoration: none;
  border: 1px solid var(--accent-soft);
  background: var(--accent-soft);
  padding: 4px 10px;
  border-radius: 8px;
}
.card-link:hover { text-decoration: underline; }
.card-link--muted {
  color: var(--text-muted);
  border-color: var(--border);
  background: transparent;
}
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
    document.querySelectorAll('.brand-group').forEach(function (section) {
      section.classList.toggle('is-hidden', filter !== 'all' && section.getAttribute('data-brand') !== filter);
    });
    return;
  }
  var imgBtn = e.target.closest('.card-image');
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
