#!/usr/bin/env python3
"""Render a static HTML design-preview of the Hephaestus home screen.

This is a *design mock* generated from the live tool catalog (same names,
blurbs, categories and accent colors as the Tkinter app) so the look can be
inspected without launching the desktop GUI.
"""

import html
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hephaestus.tools import CATEGORY_TITLES, build_catalog  # noqa: E402
from hephaestus.theme import CATEGORY_COLORS  # noqa: E402

GLYPHS = {
    "merge": "＋", "split": "✂", "organize": "▦", "rotate": "⟳",
    "pagenum": "#", "watermark": "W", "compress": "⇲", "repair": "⚒",
    "ocr": "◉", "from_word": "W", "from_ppt": "P", "from_excel": "X",
    "jpg_to_pdf": "▧", "html_to_pdf": "&lt;/&gt;", "to_word": "W",
    "to_ppt": "P", "to_excel": "X", "pdf_to_jpg": "▨", "pdfa": "A",
    "protect": "", "unlock": "", "sign": "✒", "edit": "✎",
}

CSS = """
body { margin:0; background:#F3ECDB; color:#2B2119;
       font-family:'Times New Roman', 'Liberation Serif', serif; }
header { padding:26px 40px 10px; display:flex; align-items:center; gap:18px; }
h1 { font-size:34px; margin:0; letter-spacing:.5px; }
.tag { color:#7A1F1F; font-size:11px; letter-spacing:6px; margin-top:2px; }
.spacer { flex:1; }
.search { border:1px solid #A9926B; background:#EBE2CC; padding:6px 12px;
          font:italic 13px 'Times New Roman', serif; color:#6B5B47; width:220px; }
.rule { height:2px; background:#A9926B; margin:6px 0 0; }
main { padding:8px 44px 30px; }
.section { display:flex; align-items:center; margin:26px 0 4px; }
.section .bar { width:4px; height:20px; margin-right:10px; }
.section h2 { font-size:16px; margin:0; letter-spacing:1px; }
.section .line { flex:1; height:1px; background:#C9B99A; margin-left:14px; }
.grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(200px,1fr));
        gap:16px; margin-top:12px; }
.card { background:#FAF6EA; border:1px solid #C9B99A; height:150px;
        position:relative; text-align:center; padding-top:16px;
        box-shadow:0 1px 0 #D8CBAE; }
.card .tab { position:absolute; top:0; left:0; right:0; height:3px; }
.card .ico { width:52px; height:52px; margin:4px auto 6px; border-radius:4px;
             display:flex; align-items:center; justify-content:center;
             font-size:26px; }
.card h3 { font-size:14px; margin:2px 10px; }
.card p { font-size:11px; color:#6B5B47; margin:2px 14px; line-height:1.35; }
footer { background:#EBE2CC; border-top:1px solid #C9B99A; padding:6px 16px;
         display:flex; font-size:11px; font-style:italic; color:#6B5B47; }
footer .v { margin-left:auto; font-style:normal; }
.note { margin:14px 44px 0; background:#F6E3C5; color:#6B4A12; padding:10px 14px;
        font-size:12px; border:1px solid #A9926B; }
"""


def seal_svg(size=56):
    import math
    pts = []
    for i in range(48):
        a = math.radians(i * 7.5)
        rr = size / 2 * (0.94 + 0.06 * math.sin(i * 2.4))
        pts.append(f"{size/2 + rr*math.cos(a):.1f},{size/2 + rr*math.sin(a):.1f}")
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'<polygon points="{" ".join(pts)}" fill="#8C2F24"/>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{size*0.34}" fill="none" '
            f'stroke="#F3ECDB" stroke-width="{size*0.035}"/>'
            f'<text x="{size/2}" y="{size/2}" text-anchor="middle" '
            f'dominant-baseline="central" fill="#F3ECDB" '
            f'font-family="Times New Roman, serif" font-weight="bold" '
            f'font-size="{size*0.44}">H</text></svg>')


def card(tool):
    accent = CATEGORY_COLORS[tool.category]
    glyph = GLYPHS.get(tool.icon, "•")
    return f"""
    <div class="card">
      <div class="tab" style="background:{accent}"></div>
      <div class="ico" style="color:{accent}">{glyph}</div>
      <h3>{html.escape(tool.name)}</h3>
      <p>{html.escape(tool.blurb)}</p>
    </div>"""


def main():
    catalog = build_catalog()
    out = [f"""<!doctype html><html><head><meta charset="utf-8">
<title>Hephaestus — design preview</title><style>{CSS}</style></head><body>
<div class="note">Static design preview of the Hephaestus home screen
(“The Forge Floor”). The real application is a native desktop window built
with Tkinter — run <code>python -m hephaestus</code> to use it.</div>
<header>{seal_svg()}
  <div><h1>Hephaestus</h1><div class="tag">T H E &nbsp; D O C U M E N T &nbsp; F O R G E</div></div>
  <div class="spacer"></div>
  <div class="search">Seek a tool…</div>
</header>
<div class="rule"></div><main>"""]
    for key, title in CATEGORY_TITLES:
        tools = [t for t in catalog if t.category == key]
        if not tools:
            continue
        accent = CATEGORY_COLORS[key]
        out.append(f'<div class="section"><div class="bar" style="background:{accent}">'
                   f'</div><h2 style="color:{accent}">{html.escape(title.upper())}</h2>'
                   f'<div class="line"></div></div><div class="grid">')
        out += [card(t) for t in tools]
        out.append("</div>")
    out.append(f"""</main><footer><span>{len(catalog)} tools at the anvil ·
everything runs locally on this machine</span><span class="v">v1.0.0</span>
</footer></body></html>""")
    dest = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "preview", "home_preview.html")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    print("wrote", dest)


if __name__ == "__main__":
    main()
