#!/usr/bin/env python3
"""Generate Penumbra's assets, locally (no external services):

  * AppIcon.iconset  -> AppIcon.icns   (the app icon)
  * MenuTemplate.png / _18.png         (monochrome menu-bar glyph, matches icon)
  * icon_preview.png, icon_contact.png (for review)

Concept: a partial eclipse. A luminous sphere on a deep-night squircle, with a
soft *penumbral* shadow sweeping across it. The soft, graduated shadow is the
whole point of the name. Run build_app.sh afterwards to fold assets into the app.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
S = 1024


def squircle_mask(size, frac=0.225):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=int(size * frac), fill=255)
    return m


def render_icon(size):
    S = size
    yy, xx = np.ogrid[0:S, 0:S]

    # --- deep-night vertical gradient background ---
    top, bot = np.array([32, 43, 76], float), np.array([6, 8, 15], float)
    t = np.linspace(0, 1, S)[:, None]
    canvas = np.repeat((top * (1 - t) + bot * t)[:, None, :], S, axis=1)

    cx, cy, R = S * 0.5, S * 0.5, S * 0.31

    disc = Image.new("L", (S, S), 0)
    ImageDraw.Draw(disc).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    disc = np.asarray(disc.filter(ImageFilter.GaussianBlur(S * 0.003)), float) / 255.0

    # Offset occluder with a soft (blurred) edge -> the soft terminator IS the penumbra.
    occ = Image.new("L", (S, S), 0)
    ox, oy, rr = R * 0.50, -R * 0.06, R * 1.05
    ImageDraw.Draw(occ).ellipse([cx + ox - rr, cy + oy - rr, cx + ox + rr, cy + oy + rr], fill=255)
    occ = np.asarray(occ.filter(ImageFilter.GaussianBlur(S * 0.055)), float) / 255.0
    crescent = np.clip(disc - occ, 0, 1)                  # crisp outer limb, soft inner terminator

    # --- faint shaded sphere so the full disc reads at large sizes (depth) ---
    d2 = np.clip(np.sqrt((xx - (cx - R * 0.3)) ** 2 + (yy - (cy - R * 0.3)) ** 2) / (R * 1.3), 0, 1)
    sphere_dark = np.array([40, 52, 92], float) * (1 - d2[..., None]) + \
                  np.array([15, 19, 38], float) * d2[..., None]
    canvas = canvas * (1 - disc[..., None]) + sphere_dark * disc[..., None]

    # --- corona glow around the lit crescent ---
    glow = np.asarray(Image.fromarray((crescent * 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(S * 0.05)), float) / 255.0
    corona = np.array([120, 165, 255], float)
    canvas = canvas * (1 - 0.55 * glow[..., None]) + corona * (0.55 * glow[..., None])

    # --- bright crescent on top: radial highlight from the lit limb ---
    d = np.clip(np.sqrt((xx - (cx - R * 0.55)) ** 2 + (yy - (cy - R * 0.2)) ** 2) / (R * 1.7), 0, 1)
    col = np.array([251, 253, 255], float) * (1 - d[..., None]) + \
          np.array([176, 202, 242], float) * d[..., None]
    canvas = canvas * (1 - crescent[..., None]) + col * crescent[..., None]

    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    img.putalpha(squircle_mask(S))
    return img


def make_template(px):
    """Monochrome crescent (alpha) matching the icon, for the menu bar."""
    m = Image.new("L", (px, px), 0)
    d = ImageDraw.Draw(m)
    r, c = px * 0.46, px * 0.5
    d.ellipse([c - r, c - r, c + r, c + r], fill=255)
    ox = r * 0.50
    d.ellipse([c + ox - r * 1.05, c - r * 1.05 - r * 0.06, c + ox + r * 1.05, c + r * 1.05 - r * 0.06], fill=0)
    out = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    out.putalpha(m)
    return out


def main():
    master = render_icon(S)

    # 1024 preview for the README
    os.makedirs(os.path.join(HERE, "docs"), exist_ok=True)
    master.save(os.path.join(HERE, "docs", "icon.png"))

    # full iconset -> run `iconutil -c icns AppIcon.iconset -o AppIcon.icns` after this
    iconset = os.path.join(HERE, "AppIcon.iconset")
    os.makedirs(iconset, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        for sc in (1, 2):
            px = base * sc
            master.resize((px, px), Image.LANCZOS).save(
                os.path.join(iconset, "icon_%dx%d%s.png" % (base, base, "@2x" if sc == 2 else "")))

    # monochrome menu-bar glyph (template)
    make_template(36).save(os.path.join(HERE, "MenuTemplate.png"))
    print("wrote docs/icon.png, AppIcon.iconset, MenuTemplate.png")
    print("now run:  iconutil -c icns AppIcon.iconset -o AppIcon.icns")


if __name__ == "__main__":
    main()
