#!/usr/bin/env python3
"""
render_stack.py - the window-level diagram in the README's "How it works".

Draws the macOS window stack as stacked planes, with the levels as AppKit and
CoreGraphics define them, and shows where Penumbra's two windows sit in it. One
light and one dark SVG, chosen by prefers-color-scheme through <picture>. Same
palette and type as the header band. No script, no web fonts, no external refs.

Usage: python3 tools/render_stack.py      (writes docs/stack-{light,dark}.svg)
"""

from pathlib import Path

W, H = 1000, 380
MONO = ('font-family="ui-monospace,SFMono-Regular,SF Mono,Menlo,'
        'Consolas,monospace"')

THEMES = {
    "light": dict(ink="#191713", muted="#6e6b62", line="#c6c1b2",
                  faint="#dcd6c8", accent="#d94e12", fill="#f1efe9"),
    "dark":  dict(ink="#f0ede6", muted="#8f887c", line="#4a443b",
                  faint="#3d3831", accent="#ff7a3d", fill="#1b1815"),
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


def txt(x, y, s, fill, size=10, anchor="start", ls=0.8, weight=None):
    w = f' font-weight="{weight}"' if weight else ""
    return (f'<text x="{x}" y="{y}" {MONO} font-size="{size}" letter-spacing="{ls}" '
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
    o.append(txt(0, 14, "WINDOW LEVEL, LOW TO HIGH", c["muted"], 9, ls=1.6))

    lx = X0 + PW + SKEW + 34                 # label column
    for i, (name, level, note, kind) in enumerate(LAYERS):
        y = BASE - i * STEP
        hot = kind != "sys"
        if kind == "shade":
            o.append(plane(y, c["accent"], c["ink"] if theme == "light" else "#000000",
                           0.62, 1.6))
        elif kind == "own":
            o.append(plane(y, c["accent"], c["fill"], 1, 1.4))
        else:
            o.append(plane(y, c["line"], c["fill"], 1, 1.2))
        my = y - PH / 2
        o.append(f'<path d="M{X0 + PW + SKEW / 2 + 6} {my}H{lx - 8}" stroke="'
                 f'{c["accent"] if hot else c["line"]}" stroke-width="1"/>')
        o.append(txt(lx + 86, my - 1, level, c["accent"] if hot else c["ink"], 11,
                     "end", 0.4, 600))
        o.append(txt(lx + 100, my - 1, name.upper(), c["accent"] if hot else c["ink"], 10.5,
                     ls=1.3, weight=600))
        o.append(txt(lx + 100, my + 13, note, c["muted"], 9.5, ls=0.3))

    # a click, falling straight through the shade to the app underneath
    cx = X0 + SKEW / 2 + 84
    top, shade_y, bottom = BASE - 5 * STEP + 5, BASE - 4 * STEP, BASE - PH / 2
    o.append(f'<path d="M{cx} {top}V{bottom - 3}" stroke="{c["accent"]}" stroke-width="1.4" '
             f'stroke-dasharray="4 3" marker-end="url(#c{theme})"/>')
    o.append(f'<circle cx="{cx}" cy="{shade_y - PH / 2}" r="4.5" fill="{c["fill"]}" '
             f'stroke="{c["accent"]}" stroke-width="1.4"/>')
    o.append(txt(X0, BASE + 28, "A CLICK FALLS THROUGH THE SHADE (ignoresMouseEvents) "
                 "AND LANDS ON THE APP BELOW", c["muted"], 9, ls=1.2))
    o.append("</svg>")
    return "".join(o)


if __name__ == "__main__":
    docs = Path(__file__).resolve().parent.parent / "docs"
    for theme in THEMES:
        (docs / f"stack-{theme}.svg").write_text(build(theme), encoding="utf-8")
    print("wrote stack-light.svg, stack-dark.svg")
