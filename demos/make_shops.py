"""one-off: writes the Local Studio concept demo shop pages (made-up businesses, fictional 555 numbers)."""
from pathlib import Path
OUT = Path(r"C:\dev\sites\yegsites\demos")

PAGE = """<!doctype html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} | Concept demo by [BRAND]</title>
<meta name="description" content="Concept demo website by Local Studio. {name} is a made-up business.">
<meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<style>
  :root {{ color-scheme: light; {vars} }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink); font: 400 17px/1.6 var(--body); -webkit-font-smoothing: antialiased; }}
  a {{ color: inherit; }}
  :focus-visible {{ outline: 3px solid var(--accent); outline-offset: 3px; border-radius: 6px; }}
  .wrap {{ width: min(1100px, 100% - 40px); margin-inline: auto; }}
  .note {{ background: #0e1013; color: #f2efe6; font: 600 14px/1.4 "Figtree", system-ui, sans-serif; }}
  .note .wrap {{ display: flex; flex-wrap: wrap; gap: 0 16px; justify-content: space-between; align-items: center; padding: 4px 0; }}
  .note a {{ color: #ffc83d; display: inline-flex; align-items: center; min-height: 44px; }}
  header.top {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; min-height: 76px; }}
  .brand {{ font: var(--brand-font); text-decoration: none; display: inline-flex; align-items: center; min-height: 44px; }}
  .open {{ font-size: 14px; font-weight: 700; color: var(--ok-ink); background: var(--ok-bg); padding: 6px 12px; border-radius: 99px; white-space: nowrap; }}
  .btn {{ display: inline-flex; align-items: center; justify-content: center; gap: 10px; min-height: 52px; padding: 0 24px; border-radius: var(--radius); font-weight: 700; text-decoration: none; transition: transform .12s, filter .15s; }}
  .btn:hover {{ filter: brightness(1.06); }} .btn:active {{ transform: scale(.97); }}
  .btn-main {{ background: var(--accent); color: var(--accent-ink); }}
  .btn-line {{ border: 2px solid currentColor; }}
  .hero {{ background: var(--hero); color: var(--hero-ink); border-radius: var(--radius-lg); padding: clamp(32px, 6vw, 64px); display: grid; grid-template-columns: 1.2fr .8fr; gap: 40px; align-items: center; }}
  .hero h1 {{ font: var(--h1); margin: 0 0 18px; }}
  .hero p {{ margin: 0 0 28px; font-size: 19px; max-width: 34ch; opacity: .92; }}
  .ctas {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .art {{ align-self: stretch; min-height: 280px; border-radius: calc(var(--radius-lg) - 8px); background: var(--art); position: relative; overflow: hidden; }}
  .art span {{ position: absolute; left: 14px; bottom: 12px; font-size: 13px; font-weight: 600; background: rgba(0,0,0,.55); color: #fff; padding: 4px 10px; border-radius: 99px; }}
  section {{ padding: 64px 0 0; }}
  h2 {{ font: var(--h2); margin: 0 0 22px; }}
  .grid {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 28px; }}
  .svc {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }}
  .svc li {{ display: flex; justify-content: space-between; gap: 16px; padding: 16px 20px; background: var(--card); border: 1px solid var(--line); border-radius: var(--radius); font-weight: 600; }}
  .svc li span {{ color: var(--muted); font-weight: 500; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 18px; padding: 22px; }}
  .hours {{ display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; margin: 0; }}
  .hours dt {{ color: var(--muted); }} .hours dd {{ margin: 0; font-weight: 600; text-align: right; }}
  .review {{ margin-top: 18px; padding-top: 18px; border-top: 1px solid var(--line); }}
  .review small {{ display: block; font-weight: 700; color: var(--muted); margin-bottom: 6px; font-size: 14px; }}
  .map {{ margin-top: 64px; height: 220px; border-radius: var(--radius-lg); background: var(--map); position: relative; overflow: hidden; }}
  .map svg {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
  .map .btn {{ position: absolute; right: 18px; bottom: 18px; }}
  footer {{ padding: 48px 0 56px; color: var(--muted); font-size: 15px; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; }}
  @media (max-width: 800px) {{
    .hero {{ grid-template-columns: 1fr; padding: 28px 22px; gap: 24px; }}
    .art {{ min-height: 170px; order: -1; }}
    .grid {{ grid-template-columns: 1fr; }}
    .ctas .btn {{ flex: 1 1 100%; }}
    section {{ padding-top: 48px; }}
    .wrap {{ width: calc(100% - 32px); }}
    .map .btn {{ left: 16px; right: 16px; }}
  }}
  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>
</head>
<body>
<div class="note"><div class="wrap"><span>Concept demo by [BRAND]. {name} is made up.</span><a href="/#work">Back to [BRAND]</a></div></div>
<div class="wrap">
  <header class="top"><a class="brand" href="#">{name}</a><span class="open">{open}</span></header>
  <div class="hero">
    <div>
      <h1>{headline}</h1>
      <p>{sub}</p>
      <div class="ctas"><a class="btn btn-main" href="tel:+17805550100">Call (780) 555-0100</a><a class="btn btn-line" href="#map">Get directions</a></div>
    </div>
    <div class="art" role="img" aria-label="{art_label}"><span>Your photo goes here</span></div>
  </div>

  <section>
    <div class="grid">
      <div>
        <h2>{svc_title}</h2>
        <ul class="svc">{services}</ul>
      </div>
      <div>
        <h2>Hours</h2>
        <div class="card">
          <dl class="hours">{hours}</dl>
          <div class="review"><small>From Google reviews</small><em>Your best Google review goes here, word for word, with the reviewer's first name.</em></div>
        </div>
      </div>
    </div>
  </section>

  <div class="map" id="map" role="img" aria-label="Map placeholder">
    <svg viewBox="0 0 1100 220" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><path d="M0 150h1100M0 60h1100M300 0v220M760 0v220" stroke="{road}" stroke-width="16"/><path d="M0 200L1100 30" stroke="{road2}" stroke-width="10"/><path d="M530 50c-15 0-26 11-26 26 0 20 26 46 26 46s26-26 26-46c0-15-11-26-26-26z" fill="{pin}"/><circle cx="530" cy="76" r="9" fill="#fff"/></svg>
    <a class="btn btn-main" href="#map">Directions to {short}</a>
  </div>

  <footer><span>{name}, {area}, Edmonton</span><span>Concept demo, not a client. Built by [BRAND].</span></footer>
</div>
</body>
</html>
"""


