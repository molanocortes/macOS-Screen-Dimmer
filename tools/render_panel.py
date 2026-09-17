#!/usr/bin/env python3
"""
render_panel.py - render Penumbra's control window to PNG, off screen.

Builds the same AppKit views penumbra.py builds (same frames, fonts, controls),
sets a dim level, and captures them at 2x with cacheDisplayInRect. Nothing is
shown on screen and no screen-recording permission is needed. The only stand-in
is the background: the live window uses a behind-window blur material, which has
nothing to blur off screen, so a flat dark fill takes its place.

Usage: python3 tools/render_panel.py OUTDIR 0 25 50 ...
"""

import sys
from pathlib import Path

from AppKit import (
    NSApplication, NSAppearance, NSBitmapImageRep, NSBox, NSBoxCustom, NSColor,
    NSFontWeightMedium, NSFontWeightSemibold, NSPNGFileType, NSSegmentedControl,
    NSSegmentSwitchTrackingSelectOne, NSSlider, NSTextAlignmentCenter,
    NSTextAlignmentLeft, NSTextAlignmentRight, NSView, NSWindow,
    NSBackingStoreBuffered, NSWindowStyleMaskBorderless,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from penumbra import PRESET_LABELS, PRESET_VALUES, label   # noqa: E402

W, H = 360, 240


def build(pct):
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        ((0, 0), (W, H)), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    win.setAppearance_(NSAppearance.appearanceNamed_("NSAppearanceNameDarkAqua"))
    root = NSBox.alloc().initWithFrame_(((0, 0), (W, H)))
    root.setBoxType_(NSBoxCustom)
    root.setBorderWidth_(0)
    root.setTitlePosition_(0)
    root.setContentViewMargins_((0, 0))
    root.setFillColor_(NSColor.colorWithSRGBRed_green_blue_alpha_(0.165, 0.165, 0.175, 1))
    win.setContentView_(root)
    v = root.contentView()

    v.addSubview_(label("%d%%" % pct, ((20, 168), (320, 48)), size=38,
                        weight=NSFontWeightSemibold, align=NSTextAlignmentCenter,
                        color=NSColor.controlAccentColor()))
    v.addSubview_(label("Software brightness filter", ((20, 148), (320, 16)),
                        size=11, align=NSTextAlignmentCenter,
                        color=NSColor.secondaryLabelColor()))
    s = NSSlider.alloc().initWithFrame_(((24, 106), (312, 24)))
    s.setMinValue_(0.0); s.setMaxValue_(100.0)
    s.setNumberOfTickMarks_(11)
    s.setDoubleValue_(pct)
    v.addSubview_(s)
    v.addSubview_(label("BRIGHT", ((24, 88), (90, 13)), size=9,
                        weight=NSFontWeightMedium, align=NSTextAlignmentLeft,
                        color=NSColor.tertiaryLabelColor()))
    v.addSubview_(label("DARK", ((246, 88), (90, 13)), size=9,
                        weight=NSFontWeightMedium, align=NSTextAlignmentRight,
                        color=NSColor.tertiaryLabelColor()))
    seg = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
        PRESET_LABELS, NSSegmentSwitchTrackingSelectOne, None, None)
    seg.setFrame_(((20, 52), (320, 26)))
    seg.setSelectedSegment_(PRESET_VALUES.index(pct) if pct in PRESET_VALUES else -1)
    v.addSubview_(seg)
    v.addSubview_(label("↑↓ adjust   ·   1–5 presets   ·   esc hides   ·   ⌘Q quits",
                        ((16, 20), (328, 15)), size=10, align=NSTextAlignmentCenter,
                        color=NSColor.tertiaryLabelColor()))
    return win, root


def render(pct, path, scale=2):
    win, root = build(pct)
    root.layoutSubtreeIfNeeded()
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, W * scale, H * scale, 8, 4, True, False, "NSCalibratedRGBColorSpace", 0, 0)
    rep.setSize_((W, H))
    root.cacheDisplayInRect_toBitmapImageRep_(root.bounds(), rep)
    rep.representationUsingType_properties_(NSPNGFileType, None).writeToFile_atomically_(
        str(path), True)


if __name__ == "__main__":
    NSApplication.sharedApplication()
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    for a in sys.argv[2:]:
        render(int(a), out / ("panel-%03d.png" % int(a)))
        print("panel", a)
