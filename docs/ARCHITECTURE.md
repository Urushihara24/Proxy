# Architecture

## Overview

The application consists of three main modules:

- `desktop_proxy_launcher.py` — GUI, user-flow business logic and asynchronous tasks.
- `proxy_seller_client.py` — Proxy-Seller API HTTP client, response normalization and error handling.
- `system_proxy.py` — enables/disables the system proxy on macOS and Windows.

Entry point: `app.py`.

## Data flow

1. The user configures parameters in the UI.
2. The GUI calls `ProxySellerClient` in a background worker thread.
3. For a paid flow:
   - `order/calc`,
   - `order/make`,
   - poll `proxy/list/{type}` until an active proxy appears.
4. The proxy configuration is saved as JSON.
5. The proxy is applied to the operating system through `apply_system_proxy`.
6. Status and logs are updated in the UI.

## Asynchronous model

- Network and system operations run in the background with `threading.Thread`.
- Results return to the main thread through an event queue.
- This prevents the GUI from freezing during API requests.

## Local storage

No database is used. Application data is stored in `~/.proxy-desktop-launcher`:

- `settings.json`: API key and selected parameters.
- `last_proxy.json`: last connected proxy.
- `generated_proxy_configs/*.json`: generated-configuration history.
- `app_debug.log`: technical log.

## Platform layer

### macOS

- Uses `networksetup`.
- HTTP mode enables `webproxy` and `securewebproxy`.
- SOCKS5 mode enables `socksfirewallproxy`.

### Windows

- Updates registry values under:
  - `HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings`
- Calls `InternetSetOptionW` to notify the operating system that proxy settings changed.

## Limitations

- Only macOS and Windows are supported.
- Linux is not supported in this version.
- On Windows, `user:pass` authentication is not stored globally as a system credential cache.
