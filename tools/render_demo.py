#!/usr/bin/env python3
"""
render_demo.py - the README's product pictures.

  docs/demo.gif     the desktop stepping through Off / 25 / 50 / 75 / Max
  docs/levels.png   the same frame at each preset, side by side
  docs/panel.png    the control window on its own
  docs/screenshot.png  a still of the demo at 75 %
  docs/social-preview.png  the same still on a 1280x640 card for GitHub

The desktop is an illustration (no real apps, no real wallpaper), but everything
Penumbra contributes is the real thing: the control window is rendered from the
app's own AppKit views by render_panel.py, the menu-bar crescent is
MenuTemplate.png, the Dock icon is docs/icon.png, and the shade is a black layer
at exactly the alpha the app would use: level x MAX_ALPHA. As in the app, the
control window and the cursor sit above the shade and are never dimmed.

Usage: python3 tools/render_demo.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT))
from penumbra import MAX_ALPHA, PRESET_LABELS, PRESET_VALUES   # noqa: E402

SS = 2                                  # everything is drawn at 2x
W, H = 1200, 700                        # scene size in points
SFNS = "/System/Library/Fonts/SFNS.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"
NY = "/System/Library/Fonts/NewYork.ttf"


def font(size, weight="Regular", path=SFNS, axes=None):
    f = ImageFont.truetype(path, int(size * SS))
    try:
        if axes:                        # New York: [optical size, weight, grade]
            f.set_variation_by_axes(axes)
        else:
            f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def p(*v):
    return [int(round(x * SS)) for x in v]


def shadow(base, box, radius, blur, alpha, dy=0):
    """Soft drop shadow under a rounded rect."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        p(x0, y0 + dy, x1, y1 + dy), radius=radius * SS, fill=(0, 0, 0, alpha))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur * SS)))


def wallpaper():
    """A bright daytime gradient with two soft hills: the kind of desktop that is
    pleasant at noon and blinding at midnight."""
    img = Image.new("RGB", p(W, H))
    px = img.load()
    top, mid, bot = (118, 176, 236), (196, 222, 244), (252, 226, 196)
    for y in range(H * SS):
        t = y / (H * SS - 1)
        a, b, u = (top, mid, t / 0.55) if t < 0.55 else (mid, bot, (t - 0.55) / 0.45)
        c = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
        for x in range(W * SS):
            px[x, y] = c
    img = img.convert("RGBA")
    hills = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(hills)
    d.ellipse(p(-300, 470, 760, 1100), fill=(226, 168, 132, 255))
    d.ellipse(p(420, 520, 1600, 1200), fill=(204, 132, 116, 255))
    d.ellipse(p(-100, 590, 1300, 1300), fill=(168, 98, 104, 255))
    img.alpha_composite(hills.filter(ImageFilter.GaussianBlur(3 * SS)))
    return img


