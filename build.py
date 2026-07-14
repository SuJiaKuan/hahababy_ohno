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

    haha_row = pair_row("hahababy", haha_item, haha_url, "pair-haha")
    brand_row = pair_row(esc(brand), brand_item, brand_url, "pair-brand")
    vs_html = '\n          <div class="vs-badge">VS</div>' if haha_row and brand_row else ""
    rows_html = haha_row + vs_html + brand_row
    if not rows_html:
        rows_html = '\n          <p class="pair-empty">尚未找到商品名稱與連結</p>'

    slides_html = "".join(
        f'<img class="slide{" is-active" if i == 0 else ""}" src="images/{esc(img)}" loading="lazy" alt="{alt}">'
        for i, img in enumerate(images)
    )

    nav_html = ""
    if len(images) > 1:
        dots = "".join(
            f'<button class="dot{" is-active" if i == 0 else ""}" data-index="{i}" aria-label="第 {i + 1} 張圖"></button>'
            for i in range(len(images))
        )
        nav_html = f"""
          <button class="carousel-arrow prev" aria-label="上一張">‹</button>
          <button class="carousel-arrow next" aria-label="下一張">›</button>
          <div class="carousel-dots">{dots}</div>"""

    sources_html = "、".join(
        (f'<a href="{esc(u)}" target="_blank" rel="noopener">@{esc(s)}</a>' if u else f"@{esc(s)}")
        for s, u in case["sources"]
    ) or "-"

    return f"""
      <article class="card" data-brand="{esc(brand)}">
        <div class="card-image" data-index="0">
          <span class="brand-badge">{esc(brand)}</span>
          <span class="suspect-ribbon">疑似</span>
          {slides_html}
          <button class="cover-btn" aria-label="放大檢視圖片"></button>{nav_html}
        </div>
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@900&text=%E5%85%A8%E7%B6%B2%E7%98%8B%E5%82%B3%EF%BC%9A%E6%92%9E%E8%87%89%E7%B4%80%E9%8C%84&display=swap" rel="stylesheet">
<style>
{CSS}
</style>
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <h1 class="tabloid-headline">全網瘋傳：hahababy 撞臉全紀錄</h1>
    <p class="tabloid-deck">越比對，越眼熟？</p>
  </div>
  <div class="tabloid-band">眼尖網友回報中，持續更新</div>
  <div class="tabloid-ticker">
    <div class="wrap">
      網友揪出 <strong>{total}</strong> 起，橫跨 <strong>{brand_count}</strong> 個品牌
    </div>
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
    <p>本頁圖片彙整自 Threads 等公開社群上網友分享的貼文，僅作為大眾知情與公共討論用途，不代表本站對任何品牌之侵權指控做出法律判斷。圖片著作權屬原拍攝者／品牌所有。如內容有誤、需要下架，或想提供更多案例，歡迎透過 Threads 聯繫：<a href="https://www.threads.com/@feabries" target="_blank" rel="noopener">@feabries</a>。</p>
  </div>
</footer>

<div id="lightbox" class="lightbox" role="dialog" aria-modal="true">
  <button class="lightbox-arrow prev" aria-label="上一張">‹</button>
  <img id="lightbox-img" src="" alt="">
  <button class="lightbox-arrow next" aria-label="下一張">›</button>
  <div id="lightbox-dots" class="lightbox-dots"></div>
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
  --bg: #ffffff;
  --bg-alt: #f4f4f4;
  --text: #000000;
  --text-muted: #4d4d4d;
  --border: #000000;
  --card-bg: #ffffff;
  --accent: #e4002b;
  --accent-strong: #e4002b;
  --accent-soft: #ffe1e6;
  --yellow: #fff200;
  --chip-bg: #ffffff;
  --radius-lg: 4px;
  --radius-md: 3px;
  --shadow: 0 2px 0 rgba(0,0,0,.9);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0a0a0a;
    --bg-alt: #161616;
    --text: #ffffff;
    --text-muted: #b3b3b3;
    --border: #ffffff;
    --card-bg: #161616;
    --accent: #ff3355;
    --accent-strong: #e4002b;
    --accent-soft: #3a0e15;
    --yellow: #fff200;
    --chip-bg: #161616;
    --shadow: 0 2px 0 rgba(255,255,255,.85);
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
mark {
  background: var(--yellow);
  color: var(--text);
  padding: 0 .1em;
}
.wrap { max-width: 1180px; margin: 0 auto; padding: 0 24px; }

.site-header {
  background: var(--bg);
  padding-top: 32px;
}
.site-header .wrap { padding-bottom: 22px; }
.tabloid-headline {
  margin: 0 0 12px;
  font-family: "Noto Sans TC", -apple-system, "PingFang TC", sans-serif;
  font-weight: 900;
  font-size: clamp(30px, 6vw, 62px);
  line-height: 1.08;
  letter-spacing: -.02em;
  color: var(--text);
}
.tabloid-deck {
  display: inline-block;
  margin: 0;
  padding: 2px 10px;
  background: var(--bg);
  border: 2px solid var(--accent);
  color: var(--accent);
  font-size: clamp(15px, 2vw, 19px);
  font-weight: 800;
  letter-spacing: .01em;
  transform: rotate(-1.5deg);
}
.tabloid-band {
  background: var(--yellow);
  color: #000;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .03em;
  padding: 7px 24px;
  border-top: 2px solid var(--text);
  border-bottom: 2px solid var(--text);
}
.tabloid-ticker {
  background: var(--text);
  color: var(--bg);
}
.tabloid-ticker .wrap {
  padding-top: 11px;
  padding-bottom: 11px;
  font-size: 15px;
  font-weight: 700;
}
.tabloid-ticker strong {
  color: var(--accent);
  font-size: 23px;
  font-weight: 900;
  margin: 0 2px;
}
@media (max-width: 700px) {
  .site-header { padding-top: 20px; }
  .site-header .wrap { padding-bottom: 12px; }
  .tabloid-headline { margin-bottom: 8px; }
  .tabloid-deck { font-size: 14px; }
  .tabloid-band { padding: 5px 24px; font-size: 12px; }
  .tabloid-ticker .wrap { padding-top: 8px; padding-bottom: 8px; font-size: 13px; }
  .tabloid-ticker strong { font-size: 19px; }
}

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
@media (max-width: 700px) {
  .brand-filter { padding: 10px 0; }
  .chip-row {
    flex-wrap: nowrap;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .chip-row::-webkit-scrollbar { display: none; }
  .chip { flex: 0 0 auto; }
}
.chip {
  border: 1px solid var(--border);
  background: var(--chip-bg);
  color: var(--text);
  padding: 6px 14px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .02em;
  cursor: pointer;
  white-space: nowrap;
  transition: background .15s, color .15s, border-color .15s, transform .15s;
}
.chip:hover { border-color: var(--accent); transform: translateY(-1px) rotate(-1deg); }
.chip.active {
  background: var(--accent-strong);
  border-color: var(--accent-strong);
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
  border: 2px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  transition: transform .15s, box-shadow .15s;
}
.card:hover {
  transform: translate(-2px, -2px);
  box-shadow: 5px 5px 0 var(--border);
}
.card.is-hidden { display: none; }
.card-image {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 4;
  overflow: hidden;
  background: var(--bg-alt);
  touch-action: pan-y;
  user-select: none;
}
.slide {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  opacity: 0;
  transition: opacity .2s;
  pointer-events: none;
}
.slide.is-active { opacity: 1; }
.cover-btn {
  position: absolute;
  inset: 0;
  z-index: 1;
  width: 100%;
  height: 100%;
  padding: 0;
  border: 0;
  background: none;
  cursor: zoom-in;
}
.brand-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 2;
  background: #000;
  color: var(--yellow);
  border: 1.5px solid var(--yellow);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .02em;
  padding: 4px 10px;
  border-radius: var(--radius-md);
  box-shadow: 0 2px 8px rgba(0,0,0,.25);
  max-width: calc(100% - 60px);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suspect-ribbon {
  position: absolute;
  top: 16px;
  right: -32px;
  z-index: 2;
  width: 128px;
  padding: 3px 0;
  background: var(--accent-strong);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
  letter-spacing: .15em;
  text-align: center;
  transform: rotate(45deg);
  box-shadow: 0 2px 6px rgba(0,0,0,.35);
  border-top: 1px solid rgba(255,255,255,.5);
  border-bottom: 1px solid rgba(255,255,255,.5);
}
.vs-badge {
  align-self: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--text);
  color: var(--bg);
  border: 2px solid var(--accent-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 900;
}

.carousel-arrow {
  position: absolute;
  top: 50%;
  z-index: 3;
  transform: translateY(-50%);
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: rgba(12, 12, 15, .55);
  color: #fff;
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.carousel-arrow:hover { background: rgba(12, 12, 15, .8); }
.carousel-arrow.prev { left: 8px; }
.carousel-arrow.next { right: 8px; }

.carousel-dots {
  position: absolute;
  left: 50%;
  bottom: 10px;
  z-index: 3;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  padding: 5px 8px;
  border-radius: var(--radius-md);
  background: rgba(12, 12, 15, .45);
}
.dot {
  width: 6px;
  height: 6px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .5);
  cursor: pointer;
}
.dot.is-active { background: #fff; }

.card-body { padding: 14px 16px 16px; display: flex; flex-direction: column; gap: 10px; flex: 1; }

.card-pair { display: flex; flex-direction: column; gap: 8px; }
.pair-empty { margin: 0; font-size: 12.5px; color: var(--text-muted); }
.pair-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 9px 11px;
  border-radius: var(--radius-md);
  background: var(--bg-alt);
  border: 1px solid var(--border);
}
.pair-row.pair-haha {
  border: 1.5px solid var(--accent-strong);
  background: var(--accent-soft);
}
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
  border-radius: var(--radius-md);
  padding: 1px 8px;
}
.pair-haha .pair-label {
  color: #fff;
  background: var(--accent-strong);
  border-color: var(--accent-strong);
}
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
.site-footer a { color: var(--accent); }

@media (prefers-reduced-motion: reduce) {
  .chip, .card, .cover-btn img { transition: none; }
  .chip:hover, .card:hover, .cover-btn:hover img { transform: none; }
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
  border-radius: var(--radius-lg);
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
  touch-action: pan-y;
  user-select: none;
}
.lightbox-arrow {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  z-index: 1;
  width: 46px;
  height: 46px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .12);
  color: #fff;
  font-size: 26px;
  line-height: 1;
  display: none;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.lightbox.has-multi .lightbox-arrow { display: flex; }
.lightbox-arrow:hover { background: rgba(255, 255, 255, .25); }
.lightbox-arrow.prev { left: 16px; }
.lightbox-arrow.next { right: 16px; }
.lightbox-dots {
  position: absolute;
  left: 50%;
  bottom: 22px;
  transform: translateX(-50%);
  z-index: 1;
  display: none;
  gap: 8px;
}
.lightbox.has-multi .lightbox-dots { display: flex; }
.lightbox-dots .lb-dot {
  width: 8px;
  height: 8px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, .4);
  cursor: pointer;
}
.lightbox-dots .lb-dot.is-active { background: #fff; }
"""

