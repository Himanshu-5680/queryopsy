# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | yes |

## Design

* No backend, no accounts and no network requests: SQL runs in an in-memory SQLite database inside WebAssembly on your device.
* A strict Content-Security-Policy allows only local resources.
* The Android app requests no permissions (not even INTERNET), blocks network loads and disables file access in the WebView.
* Progress is kept only in the browser's `localStorage`.

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's private reporting instead:
[Report a vulnerability](https://github.com/Himanshu-5680/queryopsy/security/advisories/new).

Include steps to reproduce and the affected version or commit. You can expect an acknowledgement within 7 days. Please allow time for a fix before public disclosure.
