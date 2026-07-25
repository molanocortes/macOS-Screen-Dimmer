#!/usr/bin/env python3
"""
Penumbra: a software brightness filter for macOS.

Lays a click-through black overlay above the menu bar, dock and every window on
every display, so you can dim the screen far below the hardware minimum, and it
keeps dimming when a video goes native fullscreen. It runs menu-bar-only (see the
activation-policy note below) with a native vibrancy control window; the menu-bar
icon opens that window.

Key implementation note: the control window MUST be a plain titled NSWindow
placed *above* the dark overlay. A utility NSPanel silently fails to order in
for this kind of app; do not switch back to one.

Second key note: showing the shade over an app in *native fullscreen* (a video
in YouTube fullscreen) needs two independent things, and a window level alone
buys neither:
  1. Space membership - the collection behaviour must let the window join the
     fullscreen Space (canJoinAllSpaces + fullScreenAuxiliary, plus
     canJoinAllApplications on macOS 13+).
  2. z-order inside that Space - the level must beat the fullscreen window,
     hence NSScreenSaverWindowLevel (1000) rather than the old 100.
macOS can also demote a window while Spaces switch, so both are re-asserted on
every Space change (see _reassert_overlays).

Gate 1 is the one that bit us, and the deciding factor is the ACTIVATION POLICY,
not the level. Measured on macOS 15.7: a Regular (Dock) app never reaches another
app's fullscreen Space, at any level, with any collection behaviour; an Accessory
app reaches it at every level. The privilege is fixed when the window is created,
so the policy must be set BEFORE the overlays are built (a Regular-born window
stays excluded even after the process transforms). Hence the app is menu-bar-only:
it still bounces in the Dock while Python starts up, then drops the icon.

Talks to AppKit through PyObjC at runtime, so it needs no compiler.
"""

import json
import os

import objc

import AppKit
from AppKit import (
    NSApplication, NSApp, NSObject, NSWindow, NSColor, NSScreen, NSView,
    NSStatusBar, NSSlider, NSSegmentedControl, NSTextField, NSFont, NSImage,
    NSVisualEffectView, NSMenu, NSMenuItem, NSAnimationContext, NSEvent,
    NSApplicationActivationPolicyAccessory,
    NSVisualEffectMaterialPopover, NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectStateActive,
    NSWindowStyleMaskBorderless, NSWindowStyleMaskTitled,
    NSWindowStyleMaskClosable, NSWindowStyleMaskFullSizeContentView,
    NSWindowTitleHidden, NSBackingStoreBuffered,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorStationary,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowCollectionBehaviorIgnoresCycle,
    NSVariableStatusItemLength, NSViewWidthSizable, NSViewHeightSizable,
    NSTextAlignmentCenter, NSTextAlignmentLeft, NSTextAlignmentRight,
    NSSegmentSwitchTrackingSelectOne, NSFontWeightSemibold, NSFontWeightMedium,
    NSEventMaskKeyDown, NSEventModifierFlagCommand, NSEventModifierFlagControl,
    NSEventModifierFlagOption, NSApplicationDidChangeScreenParametersNotification,
    NSScreenSaverWindowLevel, NSWorkspace,
    NSWorkspaceActiveSpaceDidChangeNotification,
    NSWorkspaceDidActivateApplicationNotification,
)
from Foundation import (
    NSNotificationCenter, NSDistributedNotificationCenter, NSAttributedString,
)
from PyObjCTools import AppHelper

MAX_ALPHA = 0.92                 # 100% on the slider -> never fully black
# Screen-saver level (1000): the only level that also covers another app's
# native-fullscreen window. Anything in the 100s loses to fullscreen video.
OVERLAY_LEVEL = int(NSScreenSaverWindowLevel)
MENU_LEVEL = 100                 # temporary drop so our own menus stay readable
PANEL_LEVEL = OVERLAY_LEVEL + 2  # control window sits above the overlay

# macOS 13+: "for floating windows and system overlays". Absent on older
# systems, where the mask below still works, just without this bit.
_CAN_JOIN_ALL_APPLICATIONS = getattr(
    AppKit, "NSWindowCollectionBehaviorCanJoinAllApplications", 0)

