from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests


class ProxySellerAPIError(Exception):
    """Raised when Proxy-Seller API returns an error or cannot be reached."""


class ProxySellerClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://proxy-seller.com/personal/api/v1",
        timeout: int = 30,
    ) -> None:
        if not api_key:
            raise ProxySellerAPIError("API key is required")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _build_url(self, endpoint: str) -> str:
        endpoint = endpoint.strip()
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{self.base_url}/{self.api_key}{endpoint}"

    @staticmethod
    def _extract_error(payload: Dict[str, Any], fallback: str) -> str:
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, dict):
                message = first.get("message")
                if message:
                    return str(message)
            return str(first)
        return fallback

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self._build_url(endpoint)
        request_headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
        }
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=request_headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ProxySellerAPIError(f"Proxy-Seller request failed: {exc}") from exc

        try:
            payload = response.json()
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise ProxySellerAPIError(
                    f"Proxy-Seller returned non-JSON response (HTTP {response.status_code})"
                ) from exc
            raise ProxySellerAPIError(
                "Proxy-Seller returned unreadable response "
                f"(HTTP {response.status_code}): {exc}"
            ) from exc

        if response.status_code >= 400:
            message = self._extract_error(
                payload,
                f"Proxy-Seller HTTP error {response.status_code}",
            )
            raise ProxySellerAPIError(message)

        if payload.get("status") != "success":
            message = self._extract_error(payload, "Proxy-Seller returned status=error")
            raise ProxySellerAPIError(message)

        data = payload.get("data")
        if isinstance(data, dict):
            return data
        return {"items": data if isinstance(data, list) else []}

    def get_reference(self, proxy_type: str) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/reference/list/{proxy_type}")
        items = data.get("items")
        if isinstance(items, dict):
            return [items]
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    def get_reference_options(
        self, proxy_type: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        items = self.get_reference(proxy_type)

        country_map: Dict[Any, Dict[str, Any]] = {}
        period_map: Dict[Any, Dict[str, Any]] = {}

        for item in items:
            if not isinstance(item, dict):
                continue

            for country in item.get("country", []) or []:
                if not isinstance(country, dict):
                    continue
                country_id = country.get("id")
                if country_id is None:
                    continue
                country_map[country_id] = {
                    "id": country_id,
                    "name": str(country.get("name", "Unknown")),
                    "alpha3": str(country.get("alpha3", "")),
                }

            for period in item.get("period", []) or []:
                if not isinstance(period, dict):
                    continue
                period_id = period.get("id")
                if period_id is None:
                    continue
                period_map[period_id] = {
                    "id": period_id,
                    "name": str(period.get("name", period_id)),
                }

        countries = sorted(
            country_map.values(), key=lambda c: (c.get("name") or "").lower()
        )
        periods = sorted(period_map.values(), key=lambda p: str(p.get("id")))

        return countries, periods

    def build_order_payload(
        self,
        proxy_type: str,
        country_id: int,
        period_id: str,
        quantity: int,
        payment_id: int = 1,
        protocol: str = "http",
        custom_target_name: str = "",
        authorization: str = "",
        generate_auth: str = "N",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "countryId": int(country_id),
            "periodId": str(period_id),
            "quantity": int(quantity),
            "paymentId": int(payment_id),
        }

        if proxy_type == "ipv6":
            payload["protocol"] = "SOCKS5" if protocol.lower() == "socks5" else "HTTPS"

        target_name = str(custom_target_name or "").strip()
        if target_name:
            payload["customTargetName"] = target_name

        auth_method = str(authorization or "").strip()
        if auth_method:
            payload["authorization"] = auth_method

        generate_auth_value = str(generate_auth or "N").strip().upper()
        payload["generateAuth"] = "Y" if generate_auth_value == "Y" else "N"

        return payload

    def calculate_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/order/calc", json_body=payload)

    def place_order(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", "/order/make", json_body=payload)

    def get_balance(self) -> Dict[str, Any]:
        return self._request("GET", "/balance/get")

    def get_resident_package(self) -> Dict[str, Any]:
        return self._request("GET", "/resident/package")

    def create_resident_tool_list(self) -> Dict[str, Any]:
        return self._request("PUT", "/resident/list/tools")

    def get_resident_subuser_packages(self) -> List[Dict[str, Any]]:
        data = self._request("GET", "/residentsubuser/packages")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        items = data.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []

    def create_resident_subuser_tool_list(self, package_key: str) -> Dict[str, Any]:
        normalized_key = str(package_key or "").strip()
        if not normalized_key:
            raise ProxySellerAPIError("package_key is required for resident subuser list")
        return self._request(
            "PUT",
            "/residentsubuser/list/tools",
            json_body={"package_key": normalized_key},
        )

    def build_tariff_order_payload(
        self,
        tarif_id: int,
        quantity: int,
        payment_id: int = 1,
        custom_target_name: str = "",
        authorization: str = "",
        generate_auth: str = "N",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "tarifId": int(tarif_id),
            "quantity": int(quantity),
            "paymentId": int(payment_id),
        }

        target_name = str(custom_target_name or "").strip()
        if target_name:
            payload["customTargetName"] = target_name

        auth_method = str(authorization or "").strip()
        if auth_method:
            payload["authorization"] = auth_method

        generate_auth_value = str(generate_auth or "N").strip().upper()
        payload["generateAuth"] = "Y" if generate_auth_value == "Y" else "N"
        return payload

    def get_active_proxies(
        self,
        proxy_type: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/proxy/list/{proxy_type}", params=params or {})
        items = data.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def wait_for_order_proxy(
        self,
        proxy_type: str,
        order_id: Any,
        timeout_sec: int = 120,
        poll_interval_sec: int = 4,
    ) -> Dict[str, Any]:
        order_id_str = str(order_id)
        deadline = time.time() + timeout_sec

        while time.time() < deadline:
            items = self.get_active_proxies(proxy_type, params={"orderId": order_id_str})
            if items:
                return items[0]
            time.sleep(poll_interval_sec)

        raise ProxySellerAPIError(
            f"Timed out waiting for proxy activation for order {order_id_str}"
        )
