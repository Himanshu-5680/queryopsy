# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.0] - 2026-11-14

### Added - native-style app mode
- The Android app, the installed PWA and phones up to 760 px wide now get an **app** instead of a web page (`src/ui/appmode.py`, `src/ui/ios.css`). It uses the same Python engine, cases, progress and DOM ids, so every feature keeps working. The desktop website keeps the case-file dossier.
- Screens: **Cases** home (greeting, progress ring, Continue card, grouped case list), case detail, Investigate, Evidence, Progress and the audit report. Hash routes give each screen a real history entry.
- Large-title navigation bars that collapse into a small centred title on a translucent blurred bar, with a back chevron.
- Bottom **tab bar** with icons and labels (Cases, Investigate, Evidence, Progress). It respects safe-area insets and hides while typing.
- Push/pop slide transitions and an **edge swipe-back** gesture. Android Back closes a sheet, dialog, suggestion list or keyboard first, then pops one screen, then returns to Cases, then leaves the app.
- **Bottom sheets** with a grabber and drag-to-dismiss for the evidence tables, hints and query history.
- A SQL key row with Run above the on-screen keyboard. The editor stays visible above the keyboard (`interactive-widget=resizes-content` plus a visualViewport offset).
- iOS-style segmented controls, switches (haptics, notebook lines), toast pills, 44 px+ targets, 12-16 px corners and the system font stack, with monospace only for SQL.
- Appearance follows the system light/dark setting live. Progress > Appearance lets you pick System, Light or Dark.
- App-like behaviour: no text selection or long-press callouts on chrome, no tap highlight, no pinch zoom, no whole-page rubber band.
- A fast splash screen that matches the Android launch window colour, with live loading status.
- Touch-worded first-run welcome.

### Changed - Android
- Edge-to-edge on Android 11+: transparent status and navigation bars, display-cutout aware, with the bar sizes passed to the page as CSS variables. Bar icons follow the theme. The keyboard resizes only the WebView.
- Older Android versions get solid bars in the app background colour with matching icon colours.
- Haptic feedback through `performHapticFeedback`, so the app still requests **no permissions**.
- Launch window and splash colours: `#F2F1EE` (light) and `#0B0A09` (dark). versionCode 3, signed with the same key, so it upgrades v1.0.x in place and keeps progress.

### Fixed
- Phones: the home page scrolled sideways because the long "Continue: Orientation: First Day at the Desk" button (and the header) could not wrap. Buttons now wrap, the header ellipsises, and `html`/`body` clip horizontal overflow.
- PWA manifest colours match the new launch screen.

### Tests and tools
- `tests/e2e/test_appmode.py`: no horizontal overflow at 360/393/412 px with an Android WebView user agent, in app mode and in website mode. Mobile browsers widen the layout viewport to fit over-wide content, so the test checks against the real viewport width. Also covers app-mode navigation (tabs, push, sheets, run and verdict, Back order, appearance, report), edge swipe-back, first run and non-selectable chrome.
- `tools/check_apk.py` drives the APK payload in app mode with a WebView user agent: onboarding, solve, no overflow, Back pops.
- `tools/contrast_check.py` also checks the app-mode palette in both themes.
- `tools/screenshots.py` captures 393x852 phone shots in light and dark (`docs/screenshots/app/`).


## [1.0.1] - 2026-11-13

### Changed - "Case File" redesign
- New visual identity: every case is a detective case file. **Dossier** (light): manila folder paper on a kraft desk, typewriter type (Courier Prime + Special Elite, bundled locally), CONFIDENTIAL / CLASSIFIED rubber stamps, evidence tags, file numbers, paper clips and redaction bars. **Crime Lab** (dark): night cork evidence board, pinned notes, red string connecting the ER diagram tables, subtle flashlight vignette.
- Findings are now **Exhibits A, B, C...**; solving one stamps **SOLVED** (and the last one **CASE CLOSED**) with a short stamp animation that is switched off under `prefers-reduced-motion`.
- The case list is a **case-files drawer** with folder tabs and a "Case closed" stamp on finished files.
- The audit certificate is now an **Official Forensic Audit Report**: letterhead, report number, case register table, evidence-tag audit record, signature line and verdict stamp.
- New app icon (case folder + magnifier) and matching Android system-bar colours.