# Gate 1: Space membership. Never add fullScreenNone or moveToActiveSpace here,
# they cancel the effect.
OVERLAY_BEHAVIOR = (
    NSWindowCollectionBehaviorCanJoinAllSpaces
    | NSWindowCollectionBehaviorStationary
    | NSWindowCollectionBehaviorFullScreenAuxiliary
    | NSWindowCollectionBehaviorIgnoresCycle
    | _CAN_JOIN_ALL_APPLICATIONS)

# The control window follows the shade into fullscreen Spaces, so the slider is
# reachable without leaving the video.
PANEL_BEHAVIOR = (
    NSWindowCollectionBehaviorCanJoinAllSpaces
    | NSWindowCollectionBehaviorFullScreenAuxiliary)
ACTIVATE_NOTE = "com.molanocortes.penumbra.activate"
APP_NAME = "Penumbra"
VERSION = "1.0"
PRESET_VALUES = [0, 25, 50, 75, 92]
PRESET_LABELS = ["Off", "25", "50", "75", "Max"]

# Settings live in a plain JSON file, deterministic regardless of how the app
# is launched (NSUserDefaults domain resolution is ambiguous when the running
# bundle id equals the suite name).
SETTINGS_PATH = os.path.expanduser("~/Library/Application Support/Penumbra/settings.json")
_LEGACY_SETTINGS = os.path.expanduser("~/Library/Application Support/ScreenDimmer/settings.json")


def load_settings():
    for p in (SETTINGS_PATH, _LEGACY_SETTINGS):   # prefer new; migrate old level/position
        try:
            with open(p) as f:
                return json.load(f)
        except Exception:
            continue
    return {}


def save_settings(d):
    try:
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        tmp = SETTINGS_PATH + ".tmp"
        with open(tmp, "w") as f:
            json.dump(d, f)
        os.replace(tmp, SETTINGS_PATH)
    except Exception:
        pass


def label(text, frame, *, size=12, weight=None, align=None, color=None):
    f = NSTextField.alloc().initWithFrame_(frame)
    f.setStringValue_(text)
    f.setEditable_(False); f.setSelectable_(False)
    f.setBezeled_(False); f.setDrawsBackground_(False)
    f.setFont_(NSFont.systemFontOfSize_weight_(size, weight) if weight is not None
               else NSFont.systemFontOfSize_(size))
    if align is not None:
        f.setAlignment_(align)
    f.setTextColor_(color if color is not None else NSColor.labelColor())
    return f


def screen_key(screen):
    """CGDirectDisplayID, so overlays survive hotplug and resolution changes."""
    try:
        n = screen.deviceDescription().objectForKey_("NSScreenNumber")
        if n is not None:
            return int(n)
    except Exception:
        pass
    return None


def configure_overlay(w, level=OVERLAY_LEVEL):
    """Re-assertable window traits. setLevel_ takes an int, never a float."""
    w.setLevel_(int(level))
    w.setCollectionBehavior_(OVERLAY_BEHAVIOR)
    w.setIgnoresMouseEvents_(True)          # clicks pass straight through
    w.setCanHide_(False)                    # survives Cmd-H
    w.setHidesOnDeactivate_(False)          # survives losing focus


def make_overlay(screen):
    frame = screen.frame()                  # frame(), never visibleFrame()
    w = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    w.setOpaque_(False)
    w.setBackgroundColor_(NSColor.blackColor())
    w.setAlphaValue_(0.0)
    w.setHasShadow_(False)
    configure_overlay(w)                    # so the menu bar / notch stay covered
    w.setReleasedWhenClosed_(False)
    w.setFrame_display_(frame, True)
    return w


