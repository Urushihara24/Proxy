# API Endpoints Used by the Application

Base URL:

- `https://proxy-seller.com/personal/api/v1/{API_KEY}`

## Requests

1. `GET /reference/list/{type}`
- Purpose: load reference data for the UI.
- Used to retrieve:
  - countries,
  - periods,
  - mobile operators / rotations,
  - tariffs for `resident` / `scraper`.

2. `POST /order/calc`
- Purpose: calculate order cost before payment.
- Called before `order/make` in the `Купить и подключить` (Buy and connect) flow.

3. `POST /order/make`
- Purpose: create a paid order.
- Called only after explicit user confirmation.

4. `GET /proxy/list/{type}`
- Purpose:
  - retrieve active proxies,
  - wait for activation after purchase,
  - connect an already purchased proxy.
- Supports filtering by:
  - `orderId`,
  - `baseOrderNumber`.

5. `GET /balance/get`
- Purpose: retrieve the current account balance.

6. `GET /resident/package`
- Purpose: retrieve the active resident package, including remaining traffic and `package_key`.

7. `PUT /resident/list/tools`
- Purpose: issue `login/password` credentials for API TOOL from the main resident package without buying a new tariff.

8. `GET /residentsubuser/packages`
- Purpose: retrieve resident proxy subuser packages.

9. `PUT /residentsubuser/list/tools`
- Purpose: issue `login/password` credentials for API TOOL using a subuser package `package_key`.

## Payload construction

### Standard types (`ipv4`, `ipv6`, `mobile`, `isp`, `mix`, `mix_isp`)

Required fields:

- `countryId`
- `periodId`
- `quantity`
- `paymentId`

Optional fields:

- `customTargetName`
- `authorization`
- `generateAuth`

Additional type-specific fields:

- `ipv6`: `protocol` (`HTTPS` or `SOCKS5`);
- `mobile`: `mobileServiceType`, `operatorId`, `rotationId`.

### Tariff-based types (`resident`, `scraper`)

Required fields:

- `tarifId`
- `quantity`
- `paymentId`

Optional fields:

- `customTargetName`
- `authorization`
- `generateAuth`

## Error handling

The client normalizes failures into `ProxySellerAPIError` for:

- network errors,
- HTTP status >= 400,
- `status != success`,
- invalid JSON responses.
