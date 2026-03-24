# API эндпоинты, используемые приложением

Базовый URL:

- `https://proxy-seller.com/personal/api/v1/{API_KEY}`

## Используемые запросы

1. `GET /reference/list/{type}`
- Назначение: загрузка справочных данных для UI.
- Используется для получения:
  - стран,
  - периодов,
  - mobile-операторов/ротаций,
  - тарифов (`resident` / `scraper`).

2. `POST /order/calc`
- Назначение: расчет стоимости заказа до оплаты.
- Вызывается перед `order/make` в сценарии "Купить и подключить".

3. `POST /order/make`
- Назначение: создание платного заказа.
- Вызывается только после подтверждения пользователем.

4. `GET /proxy/list/{type}`
- Назначение:
  - получение списка активных прокси,
  - ожидание активации после покупки,
  - подключение уже купленного прокси.
- Поддерживается фильтрация:
  - `orderId`,
  - `baseOrderNumber`.

5. `GET /balance/get`
- Назначение: проверка текущего баланса.

## Формирование payload

### Обычные типы (`ipv4`, `ipv6`, `mobile`, `isp`, `mix`, `mix_isp`)

Обязательные поля:

- `countryId`
- `periodId`
- `quantity`
- `paymentId`

Опциональные:

- `customTargetName`
- `authorization`
- `generateAuth`

Дополнительно:

- для `ipv6`: `protocol` (`HTTPS` или `SOCKS5`);
- для `mobile`: `mobileServiceType`, `operatorId`, `rotationId`.

### Тарифные типы (`resident`, `scraper`)

Обязательные поля:

- `tarifId`
- `quantity`
- `paymentId`

Опциональные:

- `customTargetName`
- `authorization`
- `generateAuth`

## Обработка ошибок

Клиент нормализует ошибки в исключение `ProxySellerAPIError`:

- сетевые ошибки,
- HTTP >= 400,
- `status != success`,
- невалидный JSON в ответе.