def li(rows):
    return "".join(f"<li>{a}<span>{b}</span></li>" for a, b in rows)


def dl(rows):
    return "".join(f"<dt>{a}</dt><dd>{b}</dd>" for a, b in rows)


SHOPS = {
    "sample-barber": dict(
        name="Sample Barber Co.", short="the shop", area="Sample Ave", open="Open today until 7 pm",
        fonts="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,600..900&family=Figtree:wght@400;600;700&display=swap",
        vars='--bg:#f4f1ea; --ink:#1b1d1c; --muted:#585b57; --card:#fff; --line:#e2ddd2; --accent:#f2b84b; --accent-ink:#1f1608; '
             '--hero:#1f3b3a; --hero-ink:#f4f1ea; --ok-bg:#d9f2e3; --ok-ink:#0f6b3e; --radius:12px; --radius-lg:22px; '
             '--body:"Figtree",system-ui,sans-serif; --brand-font:800 22px/1 "Archivo",sans-serif; '
             '--h1:900 clamp(48px,7vw,88px)/.9 "Archivo",sans-serif; --h2:800 30px/1.1 "Archivo",sans-serif; '
             '--art:repeating-linear-gradient(135deg,#2c5755 0 26px,#f4f1ea 26px 40px,#b8453a 40px 66px,#f4f1ea 66px 80px); --map:#e4ecdf;',
        headline='<span style="font-stretch:70%;text-transform:uppercase">Walk-ins welcome. Fresh cuts all week.</span>',
        sub="Cuts, fades and beard trims on Sample Ave. Call ahead or just come in.",
        art_label="Barber pole stripes where the shop photo goes", svc_title="Services",
        services=li([("Haircut", "Ask for a price"), ("Skin fade", "Ask for a price"), ("Beard trim", "Ask for a price"), ("Kids cut", "Ask for a price")]),
        hours=dl([("Mon to Fri", "9 am to 7 pm"), ("Saturday", "9 am to 5 pm"), ("Sunday", "Closed")]),
        road="#fff", road2="#cfdcc8", pin="#1f3b3a"),
    "sample-bakery": dict(
        name="Sample Bake House", short="the bakery", area="Sample Street", open="Open today until 5 pm",
        fonts="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600..800&family=Figtree:wght@400;600;700&display=swap",
        vars='--bg:#fbf4ec; --ink:#2b1a14; --muted:#6a554b; --card:#fffaf5; --line:#efdfd0; --accent:#b3264d; --accent-ink:#fff; '
             '--hero:#f3dccb; --hero-ink:#2b1a14; --ok-bg:#f6e3c6; --ok-ink:#6e4204; --radius:999px; --radius-lg:28px; '
             '--body:"Figtree",system-ui,sans-serif; --brand-font:700 24px/1 "Fraunces",serif; '
             '--h1:800 clamp(42px,6vw,76px)/1.02 "Fraunces",serif; --h2:700 32px/1.1 "Fraunces",serif; '
             '--art:radial-gradient(circle at 30% 35%,#e8b48a 0 18%,transparent 19%),radial-gradient(circle at 68% 58%,#c9784b 0 22%,transparent 23%),'
             'radial-gradient(circle at 40% 78%,#f1cfa6 0 12%,transparent 13%),#b3264d; --map:#efe4d6;',
        headline="Fresh bread and cakes, baked every morning.",
        sub="Sourdough, cinnamon buns and custom cakes on Sample Street. Order a cake by phone.",
        art_label="Pastry shapes where the bakery photo goes", svc_title="What we bake",
        services=li([("Sourdough loaves", "Daily"), ("Cinnamon buns", "Daily"), ("Custom cakes", "Call to order"), ("Cookies by the dozen", "Ask for a price")]),
        hours=dl([("Tue to Sat", "8 am to 5 pm"), ("Sunday", "9 am to 1 pm"), ("Monday", "Closed")]),
        road="#fffaf5", road2="#e3cdb8", pin="#b3264d"),
}

for slug, d in SHOPS.items():
    p = OUT / slug / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(PAGE.format(**d), encoding="utf-8")
    print("wrote", p)
