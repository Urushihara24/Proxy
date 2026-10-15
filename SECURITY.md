# Security Policy

## Scope

Security reports are welcome for issues that could affect the Proxy Seller Desktop Launcher's handling of API credentials, order creation, local state, generated proxy configuration, or operating-system proxy changes.

Examples include:

- exposure or unintended persistence of a Proxy-Seller API key;
- an order/purchase action occurring without the expected explicit user action;
- unsafe handling of locally stored `settings.json` or generated proxy data;
- unintended system-proxy mutation;
- dependency or build-chain issues that could affect distributed artifacts.

## Reporting

Please do **not** publish API keys, credentials, proxy configuration, account data, or exploit details in a public issue.

Use GitHub private vulnerability reporting when it is available for this repository. If a private GitHub report is not available, send a short sanitized summary through the work contact listed on the maintainer profile and keep secrets/redacted data out of the initial message.

Include, when possible:

- affected version/commit and operating system;
- reproduction steps using non-sensitive placeholder values;
- expected vs actual behavior;
- impact and whether a paid order or host-network setting could be affected;
- logs/screenshots with secrets removed.

## Safety boundary

Pull-request CI is intentionally offline: it does not create Proxy-Seller purchases and does not change the runner's system proxy. Live API checks remain opt-in and must use an explicitly authorized account.

Never commit `.env`, `settings.json`, API keys, purchased proxy credentials, or other account-specific runtime state.