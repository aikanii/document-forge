#!/usr/bin/env python3
"""Generate Hephaestus icon assets (wax-seal 'H' logo) into ../assets/.

Run once from the packaging/ directory:  python gen_assets.py
Produces: icon_64.png, icon_256.png, icon.ico (Windows), icon.icns source png.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

SEAL_RED = (140, 47, 36, 255)
SEAL_DARK = (110, 32, 24, 255)
PARCHMENT = (243, 236, 219, 255)
GOLD = (168, 127, 44, 255)


def find_serif_bold(size: int):
    names = ["timesbd.ttf", "LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf",
             "Times New Roman Bold.ttf", "Tinos-Bold.ttf"]
    roots = ["/usr/share/fonts", "/usr/local/share/fonts",
             os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
             "/System/Library/Fonts", "/Library/Fonts"]
    for root in roots:
        for dirpath, _dirs, files in os.walk(root):
            for n in names:
                if n in files:
                    try:
                        return ImageFont.truetype(os.path.join(dirpath, n), size)
                    except Exception:
                        pass
    return ImageFont.load_default(size)


def make_seal(size: int) -> Image.Image:
    S = size * 4  # supersample
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = S / 2
    # irregular wax blob edge
    pts = []
    for i in range(144):
        a = math.radians(i * 2.5)
        rr = r * (0.93 + 0.05 * math.sin(i * 2.4) + 0.02 * math.sin(i * 5.1))
        pts.append((r + rr * math.cos(a), r + rr * math.sin(a)))
    d.polygon(pts, fill=SEAL_RED)
    # subtle inner shading ring
    d.ellipse([S * 0.06, S * 0.06, S * 0.94, S * 0.94], outline=SEAL_DARK,
              width=max(2, S // 90))
    # gold rule + parchment ring
    d.ellipse([S * 0.14, S * 0.14, S * 0.86, S * 0.86], outline=GOLD,
              width=max(2, S // 110))
    d.ellipse([S * 0.17, S * 0.17, S * 0.83, S * 0.83], outline=PARCHMENT,
              width=max(2, S // 60))
    # the H
    font = find_serif_bold(int(S * 0.52))
    d.text((r, r), "H", font=font, fill=PARCHMENT, anchor="mm")
    img = img.resize((size, size), Image.LANCZOS)
    return img


def main():
    os.makedirs(ASSETS, exist_ok=True)
    sizes = {"icon_16.png": 16, "icon_32.png": 32, "icon_64.png": 64,
             "icon_128.png": 128, "icon_256.png": 256}
    for name, sz in sizes.items():
        make_seal(sz).save(os.path.join(ASSETS, name))
    # Windows .ico with multiple embedded sizes
    ico_img = make_seal(256)
    ico_img.save(os.path.join(ASSETS, "icon.ico"),
                 sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                        (64, 64), (128, 128), (256, 256)])
    # macOS: an iconset folder that iconutil can turn into .icns
    iconset = os.path.join(ASSETS, "icon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for sz in (16, 32, 64, 128, 256, 512):
        make_seal(sz).save(os.path.join(iconset, f"icon_{sz}x{sz}.png"))
        make_seal(sz * 2).save(os.path.join(iconset, f"icon_{sz}x{sz}@2x.png"))
    print("Assets written to", os.path.abspath(ASSETS))
    print("On macOS run:  iconutil -c icns assets/icon.iconset -o assets/icon.icns")


if __name__ == "__main__":
    main()
