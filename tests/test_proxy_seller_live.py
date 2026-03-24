from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from proxy_seller_client import ProxySellerClient

MIX_TYPES = {"mix", "mix_isp"}
TARIFF_TYPES = {"resident", "scraper"}


def _read_api_key() -> str:
    env_key = os.getenv("PROXY_SELLER_API_KEY", "").strip()
    if env_key:
        return env_key

    settings_path = Path.home() / ".proxy-desktop-launcher" / "settings.json"
    if not settings_path.exists():
        return ""

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    return str(data.get("api_key") or "").strip()


def _pick_country_period(
    countries: list[Dict[str, Any]],
    periods: list[Dict[str, Any]],
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if not countries or not periods:
        return None, None
    return countries[0], periods[0]


@pytest.fixture(scope="module")
def live_client() -> ProxySellerClient:
    api_key = _read_api_key()
    if not api_key:
        pytest.skip("Live API key is not set (env PROXY_SELLER_API_KEY or settings.json)")
    return ProxySellerClient(api_key=api_key)


def test_live_reference_and_active_list(live_client: ProxySellerClient) -> None:
    proxy_type = os.getenv("PROXY_SELLER_PROXY_TYPE", "ipv4").strip() or "ipv4"
    countries, periods = live_client.get_reference_options(proxy_type=proxy_type)
    assert isinstance(countries, list)
    assert isinstance(periods, list)
    active = live_client.get_active_proxies(proxy_type=proxy_type, params={"limit": 5})
    assert isinstance(active, list)


def test_live_balance(live_client: ProxySellerClient) -> None:
    data = live_client.get_balance()
    assert isinstance(data, dict)


def test_live_calculate_order(live_client: ProxySellerClient) -> None:
    proxy_type = os.getenv("PROXY_SELLER_PROXY_TYPE", "ipv4").strip() or "ipv4"
    reference_items = live_client.get_reference(proxy_type=proxy_type)
    if not reference_items or not isinstance(reference_items[0], dict):
        pytest.skip("No reference payload returned by API for calculate_order smoke test")

    root_item = reference_items[0]
    countries = list(root_item.get("country") or [])
    periods = list(root_item.get("period") or [])
    country, period = _pick_country_period(countries, periods)
    if country is None or period is None:
        pytest.skip("No country/period returned by API for calculate_order smoke test")

    quantity = 1
    if proxy_type == "ipv6":
        quantity = 10
    elif proxy_type in MIX_TYPES:
        quantity_options: list[int] = []
        for item in list(root_item.get("quantities") or []):
            if not isinstance(item, dict):
                continue
            if str(item.get("id")) != str(country.get("id")):
                continue
            for raw_value in list(item.get("quantities") or []):
                try:
                    parsed = int(raw_value)
                except (TypeError, ValueError):
                    continue
                if parsed > 0:
                    quantity_options.append(parsed)
            break
        if not quantity_options:
            pytest.skip("No allowed quantity options returned by API for MIX smoke test")
        quantity = sorted(set(quantity_options))[0]

    payload = live_client.build_order_payload(
        proxy_type=proxy_type,
        country_id=int(country["id"]),
        period_id=str(period["id"]),
        quantity=quantity,
        payment_id=1,
        protocol="http",
    )
    payload["customTargetName"] = "Proxy for Telegram"

    if proxy_type == "mobile":
        operators_root = country.get("operators")
        if not isinstance(operators_root, dict):
            pytest.skip("No mobile operators returned by API for selected country")

        service_type = ""
        operators: list[Dict[str, Any]] = []
        for key in ("dedicated", "shared"):
            candidate = operators_root.get(key)
            if isinstance(candidate, list) and candidate:
                service_type = key
                operators = [item for item in candidate if isinstance(item, dict)]
                if operators:
                    break
        if not operators:
            pytest.skip("No mobile operator entries returned by API")

        operator = operators[0]
        rotations = [item for item in list(operator.get("rotations") or []) if isinstance(item, dict)]
        if not rotations:
            pytest.skip("No mobile rotations returned by API")

        payload["mobileServiceType"] = service_type or "dedicated"
        payload["operatorId"] = str(operator.get("id") or "")
        payload["rotationId"] = rotations[0].get("id")

    calc = live_client.calculate_order(payload)
    assert isinstance(calc, dict)


@pytest.mark.parametrize("proxy_type", sorted(TARIFF_TYPES))
def test_live_calculate_tariff_order(
    live_client: ProxySellerClient,
    proxy_type: str,
) -> None:
    reference_items = live_client.get_reference(proxy_type=proxy_type)
    if not reference_items or not isinstance(reference_items[0], dict):
        pytest.skip(f"No reference payload returned by API for {proxy_type}")

    root_item = reference_items[0]
    tarifs = [
        item for item in list(root_item.get("tarifs") or root_item.get("tariffs") or [])
        if isinstance(item, dict)
    ]
    if not tarifs:
        pytest.skip(f"No tariffs returned by API for {proxy_type}")

    payload = live_client.build_tariff_order_payload(
        tarif_id=int(tarifs[0]["id"]),
        quantity=1,
        payment_id=1,
        custom_target_name="Proxy for Telegram",
        authorization="",
        generate_auth="N",
    )
    calc = live_client.calculate_order(payload)
    assert isinstance(calc, dict)
