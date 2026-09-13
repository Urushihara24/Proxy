# Proxy Seller Desktop Launcher

Desktop GUI application for macOS and Windows that automates work with Proxy-Seller:

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tkinter](https://img.shields.io/badge/Tkinter-Desktop_GUI-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://docs.python.org/3/library/tkinter.html)
[![Requests](https://img.shields.io/badge/Requests-HTTP-2CA5E0?style=for-the-badge&logo=python&logoColor=white)](https://requests.readthedocs.io/)
[![Windows](https://img.shields.io/badge/Windows-Supported-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![macOS](https://img.shields.io/badge/macOS-Supported-000000?style=for-the-badge&logo=apple&logoColor=white)](https://www.apple.com/macos/)
[![pytest](https://img.shields.io/badge/pytest-Tested-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org/)

</div>

- select proxy type, country, period or tariff;
- calculate and create an order through the API;
- wait for proxy activation;
- apply the proxy automatically to the operating system;
- reconnect a previously purchased proxy.

The goal is to let the user complete the entire workflow through the GUI without manually generating or copying proxy configurations in a terminal.

## Implemented functionality

- Complete GUI flow for `ipv4`, `ipv6`, `mobile`, `isp`, `mix`, `mix_isp`, `resident`, and `scraper`.
- Reference-data loading from the API: countries, periods and tariffs.
- Pre-purchase constraint validation:
  - `ipv6`: minimum quantity;
  - `mix`/`mix_isp`: allowed quantities;
  - `mobile`: required `service/operator/rotation`.
- Additional order parameters:
  - `paymentId` (`1` balance, `43` card),
  - `authorization` (IP authorization),
  - `generateAuth` (`Y/N`),
  - `customTargetName`.
- Active-proxy filtering by `orderId` or `baseOrderNumber`.
- Resident configuration issuance without a new purchase through the API TOOL list when an active package still has traffic.
- UI actions:
  - `Купить и подключить` — buy and connect;
  - `Подключить купленный` — connect an already purchased proxy;
  - `Подключить последний` — reconnect the last proxy;
  - `Выпустить resident конфиг` — issue a resident configuration;
  - `Отключить прокси` — disable the system proxy;
  - `Проверить баланс` — check account balance;
  - `Показать активные` — show active proxies;
  - `Открыть папку конфигов` — open the configuration directory.
- Asynchronous API operations without blocking the GUI, plus a paginated event log.
- Paste an API key from the clipboard and remove it from settings.
- Persist local state: API key, selected parameters and last connected proxy.

> The application UI is currently Russian, so button labels are kept exactly as they appear in the product.

## Supported platforms

- macOS
- Windows

Linux is not supported in this build.

## Quick start for development

### 1) Install dependencies

```bash
pip install -r requirements.txt
```

### 2) Run from source

```bash
python app.py
```

## macOS: environment setup and `.app` build

Automated environment setup:

```bash
./setup_macos_env.sh
```

Build the application:

```bash
./build_macos_app.sh
```

Output:

- `dist/Proxy Seller Launcher.app`

## Windows: `.exe` build

Install dependencies on Windows before building:

```powershell
pip install -r requirements.txt
pip install pyinstaller
```

Then run:

```powershell
.\build_windows_app.ps1
```

or:

```bat
build_windows_app.bat
```

Output:

- `dist\Proxy Seller Launcher\Proxy Seller Launcher.exe`

## Automated Windows build with GitHub Actions

The repository includes:

- `.github/workflows/windows-build.yml`

Usage:

1. Open the `Actions` tab on GitHub.
2. Select the `Build Windows App` workflow.
3. Press `Run workflow`, or push changes to `main` when application/build files are affected.
4. After the run completes, download the `proxy-seller-launcher-windows` artifact.

The artifact contains the built `.exe` and the contents of `dist/Proxy Seller Launcher`.

## Using the application

1. Paste your Proxy-Seller API key.
2. Select a proxy type and protocol.
3. Press `Обновить данные`.
4. Select:
   - country + period for standard proxy types, or
   - a tariff for `resident` / `scraper`.
5. Enter the quantity.
6. For `mobile`, select service, operator and rotation.
7. If necessary, open advanced parameters and configure:
   - payment method,
   - authorization IP,
   - `generateAuth`,
   - `customTargetName`,
   - `orderId/baseOrderNumber` filter.
8. Press:
   - `Купить и подключить` to create a paid order and connect it, or
   - `Подключить купленный` to connect without creating another order.
9. For a resident package with remaining traffic, use `Ещё -> Выпустить resident конфиг` to issue a configuration without buying a new package.
10. Use `Отключить прокси` to disable the system proxy.

## Local data storage

All application data is stored in:

- `~/.proxy-desktop-launcher/`

Key files:

- `settings.json` — UI settings and API key;
- `last_proxy.json` — last successfully connected proxy;
- `generated_proxy_configs/` — saved order configurations;
- `app_debug.log` — application debug log.

## Tests

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

Run unit tests:

```bash
PYTHONPATH=. pytest -q
```

Optional live API smoke tests:

```bash
PROXY_SELLER_API_KEY=your_key PYTHONPATH=. pytest -q tests/test_proxy_seller_live.py
```

Live tests check reference data, balance and calculation endpoints and must not create a purchase.

## Limitations and important behavior

- `Купить и подключить` creates a paid Proxy-Seller order and therefore has a confirmation dialog.
- Windows system proxy settings do not persist username/password globally; individual applications may request authentication separately.
- The API key is stored locally in plaintext inside `settings.json` for autofill convenience.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API endpoints](docs/API_ENDPOINTS.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Customer guide for Windows](docs/INSTRUCTION.md)
