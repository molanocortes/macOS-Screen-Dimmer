#!/usr/bin/env python3
"""
render_stack.py - the window-level diagram in the README's "How it works".

Draws the macOS window stack as stacked planes, with the levels as AppKit and
CoreGraphics define them, and shows where Penumbra's two windows sit in it. One
light and one dark SVG, chosen by prefers-color-scheme through <picture>, in the
app's own colours: neutral greys and the system blue of the control window. No
script, no web fonts, no external refs.

Usage: python3 tools/render_stack.py      (writes docs/stack-{light,dark}.svg)
"""

from pathlib import Path

W, H = 860, 380
SANS = ('font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,'
        'Arial,sans-serif"')

THEMES = {
    "light": dict(ink="#1d1d1f", muted="#6e6e73", line="#c7c7cc",
                  accent="#0a6cff", fill="#f5f5f7"),
    "dark":  dict(ink="#f5f5f7", muted="#98989d", line="#48484a",
                  accent="#4c9dff", fill="#1c1c1e"),
}

# bottom to top: (name, level, note, kind)
LAYERS = [
    ("app windows",     "0",    "NSNormalWindowLevel  ·  full-screen Spaces included", "sys"),
    ("Dock",            "20",   "NSDockWindowLevel", "sys"),
    ("menu bar",        "24",   "NSMainMenuWindowLevel", "sys"),
    ("open menus",      "101",  "NSPopUpMenuWindowLevel", "sys"),
    ("Penumbra shade",  "1000", "NSScreenSaverWindowLevel  ·  one black window per display", "shade"),
    ("control window",  "1002", "two above the shade, so the slider is never dimmed", "own"),
    ("cursor",          "2147483630", "kCGCursorWindowLevel  ·  above every window, never dimmed", "sys"),
]

X0, PW, SKEW, PH, STEP, BASE = 40, 250, 78, 30, 42, 330


def txt(x, y, s, fill, size=10, anchor="start", ls=0, weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" {SANS} font-size="{size}" letter-spacing="{ls}" '
            f'text-anchor="{anchor}" fill="{fill}"{w}>{s}</text>')


def plane(y, stroke, fill, fo, sw):
    pts = f"{X0},{y} {X0 + PW},{y} {X0 + PW + SKEW},{y - PH} {X0 + SKEW},{y - PH}"
    return (f'<polygon points="{pts}" fill="{fill}" fill-opacity="{fo}" '
            f'stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round"/>')


def build(theme):
    c = THEMES[theme]
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
         f'height="{H}" fill="none" role="img" aria-label="The macOS window stack. '
         f'Penumbra\'s shade sits at level 1000, above app windows, the Dock, the menu bar '
         f'and open menus. Its control window is at 1002 and the cursor is above '
         f'everything. Clicks pass through the shade.">',
         f'<defs><marker id="c{theme}" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" '
         f'markerHeight="7" orient="auto"><path d="M0 1L7 4L0 7z" '
         f'fill="{c["accent"]}"/></marker></defs>']
    o.append(txt(0, 14, "Window level, low to high", c["muted"], 11))

    lx = X0 + PW + SKEW + 34                 # label column
    for i, (name, level, note, kind) in enumerate(LAYERS):
        y = BASE - i * STEP
        hot = kind != "sys"
        if kind == "shade":
            o.append(plane(y, c["accent"], "#000000", 0.78, 1.6))
        elif kind == "own":
            o.append(plane(y, c["accent"], c["fill"], 1, 1.4))
        else:
            o.append(plane(y, c["line"], c["fill"], 1, 1.2))
        my = y - PH / 2
        o.append(f'<path d="M{X0 + PW + SKEW / 2 + 6} {my}H{lx - 8}" stroke="'
                 f'{c["accent"] if hot else c["line"]}" stroke-width="1"/>')
        o.append(txt(lx + 86, my - 1, level, c["accent"] if hot else c["ink"], 12,
                     "end", 0, 600))
        o.append(txt(lx + 100, my - 1, name[0].upper() + name[1:], c["accent"] if hot else c["ink"],
                     12, weight=600))
        o.append(txt(lx + 100, my + 14, note, c["muted"], 10.5))

    # a click, falling straight through the shade to the app underneath
    cx = X0 + SKEW / 2 + 84
    top, shade_y, bottom = BASE - 5 * STEP + 5, BASE - 4 * STEP, BASE - PH / 2
    o.append(f'<path d="M{cx} {top}V{bottom - 3}" stroke="{c["accent"]}" stroke-width="1.4" '
             f'stroke-dasharray="4 3" marker-end="url(#c{theme})"/>')
    o.append(f'<circle cx="{cx}" cy="{shade_y - PH / 2}" r="4.5" fill="{c["fill"]}" '
             f'stroke="{c["accent"]}" stroke-width="1.4"/>')
    o.append(txt(X0, BASE + 28, "A click falls through the shade (ignoresMouseEvents) "
                 "and lands on the app below.", c["muted"], 11))
    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    docs = Path(__file__).resolve().parent.parent / "docs"
    for theme in THEMES:
        (docs / f"stack-{theme}.svg").write_text(build(theme), encoding="utf-8")
    print("wrote stack-light.svg, stack-dark.svg")