def desktop():
    img = wallpaper()
    d = ImageDraw.Draw(img)

    # menu bar
    bar = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(bar).rectangle(p(0, 0, W, 26), fill=(255, 255, 255, 150))
    img.alpha_composite(bar)
    d = ImageDraw.Draw(img)
    x = 22
    for i, word in enumerate(["Notes", "File", "Edit", "Format", "View", "Window", "Help"]):
        f = font(13, "Bold" if i == 0 else "Regular")
        d.text(p(x, 5), word, font=f, fill=(20, 20, 24))
        x += d.textlength(word, font=f) / SS + 20
    d.text(p(W - 118, 5), "Thu 23:48", font=font(13, "Medium"), fill=(20, 20, 24))
    glyph = Image.open(ROOT / "MenuTemplate.png").convert("RGBA").resize(p(17, 17), Image.LANCZOS)
    black = Image.new("RGBA", glyph.size, (20, 20, 24, 255))
    img.paste(black, p(W - 152, 5), glyph.split()[3])

    # a bright document window
    wx0, wy0, wx1, wy1 = 96, 70, 800, 586
    shadow(img, (wx0, wy0, wx1, wy1), 11, 22, 95, dy=14)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(p(wx0, wy0, wx1, wy1), radius=11 * SS, fill=(255, 255, 255))
    d.rounded_rectangle(p(wx0, wy0, wx1, wy0 + 40), radius=11 * SS, fill=(246, 246, 247))
    d.rectangle(p(wx0, wy0 + 28, wx1, wy0 + 40), fill=(246, 246, 247))
    d.line(p(wx0, wy0 + 40, wx1, wy0 + 40), fill=(222, 222, 226), width=SS)
    for i, col in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
        cx = wx0 + 20 + i * 20
        d.ellipse(p(cx - 6, wy0 + 14, cx + 6, wy0 + 26), fill=col)
    d.text(p((wx0 + wx1) / 2, wy0 + 20), "Eclipse notes", font=font(13, "Semibold"),
           fill=(70, 70, 76), anchor="mm")

    tx = wx0 + 56
    d.text(p(tx, wy0 + 76), "Penumbra", font=font(34, path=NY, axes=[34, 700, 0]), fill=(24, 24, 28))
    d.text(p(tx, wy0 + 124), "NOUN  ·  ASTRONOMY", font=font(10.5, "Medium", MONO),
           fill=(150, 150, 158))
    body = [
        "The partial shadow at the edge of an eclipse, where the light",
        "source is only partly blocked. Inside it the sky never goes",
        "black. It fades, smoothly, by degrees.",
        "",
        "A laptop backlight has no such gradient at the bottom of its",
        "range. One step above off is still a lit panel, and in a dark",
        "room a white page at that floor is far brighter than the room",
        "around it. The last stretch, from the hardware minimum down",
        "to near black, has to be added in software.",
    ]
    y = wy0 + 160
    for line in body:
        d.text(p(tx, y), line, font=font(15.5, path=NY, axes=[16, 400, 0]), fill=(52, 52, 58))
        y += 25
    # a small figure in the page: light source, body, umbra and penumbra
    fy = wy0 + 420
    d.rounded_rectangle(p(tx, fy, wx1 - 56, fy + 74), radius=8 * SS, fill=(244, 245, 248))
    d.ellipse(p(tx + 28, fy + 17, tx + 68, fy + 57), fill=(250, 196, 84))
    d.polygon(p(tx + 190, fy + 25, tx + 560, fy + 6, tx + 560, fy + 68, tx + 190, fy + 49),
              fill=(214, 217, 226))
    d.polygon(p(tx + 190, fy + 25, tx + 560, fy + 30, tx + 560, fy + 44, tx + 190, fy + 49),
              fill=(120, 124, 140))
    d.ellipse(p(tx + 166, fy + 23, tx + 194, fy + 51), fill=(70, 74, 92))
    d.text(p(tx + 470, fy + 12), "penumbra", font=font(9.5, "Medium", MONO), fill=(120, 124, 140))

    # Dock
    n, tile, gap = 8, 46, 10
    dw = n * tile + (n + 1) * gap
    dx0, dy0 = (W - dw) / 2, H - 70
    dock = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(dock).rounded_rectangle(p(dx0, dy0, dx0 + dw, dy0 + 62), radius=17 * SS,
                                           fill=(255, 255, 255, 120),
                                           outline=(255, 255, 255, 170), width=SS)
    img.alpha_composite(dock)
    d = ImageDraw.Draw(img)
    cols = [(52, 132, 246), (250, 250, 252), (52, 199, 89), (255, 159, 10),
            (255, 69, 58), (175, 82, 222), (90, 200, 250)]
    for i in range(n):
        x0 = dx0 + gap + i * (tile + gap)
        if i == n - 1:
            icon = Image.open(DOCS / "icon.png").convert("RGBA").resize(p(tile, tile), Image.LANCZOS)
            img.alpha_composite(icon, tuple(p(x0, dy0 + 8)))
        else:
            d.rounded_rectangle(p(x0, dy0 + 8, x0 + tile, dy0 + 8 + tile), radius=11 * SS,
                                fill=cols[i])
    return img


def cursor(img, x, y):
    pts = [(0, 0), (0, 17), (4.2, 13.2), (7.4, 20), (10, 18.8), (6.9, 12.2), (12.4, 12.2)]
    poly = [(int((x + a) * SS), int((y + b) * SS)) for a, b in pts]
    d = ImageDraw.Draw(img)
    d.polygon(poly, fill=(0, 0, 0))
    d.line(poly + [poly[0]], fill=(255, 255, 255), width=int(1.4 * SS), joint="curve")


def panel_image(path):
    """The captured control window, with the window's corner radius restored."""
    im = Image.open(path).convert("RGBA")
    if im.width != 360 * SS:
        im = im.resize(p(360, 240), Image.LANCZOS)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1],
                                        radius=12 * SS, fill=255)
    im.putalpha(m)
    ImageDraw.Draw(im).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=12 * SS,
                                         outline=(255, 255, 255, 46), width=SS)
    return im


