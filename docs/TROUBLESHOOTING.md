# Troubleshooting

## 1) Countries or tariffs do not refresh

Check that:

- the API key is correct;
- internet access and `proxy-seller.com` are available;
- the application log (`Журнал`) does not show an API error.

Also inspect the latest lines in:

- `~/.proxy-desktop-launcher/app_debug.log`

## 2) `Купить и подключить` does not continue

Common causes:

- no country/period selected, or no tariff selected for `resident`/`scraper`;
- invalid quantity for the selected proxy type;
- operator/rotation not selected for `mobile`;
- insufficient account balance.

## 3) The proxy was purchased but not applied to the system

Check that:

- the application has permission to change system settings;
- active network services exist on macOS;
- corporate policy is not blocking changes to proxy settings.

Retry with:

- `Подключить купленный` or `Подключить последний`.

## 4) Windows applications ask for username/password

This is expected for some applications.

- Windows system proxy settings do not always store global credentials.
- Use the username/password from the generated JSON configuration or configure authentication directly in the target application.

## 5) Scrolling does not work

The application supports:

- mouse wheel;
- trackpad / macOS gesture scrolling;
- vertical scrollbars in the main window and event log.

If scrolling still does not respond:

- click inside the list/log area and try again;
- verify that the application window has focus;
- restart the application.

## 6) Logs and configuration files

- Debug log: `~/.proxy-desktop-launcher/app_debug.log`
- Last proxy: `~/.proxy-desktop-launcher/last_proxy.json`
- Saved configurations: `~/.proxy-desktop-launcher/generated_proxy_configs/`

## 7) Clean start

1. Close the application.
2. Delete or rename `~/.proxy-desktop-launcher/`.
3. Start the application again.

This resets the saved API key, form parameters and last-proxy state.

> The application UI is currently Russian, so UI labels above are kept exactly as displayed in the product.
