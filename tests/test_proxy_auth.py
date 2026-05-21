"""Tests for the Matatika OAuth proxy auth flow."""

from __future__ import annotations

import time

import pytest
import requests_mock

from tap_powerbi.auth import (
    POWERBI_SCOPE,  # noqa: F401  (exposed for sanity)
    ProxyRefreshAuthenticator,
)
from tap_powerbi.tap import TapPowerBI

PROXY_URL = "https://proxy.example.com/oauth/refresh"
POWERBI_GROUPS_URL = "https://api.powerbi.com/v1.0/myorg/groups"
MICROSOFT_TOKEN_URL = "https://login.microsoftonline.com"  # noqa: S105


@pytest.fixture
def proxy_config() -> dict:
    """Tap config for the proxy flow — no client_secret, proxy holds it."""
    return {
        "client_id": "matatika-azure-app-client-id",
        "refresh_token": "minted-by-proxy",
        "oauth_credentials.refresh_proxy_url": PROXY_URL,
        "start_date": "2024-01-01T00:00:00Z",
    }


def _reset_proxy_singleton() -> None:
    """Clear the SingletonMeta cache so each test gets a fresh authenticator."""
    # SingletonMeta stores the cached instance under the name-mangled attribute
    # ``_SingletonMeta__single_instance`` on the class object.
    ProxyRefreshAuthenticator._SingletonMeta__single_instance = None  # type: ignore[attr-defined]  # noqa: SLF001


@pytest.fixture(autouse=True)
def _isolate_singleton() -> None:
    _reset_proxy_singleton()


def test_proxy_flow_mints_and_uses_token(proxy_config: dict) -> None:
    """Tap calls the proxy and uses the returned access token on Power BI calls."""
    _reset_proxy_singleton()

    with requests_mock.Mocker() as m:
        proxy_mock = m.post(
            PROXY_URL,
            json={"access_token": "fake-tok", "expires_in": 3600},
        )
        groups_mock = m.get(
            POWERBI_GROUPS_URL,
            json={"value": [{"id": "g1", "name": "Workspace 1"}]},
        )

        tap = TapPowerBI(config=proxy_config, parse_env_config=False)
        groups_stream = next(
            s for s in tap.discover_streams() if s.name == "groups"
        )
        records = list(groups_stream.get_records(context=None))

        assert len(records) == 1
        assert proxy_mock.call_count == 1
        assert proxy_mock.last_request.json() == {
            "refresh_token": "minted-by-proxy",
        }
        assert groups_mock.last_request.headers["Authorization"] == (
            "Bearer fake-tok"
        )
        # Microsoft's token endpoint must never be hit.
        for req in m.request_history:
            assert MICROSOFT_TOKEN_URL not in req.url


def test_proxy_token_is_cached_within_ttl(proxy_config: dict) -> None:
    """A second sync within ``expires_in`` reuses the cached token."""
    _reset_proxy_singleton()

    with requests_mock.Mocker() as m:
        proxy_mock = m.post(
            PROXY_URL,
            json={"access_token": "fake-tok", "expires_in": 3600},
        )
        m.get(POWERBI_GROUPS_URL, json={"value": []})

        tap = TapPowerBI(config=proxy_config, parse_env_config=False)
        groups_stream = next(
            s for s in tap.discover_streams() if s.name == "groups"
        )
        list(groups_stream.get_records(context=None))
        list(groups_stream.get_records(context=None))

        assert proxy_mock.call_count == 1


def test_proxy_token_refreshes_after_expiry(
    proxy_config: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the cached token expires, the next call re-POSTs to the proxy."""
    _reset_proxy_singleton()

    with requests_mock.Mocker() as m:
        proxy_mock = m.post(
            PROXY_URL,
            [
                {"json": {"access_token": "tok-1", "expires_in": 3600}},
                {"json": {"access_token": "tok-2", "expires_in": 3600}},
            ],
        )
        groups_mock = m.get(POWERBI_GROUPS_URL, json={"value": []})

        tap = TapPowerBI(config=proxy_config, parse_env_config=False)
        groups_stream = next(
            s for s in tap.discover_streams() if s.name == "groups"
        )
        list(groups_stream.get_records(context=None))
        assert proxy_mock.call_count == 1
        assert groups_mock.last_request.headers["Authorization"] == "Bearer tok-1"

        # Jump forward past the cached token's expiry.
        real_time = time.time
        future = real_time() + 7200
        monkeypatch.setattr(time, "time", lambda: future)

        list(groups_stream.get_records(context=None))
        assert proxy_mock.call_count == 2  # noqa: PLR2004
        assert groups_mock.last_request.headers["Authorization"] == "Bearer tok-2"


def test_proxy_authorization_header_forwarded(proxy_config: dict) -> None:
    """``oauth_credentials.refresh_proxy_url_auth`` is sent on proxy POSTs."""
    _reset_proxy_singleton()
    proxy_config = {
        **proxy_config,
        "oauth_credentials.refresh_proxy_url_auth": "Bearer proxy-secret",
    }

    with requests_mock.Mocker() as m:
        proxy_mock = m.post(
            PROXY_URL,
            json={"access_token": "fake-tok", "expires_in": 3600},
        )
        m.get(POWERBI_GROUPS_URL, json={"value": []})

        tap = TapPowerBI(config=proxy_config, parse_env_config=False)
        groups_stream = next(
            s for s in tap.discover_streams() if s.name == "groups"
        )
        list(groups_stream.get_records(context=None))

        assert proxy_mock.last_request.headers["Authorization"] == (
            "Bearer proxy-secret"
        )