def frame(base, panels, shown_pct, alpha, with_panel=True):
    img = base.copy()
    if alpha > 0:
        img.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, int(round(alpha * 255)))))
    if with_panel:
        px, py = 790, 330
        shadow(img, (px, py, px + 360, py + 240), 12, 20, 120, dy=12)
        img.alpha_composite(panels[shown_pct], tuple(p(px, py)))
        seg = PRESET_VALUES.index(shown_pct)
        cursor(img, px + 20 + (seg + 0.5) * 64 + 6, py + 240 - 52 - 10)
    return img


def main():
    tmp = Path(tempfile.mkdtemp())
    subprocess.run([sys.executable, str(ROOT / "tools" / "render_panel.py"), str(tmp)]
                   + [str(v) for v in PRESET_VALUES], check=True, stdout=subprocess.DEVNULL)
    panels = {v: panel_image(tmp / ("panel-%03d.png" % v)) for v in PRESET_VALUES}
    base = desktop()

    # ---- demo.gif ----------------------------------------------------------
    ease = lambda t: t * t * (3 - 2 * t)
    order = PRESET_VALUES + [PRESET_VALUES[0]]
    frames, durs = [], []
    for a, b in zip(order, order[1:]):
        steps = 5 if b else 7
        for i in range(1, steps + 1):
            lvl = a + (b - a) * ease(i / steps)
            frames.append(frame(base, panels, b, lvl / 100 * MAX_ALPHA))
            durs.append(60)
        durs[-1] = 1500 if b == PRESET_VALUES[-1] else 1100
    frames.insert(0, frame(base, panels, 0, 0)); durs.insert(0, 1100)
    frames.pop(); durs.pop()                      # last frame equals the first
    GW = 1000
    small = [f.convert("RGB").resize((GW, GW * H // W), Image.LANCZOS) for f in frames]
    # one palette per frame: a shared one cannot hold both the bright and the dark end
    quant = [f.quantize(colors=255, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG)
             for f in small]
    quant[0].save(DOCS / "demo.gif", save_all=True, append_images=quant[1:], duration=durs,
                  loop=0, optimize=False, disposal=1)

    # ---- hero still (used as the GIF's poster in the social preview etc.) ---
    still = frame(base, panels, 75, 0.75 * MAX_ALPHA).convert("RGB")
    still.resize((1600, 1600 * H // W), Image.LANCZOS).save(DOCS / "screenshot.png", optimize=True)

    card = Image.new("RGB", (1280, 640), (12, 16, 30))       # 1280x640 for GitHub
    shot = still.resize((960, 960 * H // W), Image.LANCZOS)
    m = Image.new("L", shot.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], radius=14, fill=255)
    card.paste(shot, ((1280 - shot.width) // 2, (640 - shot.height) // 2), m)
    card.save(DOCS / "social-preview.png", optimize=True)
    panels[50].save(DOCS / "panel.png", optimize=True)     # the control window on its own

    # ---- levels.png --------------------------------------------------------
    tw, th, gap, cap = 224, 150, 20, 46
    LW = 5 * tw + 4 * gap
    out = Image.new("RGBA", p(LW, th + cap), (0, 0, 0, 0))
    crop = base.crop(p(70, 0, 70 + tw * 1.75, th * 1.75)).resize(p(tw, th), Image.LANCZOS)
    d = ImageDraw.Draw(out)
    for i, (v, name) in enumerate(zip(PRESET_VALUES, PRESET_LABELS)):
        a = v / 100 * MAX_ALPHA
        t = crop.copy()
        t.alpha_composite(Image.new("RGBA", t.size, (0, 0, 0, int(round(a * 255)))))
        m = Image.new("L", t.size, 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, t.width - 1, t.height - 1], radius=8 * SS, fill=255)
        x = i * (tw + gap)
        out.paste(t, tuple(p(x, 0)), m)
        d.rounded_rectangle(p(x, 0, x + tw, th), radius=8 * SS, outline=(128, 128, 134, 110), width=SS)
        d.text(p(x + 2, th + 11), name if not name.isdigit() else name + "%",
               font=font(13, "Semibold"), fill=(64, 140, 255))
        d.text(p(x + tw - 2, th + 12), "shade opacity %.2f" % a, font=font(11.5, "Regular"),
               fill=(134, 134, 140), anchor="ra")
    out.save(DOCS / "levels.png", optimize=True)

    for f in ("demo.gif", "screenshot.png", "panel.png", "levels.png"):
        print("%-16s %5.0f KB" % (f, (DOCS / f).stat().st_size / 1024))


if __name__ == "__main__":
    main()
