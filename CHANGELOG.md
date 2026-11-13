# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-11-12

### Added
- Six investigations (24 levels): Orientation, Funding Forensics, Dark Store Delivery Audit, Shelf Integrity Audit, UPI Fraud Desk, Payroll Leak.
- Python engine on Pyodide 0.29.5 (CPython 3.13 + SQLite in WebAssembly), all assets bundled locally.
- Hash-based validator with row/column diff feedback, friendly SQL errors and a 4 s query guard.
- Editor with highlighting, autocomplete, history and drafts; schema explorer and clickable ER diagram.
- Progressive hints, onboarding, keyboard shortcuts, light/dark neo-brutalist themes, mobile tabs.
- On-device audit certificate (PNG and PDF).
- Data pipeline for CSV/XLSX with auto-detection, cleaning and documented planted anomalies; placeholder data until real files are supplied.
- Android WebView app (minSdk 24, no permissions), PWA offline support.
- pytest unit tests, Playwright end-to-end tests, CI, Pages deployment, release workflow and CodeQL.

[Unreleased]: https://github.com/Himanshu-5680/queryopsy/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Himanshu-5680/queryopsy/releases/tag/v1.0.0