JS = """
function showSlide(cardImage, index) {
  var slides = cardImage.querySelectorAll('.slide');
  var dots = cardImage.querySelectorAll('.dot');
  if (!slides.length) return;
  index = ((index % slides.length) + slides.length) % slides.length;
  slides.forEach(function (s, i) { s.classList.toggle('is-active', i === index); });
  dots.forEach(function (d, i) { d.classList.toggle('is-active', i === index); });
  cardImage.setAttribute('data-index', index);
}

var lightboxImages = [];
var lightboxIndex = 0;

function renderLightboxDots() {
  var dotsEl = document.getElementById('lightbox-dots');
  dotsEl.innerHTML = '';
  lightboxImages.forEach(function (src, i) {
    var b = document.createElement('button');
    b.className = 'lb-dot' + (i === lightboxIndex ? ' is-active' : '');
    b.setAttribute('data-index', i);
    b.setAttribute('aria-label', '第 ' + (i + 1) + ' 張圖');
    dotsEl.appendChild(b);
  });
}

function showLightboxSlide(index) {
  if (!lightboxImages.length) return;
  lightboxIndex = ((index % lightboxImages.length) + lightboxImages.length) % lightboxImages.length;
  document.getElementById('lightbox-img').src = lightboxImages[lightboxIndex];
  renderLightboxDots();
}

function openLightbox(images, startIndex) {
  lightboxImages = images;
  var lb = document.getElementById('lightbox');
  lb.classList.toggle('has-multi', images.length > 1);
  showLightboxSlide(startIndex || 0);
  lb.classList.add('is-open');
}

var swipe = { x: 0, cardImage: null, moved: false };
document.addEventListener('pointerdown', function (e) {
  var ci = e.target.closest('.card-image');
  swipe.cardImage = ci;
  swipe.x = e.clientX;
  swipe.moved = false;
});
document.addEventListener('pointerup', function (e) {
  if (!swipe.cardImage) return;
  var dx = e.clientX - swipe.x;
  if (Math.abs(dx) > 40) {
    var idx = parseInt(swipe.cardImage.getAttribute('data-index') || '0', 10);
    showSlide(swipe.cardImage, dx < 0 ? idx + 1 : idx - 1);
    swipe.moved = true;
  }
});

var lbSwipe = { x: 0, active: false, moved: false };
document.addEventListener('pointerdown', function (e) {
  var lb = document.getElementById('lightbox');
  lbSwipe.active = lb.classList.contains('is-open') && !!e.target.closest('#lightbox');
  lbSwipe.x = e.clientX;
  lbSwipe.moved = false;
});
document.addEventListener('pointerup', function (e) {
  if (!lbSwipe.active) return;
  var dx = e.clientX - lbSwipe.x;
  if (Math.abs(dx) > 40) {
    showLightboxSlide(lightboxIndex + (dx < 0 ? 1 : -1));
    lbSwipe.moved = true;
  }
});

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

  var prevBtn = e.target.closest('.carousel-arrow.prev');
  if (prevBtn) {
    var ci1 = prevBtn.closest('.card-image');
    showSlide(ci1, parseInt(ci1.getAttribute('data-index') || '0', 10) - 1);
    return;
  }
  var nextBtn = e.target.closest('.carousel-arrow.next');
  if (nextBtn) {
    var ci2 = nextBtn.closest('.card-image');
    showSlide(ci2, parseInt(ci2.getAttribute('data-index') || '0', 10) + 1);
    return;
  }
  var dot = e.target.closest('.dot');
  if (dot) {
    var ci3 = dot.closest('.card-image');
    showSlide(ci3, parseInt(dot.getAttribute('data-index'), 10));
    return;
  }

  var coverBtn = e.target.closest('.cover-btn');
  if (coverBtn) {
    if (swipe.moved) { swipe.moved = false; return; }
    var ci4 = coverBtn.closest('.card-image');
    var slideEls = ci4.querySelectorAll('.slide');
    var srcs = Array.prototype.map.call(slideEls, function (s) { return s.getAttribute('src'); });
    var activeIdx = parseInt(ci4.getAttribute('data-index') || '0', 10);
    openLightbox(srcs, activeIdx);
    return;
  }

  var lbPrev = e.target.closest('.lightbox-arrow.prev');
  if (lbPrev) { showLightboxSlide(lightboxIndex - 1); return; }
  var lbNext = e.target.closest('.lightbox-arrow.next');
  if (lbNext) { showLightboxSlide(lightboxIndex + 1); return; }
  var lbDot = e.target.closest('.lb-dot');
  if (lbDot) { showLightboxSlide(parseInt(lbDot.getAttribute('data-index'), 10)); return; }

  if (e.target.closest('#lightbox')) {
    if (lbSwipe.moved) { lbSwipe.moved = false; return; }
    document.getElementById('lightbox').classList.remove('is-open');
  }
});
document.addEventListener('keydown', function (e) {
  var lb = document.getElementById('lightbox');
  if (!lb.classList.contains('is-open')) return;
  if (e.key === 'Escape') { lb.classList.remove('is-open'); return; }
  if (e.key === 'ArrowLeft') { showLightboxSlide(lightboxIndex - 1); return; }
  if (e.key === 'ArrowRight') { showLightboxSlide(lightboxIndex + 1); return; }
});
"""

if __name__ == "__main__":
    build()
