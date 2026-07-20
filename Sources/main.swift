import Cocoa
import ServiceManagement

// MARK: - Constants

/// Never fully black: at 100% the slider maps to this alpha so a sliver of the
/// screen is always visible (and the control menu is reachable). 0.92 is far
/// darker than any hardware minimum.
private let kMaxAlpha: CGFloat = 0.92
private let kDefaultsKey = "dimLevel"
private let kBundleID = "com.molanocortes.penumbra"

// MARK: - Overlay window (the click-through dark filter)

/// A borderless, transparent, click-through black window that sits above the
/// menu bar, dock and all app windows but *below* pop-up menus, so this app's
/// own control menu stays readable at any dim level.
final class OverlayWindow: NSWindow {

    init(screen: NSScreen) {
        super.init(contentRect: screen.frame,
                   styleMask: .borderless,
                   backing: .buffered,
                   defer: false)

        isOpaque = false
        backgroundColor = .clear
        hasShadow = false
        ignoresMouseEvents = true          // clicks pass straight through
        isReleasedWhenClosed = false
        // One below pop-up-menu level: covers menu bar + dock + every window,
        // but our NSMenu (drawn at pop-up level) still renders on top of it.
        level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.popUpMenuWindow)) - 1)
        collectionBehavior = [.canJoinAllSpaces, .stationary,
                              .fullScreenAuxiliary, .ignoresCycle]

        let v = NSView(frame: screen.frame)
        v.wantsLayer = true
        v.layer?.backgroundColor = NSColor.black.cgColor
        contentView = v

        setFrame(screen.frame, display: true)
    }

    // Never steal focus.
    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }
}

// MARK: - Control view (title + % + slider) hosted inside the menu

final class ControlView: NSView {
    private let title   = NSTextField(labelWithString: "Penumbra")
    private let percent = NSTextField(labelWithString: "0%")
    private let slider  = NSSlider(value: 0, minValue: 0, maxValue: 100,
                                   target: nil, action: nil)
    /// Called continuously as the user drags. Argument is 0 to 1.
    var onChange: ((CGFloat) -> Void)?

    init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 264, height: 78))

        title.font = .boldSystemFont(ofSize: 13)
        title.frame = NSRect(x: 16, y: 50, width: 170, height: 18)

        percent.font = .monospacedDigitSystemFont(ofSize: 12, weight: .regular)
        percent.textColor = .secondaryLabelColor
        percent.alignment = .right
        percent.frame = NSRect(x: 176, y: 50, width: 72, height: 18)

        slider.frame = NSRect(x: 16, y: 16, width: 232, height: 22)
        slider.isContinuous = true
        slider.target = self
        slider.action = #selector(sliderMoved)

        addSubview(title)
        addSubview(percent)
        addSubview(slider)
    }

    required init?(coder: NSCoder) { nil }

    @objc private func sliderMoved() {
        let v = CGFloat(slider.doubleValue / 100.0)
        percent.stringValue = "\(Int(slider.doubleValue.rounded()))%"
        onChange?(v)
    }

    /// Sync the UI to an external value (0 to 1).
    func set(_ dim: CGFloat) {
        slider.doubleValue = Double(dim * 100)
        percent.stringValue = "\(Int((dim * 100).rounded()))%"
    }
}

// MARK: - App delegate

final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {

    private var overlays: [OverlayWindow] = []
    private let statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private let control = ControlView()
    private var loginItem: NSMenuItem?

    /// Dim fraction, 0 (off) to 1 (max). Mapped to alpha via kMaxAlpha.
    private var dim: CGFloat = 0 {
        didSet {
            applyDim()
            control.set(dim)
            UserDefaults.standard.set(Double(dim), forKey: kDefaultsKey)
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)   // menu-bar-only, no dock icon

        control.onChange = { [weak self] v in self?.dim = v }
        setupStatusItem()
        rebuildOverlays()

        NotificationCenter.default.addObserver(
            self, selector: #selector(screensChanged),
            name: NSApplication.didChangeScreenParametersNotification, object: nil)

        // Restore last level (clamped).
        let saved = UserDefaults.standard.double(forKey: kDefaultsKey)
        dim = min(max(CGFloat(saved), 0), 1)
    }

    // MARK: overlays

    private func rebuildOverlays() {
        overlays.forEach { $0.orderOut(nil) }
        overlays = NSScreen.screens.map { OverlayWindow(screen: $0) }
        applyDim()
    }

    @objc private func screensChanged() { rebuildOverlays() }

    private func applyDim() {
        let a = dim * kMaxAlpha
        for w in overlays {
            if a <= 0.001 {
                w.orderOut(nil)
            } else {
                w.alphaValue = a
                w.orderFrontRegardless()
            }
        }
        updateIcon()
    }

    private func updateIcon() {
        let name: String
        switch dim {
        case ..<0.001: name = "sun.max"
        case ..<0.5:   name = "sun.min"
        default:       name = "moon.fill"
        }
        let img = NSImage(systemSymbolName: name, accessibilityDescription: "Penumbra")
        img?.isTemplate = true
        statusItem.button?.image = img
        statusItem.button?.toolTip = "Penumbra: \(Int((dim * 100).rounded()))%"
    }

    // MARK: menu

    private func setupStatusItem() {
        updateIcon()

        let menu = NSMenu()
        menu.delegate = self

        let controlItem = NSMenuItem()
        controlItem.view = control
        menu.addItem(controlItem)
        menu.addItem(.separator())

        for p in [0, 25, 50, 75, 92] {
            let item = NSMenuItem(title: p == 0 ? "Off" : "\(p)%",
                                  action: #selector(preset(_:)), keyEquivalent: "")
            item.target = self
            item.tag = p
            menu.addItem(item)
        }
        menu.addItem(.separator())

        let login = NSMenuItem(title: "Launch at Login",
                               action: #selector(toggleLogin), keyEquivalent: "")
        login.target = self
        loginItem = login
        menu.addItem(login)
        menu.addItem(.separator())

        let quit = NSMenuItem(title: "Quit Penumbra",
                              action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        quit.target = NSApp
        menu.addItem(quit)

        statusItem.menu = menu
    }

    /// Keep the slider and login checkmark in sync when the menu opens.
    func menuWillOpen(_ menu: NSMenu) {
        control.set(dim)
        if #available(macOS 13.0, *) {
            loginItem?.state = (SMAppService.mainApp.status == .enabled) ? .on : .off
        } else {
            loginItem?.isHidden = true
        }
    }

    @objc private func preset(_ sender: NSMenuItem) {
        dim = min(max(CGFloat(sender.tag) / 100.0, 0), 1)
    }

    @objc private func toggleLogin() {
        guard #available(macOS 13.0, *) else { return }
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            NSLog("Penumbra: launch-at-login toggle failed: \(error)")
        }
    }
}

// MARK: - Entry point

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