### Fixed - layout and overlap
- Results table header painted over the Evidence Room: the bench grid column had an implicit `auto` track whose minimum was the table's min-content width, so wide results pushed the bench under the right panel and the page scrolled sideways (~1800 px at 1024 px). Columns now use `minmax(0, 1fr)`, panels `min-width: 0`, and the table scrolls inside its own pane (`contain: paint`, bounded height, sticky header stays inside it).
- Evidence Room tabs (Tables / ER diagram) were covered by the sticky schema list: the whole panel is now one sticky flex column with its own internal scroll.
- Editor hint bar text was cut off: it now wraps (`min-width: 0`, `overflow-wrap: anywhere`).
- Narrow desktops / tablets (861-1180 px) squeezed three columns: the Evidence Room becomes a slide-in drawer (Evidence button or Alt+E, Escape or Back to close, scrim, focus kept inside while open).
- Short windows (<= 640 px tall, e.g. 1024x450 or 150 % zoom) made sticky panels taller than the screen so their bottoms were unreachable: sticky is disabled there.
- Mobile: table cells could intercept taps on the bottom tab bar; stacking fixed.
- Mobile tab bar disappeared on any short narrow window (zoomed desktop, landscape phone) and stranded the player on one panel: it now hides only while the on-screen keyboard is up (touch device with a focused field).
- Editor line numbers drifted from the text when long lines soft-wrapped: numbering is now wrap-aware and re-measured on resize.
- Active mobile tab had no visible state.

### Fixed - UX, accessibility, Android
- After Run on desktop the verdict could be below the fold: results scroll into view when needed. Previewing a table from the drawer closes it so the rows are visible. Switching mobile tabs starts at the top.
- Android Back now walks back one step at a time: dialog, evidence drawer, autocomplete, mobile tab, then the case list, then leaves the app.
- Evidence Room tabs are real ARIA tabs (tabpanel, roving tabindex, Arrow / Home / End). Mobile switcher uses `aria-pressed` buttons instead of tabs without panels. Verdicts are announced (`role=status`). ER diagram names insert with Enter / Space as well as click.
- Contrast: comment and secondary text raised to at least 4.5:1 in both themes; every text token pair is checked by `tools/contrast_check.py` (also a unit test).
- Certificate could be drawn with fallback fonts before the web fonts loaded; it now redraws once they are ready.
- Touch targets at least 46 px on phones (48 px for the Evidence tabs on touch screens).
- Removed the unused Space Grotesk font files (smaller download); the PWA cache name now follows `version.json` automatically.

### Added
- `tools/layout_audit.py`: opens a busy case at 13 viewports (1024x450 to 1920x1080, phones, tablet) and 5 zoom levels in both themes and reports panel overlaps, clipped text, covered headers/tabs and sideways scrolling.
- `tests/e2e/test_layout.py`: no bounding-box overlap between the main panels, results header stays inside its pane (8 viewports x 2 themes), evidence drawer keyboard + Back behaviour, mobile Back order.
- `tests/test_theme.py`: contrast, bundled fonts, no external CSS assets, reduced-motion support.

## [1.0.0] - 2026-11-12

### Added
- Six investigations (24 levels): Orientation, Funding Forensics, Dark Store Delivery Audit, Shelf Integrity Audit, UPI Fraud Desk, Payroll Leak.
- Python engine on Pyodide 0.29.5 (CPython 3.13 + SQLite in WebAssembly), all assets bundled locally.
- Hash-based validator with row/column diff feedback, friendly SQL errors and a 4 s query guard.
- Editor with highlighting, autocomplete, history and drafts; schema explorer and clickable ER diagram.
- Progressive hints, onboarding, keyboard shortcuts, light/dark themes, mobile tabs.
- On-device audit certificate (PNG and PDF).
- Data pipeline for CSV/XLSX with auto-detection, cleaning and documented planted anomalies; placeholder data until real files are supplied.
- Android WebView app (minSdk 24, no permissions), PWA offline support.
- pytest unit tests, Playwright end-to-end tests, CI, Pages deployment, release workflow and CodeQL.

[Unreleased]: https://github.com/Himanshu-5680/queryopsy/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Himanshu-5680/queryopsy/compare/v1.0.1...v1.1.0
[1.0.1]: https://github.com/Himanshu-5680/queryopsy/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/Himanshu-5680/queryopsy/releases/tag/v1.0.0
