from __future__ import annotations

import zlib
from typing import Any, Dict, Optional

import pytest

import proxy_seller_client as psc
from proxy_seller_client import ProxySellerAPIError, ProxySellerClient


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


@pytest.fixture
def client() -> ProxySellerClient:
    return ProxySellerClient(api_key="test_key", base_url="https://example.com/api/v1")


def _patch_request(
    monkeypatch: pytest.MonkeyPatch,
    response: FakeResponse,
) -> Dict[str, Any]:
    captured: Dict[str, Any] = {}

    def fake_request(
        *,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
        timeout: int,
    ) -> FakeResponse:
        captured["method"] = method
        captured["url"] = url
        captured["params"] = params
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return response

    monkeypatch.setattr(psc.requests, "request", fake_request)
    return captured


def test_build_url_normalizes_slashes(client: ProxySellerClient) -> None:
    assert client._build_url("/order/calc") == "https://example.com/api/v1/test_key/order/calc"
    assert client._build_url("order/calc") == "https://example.com/api/v1/test_key/order/calc"


def test_request_returns_dict_data(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": {"foo": "bar"}}),
    )
    data = client._request("GET", "/some-endpoint")
    assert data == {"foo": "bar"}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/api/v1/test_key/some-endpoint"
    assert captured["headers"] == {
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    assert captured["timeout"] == 30


def test_request_wraps_list_data_as_items(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": [{"id": 1}, {"id": 2}]}),
    )
    data = client._request("GET", "/list")
    assert data == {"items": [{"id": 1}, {"id": 2}]}


def test_request_raises_with_http_error_message(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(
        monkeypatch,
        FakeResponse(
            400,
            {"status": "error", "errors": [{"message": "Bad request from API"}]},
        ),
    )
    with pytest.raises(ProxySellerAPIError, match="Bad request from API"):
        client._request("GET", "/broken")


def test_request_raises_if_status_not_success(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "error", "errors": ["business error"]}),
    )
    with pytest.raises(ProxySellerAPIError, match="business error"):
        client._request("POST", "/calc", json_body={"x": 1})