class DimmerDelegate(NSObject):

    # ---- lifecycle ---------------------------------------------------------

    def applicationDidFinishLaunching_(self, note):
        # Menu-bar-only, and set FIRST: every window built below inherits its
        # fullscreen-Space privilege from the policy in force at creation time.
        # Regular here = the shade silently vanishes over fullscreen video.
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
        icon = self._app_icon()
        if icon is not None:
            NSApp.setApplicationIconImage_(icon)

        self.settings = load_settings()
        self.dim = min(max(float(self.settings.get("dimLevel", 0.0)), 0.0), 1.0)
        self.overlays = {}              # CGDirectDisplayID -> NSWindow
        self.level = OVERLAY_LEVEL

        self._build_main_menu()
        self._build_status_item()
        self._build_panel()
        self._rebuild_overlays()

        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "screensChanged:",
            NSApplicationDidChangeScreenParametersNotification, None)
        # Fullscreen enter/exit creates a Space *after* the overlay was ordered
        # in, and macOS can demote windows across the transition. Re-assert.
        wsc = NSWorkspace.sharedWorkspace().notificationCenter()
        for name in (NSWorkspaceActiveSpaceDidChangeNotification,
                     NSWorkspaceDidActivateApplicationNotification):
            wsc.addObserver_selector_name_object_(self, "spaceChanged:", name, None)
        NSDistributedNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "reactivate:", ACTIVATE_NOTE, None)
        self._install_key_monitor()

        self._apply(animated=False)
        self.show_panel()

    def applicationShouldHandleReopen_hasVisibleWindows_(self, app, flag):
        self.show_panel()               # Dock-icon click / relaunch re-shows it
        return True

    def applicationShouldTerminateAfterLastWindowClosed_(self, app):
        return False                    # closing the window never quits the app

    def applicationWillTerminate_(self, note):
        o = self.panel.frame().origin
        self.settings.update(dimLevel=self.dim, winX=float(o.x), winY=float(o.y))
        save_settings(self.settings)

    # ---- overlays ----------------------------------------------------------

    @objc.python_method
    def _windows(self):
        return list(self.overlays.values())

    def _rebuild_overlays(self):
        """Keyed by display ID: keep the window a display already has, close the
        rest. Ordering out without closing leaked one window per display change."""
        stale = dict(self.overlays)
        fresh = {}
        for i, s in enumerate(NSScreen.screens()):
            key = screen_key(s)
            if key is None:
                key = "idx%d" % i            # nameless display: fall back to order
            w = stale.pop(key, None)
            if w is None:
                w = make_overlay(s)
            else:
                configure_overlay(w, self.level)
                w.setFrame_display_(s.frame(), True)
            fresh[key] = w
        for w in stale.values():
            w.orderOut_(None)
            w.close()
        self.overlays = fresh
        self._apply(animated=False)

    def screensChanged_(self, note):
        self._rebuild_overlays()

    def spaceChanged_(self, note):
        self._reassert_overlays()
        # The Space transition finishes after the notification; do it again once
        # the new Space actually exists.
        AppHelper.callLater(0.35, self._reassert_overlays)

    def _reassert_overlays(self):
        """Idempotent: re-apply level + collection behaviour and re-order in."""
        visible = self.dim * MAX_ALPHA > 0.001
        for w in self._windows():
            configure_overlay(w, self.level)
            if visible:
                w.orderFrontRegardless()

    @objc.python_method
    def _apply(self, animated=False):
        a = self.dim * MAX_ALPHA
        if animated:
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(0.18)
            for w in self._windows():
                if a > 0.001:
                    w.orderFrontRegardless()
                w.animator().setAlphaValue_(a)
            NSAnimationContext.endGrouping()
            if a <= 0.001:
                AppHelper.callLater(0.22, self._hide_zero_overlays)
        else:
            for w in self._windows():
                if a <= 0.001:
                    w.orderOut_(None)
                else:
                    w.setAlphaValue_(a); w.orderFrontRegardless()
        self.settings["dimLevel"] = self.dim
        save_settings(self.settings)
        self._update_ui()

    def _hide_zero_overlays(self):
        if self.dim * MAX_ALPHA <= 0.001:
            for w in self._windows():
                w.orderOut_(None)

    # ---- control window ----------------------------------------------------

    def _build_panel(self):
        W, H = 360, 240
        self.panel = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            ((0, 0), (W, H)),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
            | NSWindowStyleMaskFullSizeContentView,
            NSBackingStoreBuffered, False)
        self.panel.setTitle_(APP_NAME)
        self.panel.setTitleVisibility_(NSWindowTitleHidden)
        self.panel.setTitlebarAppearsTransparent_(True)
        self.panel.setMovableByWindowBackground_(True)
        self.panel.setLevel_(int(PANEL_LEVEL))
        self.panel.setCollectionBehavior_(PANEL_BEHAVIOR)   # reachable inside fullscreen
        self.panel.setReleasedWhenClosed_(False)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(NSColor.clearColor())
        self.panel.setDelegate_(self)

        vev = NSVisualEffectView.alloc().initWithFrame_(((0, 0), (W, H)))
        vev.setMaterial_(NSVisualEffectMaterialPopover)
        vev.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        vev.setState_(NSVisualEffectStateActive)
        vev.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        self.panel.setContentView_(vev)

        self.pct_label = label("0%", ((20, 168), (320, 48)), size=38,
                               weight=NSFontWeightSemibold, align=NSTextAlignmentCenter,
                               color=NSColor.controlAccentColor())
        vev.addSubview_(self.pct_label)
        vev.addSubview_(label("Software brightness filter", ((20, 148), (320, 16)),
                              size=11, align=NSTextAlignmentCenter,
                              color=NSColor.secondaryLabelColor()))

        self.slider = NSSlider.alloc().initWithFrame_(((24, 106), (312, 24)))
        self.slider.setMinValue_(0.0); self.slider.setMaxValue_(100.0)
        self.slider.setNumberOfTickMarks_(11)
        self.slider.setContinuous_(True)
        self.slider.setTarget_(self); self.slider.setAction_("sliderChanged:")
        vev.addSubview_(self.slider)

        vev.addSubview_(label("BRIGHT", ((24, 88), (90, 13)), size=9,
                              weight=NSFontWeightMedium, align=NSTextAlignmentLeft,
                              color=NSColor.tertiaryLabelColor()))
        vev.addSubview_(label("DARK", ((246, 88), (90, 13)), size=9,
                              weight=NSFontWeightMedium, align=NSTextAlignmentRight,
                              color=NSColor.tertiaryLabelColor()))

        self.segmented = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            PRESET_LABELS, NSSegmentSwitchTrackingSelectOne, self, "segmentChanged:")
        self.segmented.setFrame_(((20, 52), (320, 26)))
        vev.addSubview_(self.segmented)

        vev.addSubview_(label("↑↓ adjust   ·   1–5 presets   ·   esc hides   ·   ⌘Q quits",
                              ((16, 20), (328, 15)), size=10, align=NSTextAlignmentCenter,
                              color=NSColor.tertiaryLabelColor()))

        if "winX" in self.settings and "winY" in self.settings:
            self.panel.setFrameOrigin_((self.settings["winX"], self.settings["winY"]))
        else:
            self.panel.center()

    def show_panel(self):
        NSApp.activateIgnoringOtherApps_(True)
        self.panel.makeKeyAndOrderFront_(None)
        self.panel.orderFrontRegardless()
        self.panel.makeFirstResponder_(self.slider)

    def reactivate_(self, note):
        self.show_panel()

    def windowShouldClose_(self, sender):
        sender.orderOut_(None)          # hide instead of destroy
        return False

    def windowDidMove_(self, note):
        o = self.panel.frame().origin
        self.settings["winX"] = float(o.x)
        self.settings["winY"] = float(o.y)
        save_settings(self.settings)

    # ---- menu bar + app menu ----------------------------------------------

    def _build_status_item(self):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(
            NSVariableStatusItemLength)
        btn = self.status_item.button()
        btn.setTarget_(self); btn.setAction_("showPanel:")
        img = self._menu_image()
        if img is not None:
            btn.setImage_(img)          # template crescent, matches the app icon
        else:
            btn.setTitle_("◐")

    def _build_main_menu(self):
        main = NSMenu.alloc().init()
        app_item = NSMenuItem.alloc().init()
        main.addItem_(app_item)
        m = NSMenu.alloc().init()
        about = m.addItemWithTitle_action_keyEquivalent_(
            "About " + APP_NAME, "showAbout:", "")
        about.setTarget_(self)
        m.addItem_(NSMenuItem.separatorItem())
        m.addItemWithTitle_action_keyEquivalent_("Hide " + APP_NAME, "hide:", "h")
        m.addItem_(NSMenuItem.separatorItem())
        m.addItemWithTitle_action_keyEquivalent_("Quit " + APP_NAME, "terminate:", "q")
        m.setDelegate_(self)            # drop the shade while this menu is open
        app_item.setSubmenu_(m)
        NSApp.setMainMenu_(main)

    # Menus draw at level 101, below the shade at 1000, so our own app menu
    # would be dimmed into unreadability. Duck under it while it is tracking.
    def menuWillOpen_(self, menu):
        self.level = MENU_LEVEL
        self._reassert_overlays()

    def menuDidClose_(self, menu):
        self.level = OVERLAY_LEVEL
        self._reassert_overlays()

    def showPanel_(self, sender):
        self.show_panel()

    def showAbout_(self, sender):
        opts = {
            "ApplicationName": APP_NAME,
            "ApplicationVersion": VERSION,
            "Version": VERSION,
            "Credits": NSAttributedString.alloc().initWithString_(
                "A software brightness filter.\nDim your screen below the hardware minimum."),
        }
        icon = self._app_icon()
        if icon is not None:
            opts["ApplicationIcon"] = icon
        NSApp.activateIgnoringOtherApps_(True)
        NSApp.orderFrontStandardAboutPanelWithOptions_(opts)

    # ---- actions -----------------------------------------------------------

    def sliderChanged_(self, sender):
        self.dim = min(max(sender.doubleValue() / 100.0, 0.0), 1.0)
        self._apply(animated=False)     # responsive while dragging

    def segmentChanged_(self, sender):
        i = sender.selectedSegment()
        if 0 <= i < len(PRESET_VALUES):
            self.dim = PRESET_VALUES[i] / 100.0
            self._apply(animated=True)

    @objc.python_method
    def _nudge(self, delta):
        self.dim = min(max(self.dim + delta, 0.0), 1.0)
        self._apply(animated=False)

    def _update_ui(self):
        pct = int(round(self.dim * 100))
        if getattr(self, "slider", None) is not None:
            self.slider.setDoubleValue_(self.dim * 100)
            self.pct_label.setStringValue_("%d%%" % pct)
            self.segmented.setSelectedSegment_(
                PRESET_VALUES.index(pct) if pct in PRESET_VALUES else -1)
        self.status_item.button().setToolTip_("%s: %d%%" % (APP_NAME, pct))

    # ---- keyboard ----------------------------------------------------------

    def _install_key_monitor(self):
        def handler(event):
            if not self.panel.isKeyWindow():
                return event
            mods = event.modifierFlags()
            if mods & NSEventModifierFlagCommand:
                # A menu-bar-only app has no menu bar, so the main menu's key
                # equivalents never fire. Honour the two the panel advertises.
                ch = (event.charactersIgnoringModifiers() or "").lower()
                if ch == "q":
                    NSApp.terminate_(None); return None
                if ch == "w":
                    self.panel.orderOut_(None); return None
                return event
            if mods & (NSEventModifierFlagControl | NSEventModifierFlagOption):
                return event
            code = event.keyCode()
            if code == 53:                          # esc -> hide
                self.panel.orderOut_(None); return None
            if code in (123, 125):                  # left / down
                self._nudge(-0.02); return None
            if code in (124, 126):                  # right / up
                self._nudge(0.02); return None
            ch = event.charactersIgnoringModifiers()
            if ch in ("1", "2", "3", "4", "5"):
                self.dim = PRESET_VALUES[int(ch) - 1] / 100.0
                self._apply(animated=True); return None
            return event
        self._key_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, handler)

    # ---- helpers -----------------------------------------------------------

    def _app_icon(self):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AppIcon.icns")
        return NSImage.alloc().initWithContentsOfFile_(p) if os.path.exists(p) else None

    def _menu_image(self):
        """Monochrome crescent for the menu bar (template -> adapts to light/dark)."""
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "MenuTemplate.png")
        img = NSImage.alloc().initWithContentsOfFile_(p) if os.path.exists(p) else None
        if img is None:                                  # fall back to an SF Symbol crescent
            img = NSImage.imageWithSystemSymbolName_accessibilityDescription_("moon.fill", APP_NAME)
        if img is not None:
            img.setSize_((18, 18))                       # menu-bar point size (@2x source)
            img.setTemplate_(True)
        return img


def _single_instance_or_exit():
    import sys
    import fcntl
    path = os.path.expanduser("~/Library/Caches/com.molanocortes.penumbra.lock")
    fh = open(path, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        NSDistributedNotificationCenter.defaultCenter() \
            .postNotificationName_object_userInfo_deliverImmediately_(
                ACTIVATE_NOTE, None, None, True)
        sys.exit(0)
    _single_instance_or_exit._fh = fh


def main():
    _single_instance_or_exit()
    app = NSApplication.sharedApplication()
    delegate = DimmerDelegate.alloc().init()
    app.setDelegate_(delegate)
    main._delegate = delegate
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