def test_request_raises_for_non_json_response(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(monkeypatch, FakeResponse(200, ValueError("not json")))
    with pytest.raises(ProxySellerAPIError, match="non-JSON"):
        client._request("GET", "/no-json")


def test_request_raises_for_unreadable_response(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(monkeypatch, FakeResponse(200, zlib.error("incorrect header check")))
    with pytest.raises(ProxySellerAPIError, match="unreadable response"):
        client._request("GET", "/decode-broken")


def test_get_reference_calls_expected_endpoint(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": [{"x": 1}]}),
    )
    items = client.get_reference("ipv4")
    assert items == [{"x": 1}]
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/api/v1/test_key/reference/list/ipv4"


def test_get_reference_wraps_dict_items(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_request(
        monkeypatch,
        FakeResponse(
            200,
            {
                "status": "success",
                "data": {
                    "items": {
                        "country": [{"id": 1, "name": "Proxy of US", "alpha3": "USA"}],
                        "period": [{"id": 7, "name": "7 days"}],
                    }
                },
            },
        ),
    )
    items = client.get_reference("ipv4")
    assert items == [
        {
            "country": [{"id": 1, "name": "Proxy of US", "alpha3": "USA"}],
            "period": [{"id": 7, "name": "7 days"}],
        }
    ]


def test_calculate_order_calls_calc_endpoint(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"countryId": 1, "periodId": "30", "quantity": 1, "paymentId": 1}
    captured = _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": {"total": 10}}),
    )
    data = client.calculate_order(payload)
    assert data == {"total": 10}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/api/v1/test_key/order/calc"
    assert captured["json"] == payload


def test_place_order_calls_make_endpoint(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {"countryId": 1, "periodId": "30", "quantity": 1, "paymentId": 1}
    captured = _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": {"order_id": 999}}),
    )
    data = client.place_order(payload)
    assert data == {"order_id": 999}
    assert captured["method"] == "POST"
    assert captured["url"] == "https://example.com/api/v1/test_key/order/make"
    assert captured["json"] == payload


def test_get_balance_calls_balance_endpoint(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_request(
        monkeypatch,
        FakeResponse(200, {"status": "success", "data": {"summ": 123.45, "currency": "USD"}}),
    )
    data = client.get_balance()
    assert data == {"summ": 123.45, "currency": "USD"}
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/api/v1/test_key/balance/get"
    assert captured["params"] is None


def test_get_active_proxies_filters_non_dict(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _patch_request(
        monkeypatch,
        FakeResponse(
            200,
            {"status": "success", "data": [{"id": 1}, "bad-item", {"id": 2}]},
        ),
    )
    items = client.get_active_proxies("ipv4", params={"orderId": "123"})
    assert items == [{"id": 1}, {"id": 2}]
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/api/v1/test_key/proxy/list/ipv4"
    assert captured["params"] == {"orderId": "123"}


def test_get_reference_options_dedupes_and_sorts(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client,
        "get_reference",
        lambda proxy_type: [
            {
                "country": [
                    {"id": 2, "name": "Germany", "alpha3": "DEU"},
                    {"id": 1, "name": "Austria", "alpha3": "AUT"},
                ],
                "period": [{"id": "30", "name": "30 days"}],
            },
            {
                "country": [{"id": 2, "name": "Germany", "alpha3": "DEU"}],
                "period": [{"id": "7", "name": "7 days"}],
            },
        ],
    )
    countries, periods = client.get_reference_options("ipv4")
    assert countries == [
        {"id": 1, "name": "Austria", "alpha3": "AUT"},
        {"id": 2, "name": "Germany", "alpha3": "DEU"},
    ]
    assert periods == [
        {"id": "30", "name": "30 days"},
        {"id": "7", "name": "7 days"},
    ]


def test_build_order_payload_sets_ipv6_protocol(client: ProxySellerClient) -> None:
    payload = client.build_order_payload(
        proxy_type="ipv6",
        country_id=1,
        period_id="7",
        quantity=2,
        payment_id=1,
        protocol="socks5",
    )
    assert payload == {
        "countryId": 1,
        "periodId": "7",
        "quantity": 2,
        "paymentId": 1,
        "protocol": "SOCKS5",
        "generateAuth": "N",
    }


def test_build_order_payload_for_ipv4_has_no_protocol(client: ProxySellerClient) -> None:
    payload = client.build_order_payload(
        proxy_type="ipv4",
        country_id=1,
        period_id="7",
        quantity=2,
        payment_id=1,
        protocol="socks5",
    )
    assert payload == {
        "countryId": 1,
        "periodId": "7",
        "quantity": 2,
        "paymentId": 1,
        "generateAuth": "N",
    }


def test_build_order_payload_sets_optional_auth_fields(client: ProxySellerClient) -> None:
    payload = client.build_order_payload(
        proxy_type="ipv4",
        country_id=1,
        period_id="7",
        quantity=2,
        payment_id=43,
        protocol="http",
        custom_target_name="Proxy for Telegram",
        authorization="ip",
        generate_auth="Y",
    )
    assert payload == {
        "countryId": 1,
        "periodId": "7",
        "quantity": 2,
        "paymentId": 43,
        "customTargetName": "Proxy for Telegram",
        "authorization": "ip",
        "generateAuth": "Y",
    }


def test_build_tariff_order_payload_sets_expected_fields(client: ProxySellerClient) -> None:
    payload = client.build_tariff_order_payload(
        tarif_id=6928,
        quantity=1,
        payment_id=43,
        custom_target_name="Proxy for Telegram",
        authorization="1.2.3.4",
        generate_auth="Y",
    )
    assert payload == {
        "tarifId": 6928,
        "quantity": 1,
        "paymentId": 43,
        "customTargetName": "Proxy for Telegram",
        "authorization": "1.2.3.4",
        "generateAuth": "Y",
    }


def test_wait_for_order_proxy_returns_first_item(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"n": 0}

    def fake_get_active_proxies(proxy_type: str, params: Dict[str, Any]) -> list[Dict[str, Any]]:
        calls["n"] += 1
        if calls["n"] < 3:
            return []
        return [{"ip": "1.2.3.4"}]

    monkeypatch.setattr(client, "get_active_proxies", fake_get_active_proxies)
    monkeypatch.setattr(psc.time, "sleep", lambda _sec: None)
    result = client.wait_for_order_proxy("ipv4", order_id="123", timeout_sec=10, poll_interval_sec=0)
    assert result == {"ip": "1.2.3.4"}
    assert calls["n"] == 3


def test_wait_for_order_proxy_times_out(
    client: ProxySellerClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client, "get_active_proxies", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(psc.time, "sleep", lambda _sec: None)

    timeline = iter([0.0, 0.1, 0.2, 1.2])
    monkeypatch.setattr(psc.time, "time", lambda: next(timeline))

    with pytest.raises(ProxySellerAPIError, match="Timed out waiting for proxy activation"):
        client.wait_for_order_proxy("ipv4", order_id="123", timeout_sec=1, poll_interval_sec=0)
