"""PowerBI Authentication."""

from __future__ import annotations

import sys
import time
from typing import TYPE_CHECKING

import requests
from singer_sdk.authenticators import (
    APIAuthenticatorBase,
    OAuthAuthenticator,
    SingletonMeta,
)

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from singer_sdk.streams import Stream

POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"

PROXY_URL_KEYS = (
    "oauth_credentials.refresh_proxy_url",
    "refresh_proxy_url",
)
PROXY_AUTH_KEYS = (
    "oauth_credentials.refresh_proxy_url_auth",
    "refresh_proxy_url_auth",
)
REFRESH_TOKEN_KEYS = (
    "refresh_token",
    "oauth_credentials.refresh_token",
)

# Refresh slightly before the proxy-reported expiry so an in-flight request
# does not race the token's actual expiration.
_EXPIRY_SKEW_SECONDS = 60


def _first_present(config: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = config.get(key)
        if value:
            return str(value)
    return None


class ProxyRefreshAuthenticator(APIAuthenticatorBase, metaclass=SingletonMeta):
    """Bearer-token authenticator that mints access tokens via the Matatika OAuth proxy.

    The catalog UI's "Connect with Microsoft" button uses Matatika's Azure AD
    app to mint a refresh token via PKCE. Microsoft binds refresh tokens to
    the minting client, so the tap cannot exchange the refresh token directly
    — the proxy holds Matatika's client_secret and performs the exchange
    server-side. The tap POSTs ``{"refresh_token": ...}`` and receives a
    fresh ``{"access_token", "expires_in"}``.
    """

    def __init__(
        self,
        *,
        proxy_url: str,
        refresh_token: str,
        proxy_auth_header: str | None = None,
    ) -> None:
        """Initialise the authenticator with proxy URL and refresh token."""
        super().__init__()
        self._proxy_url = proxy_url
        self._refresh_token = refresh_token
        self._proxy_auth_header = proxy_auth_header
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    @property
    def _is_token_valid(self) -> bool:
        return (
            self._access_token is not None
            and time.time() < self._expires_at - _EXPIRY_SKEW_SECONDS
        )

    def _refresh_access_token(self) -> None:
        headers = {"Content-Type": "application/json"}
        if self._proxy_auth_header:
            headers["Authorization"] = self._proxy_auth_header
        response = requests.post(
            self._proxy_url,
            json={"refresh_token": self._refresh_token},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        # Default to 1h if proxy omits expires_in (matches Microsoft's default).
        expires_in = int(payload.get("expires_in", 3600))
        self._expires_at = time.time() + expires_in

    @override
    def authenticate_request(
        self,
        request: requests.PreparedRequest,
    ) -> requests.PreparedRequest:
        if not self._is_token_valid:
            self._refresh_access_token()
        self.auth_headers["Authorization"] = f"Bearer {self._access_token}"
        return super().authenticate_request(request)


class PowerBIAuthenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator for Power BI supporting service-principal and direct refresh-token flows."""

    def __init__(
        self,
        *,
        tap_config: dict,
        auth_endpoint: str,
        oauth_scopes: str,
    ) -> None:
        super().__init__(
            auth_endpoint=auth_endpoint,
            oauth_scopes=oauth_scopes,
            client_id=tap_config.get("client_id"),
            client_secret=tap_config.get("client_secret"),
        )
        # OAuthAuthenticator leaves _config={} when stream is not passed;
        # restore the full tap config so oauth_request_body can read
        # refresh_token and other settings.
        self._config = dict(tap_config)

    @classmethod
    def create_for_stream(cls, stream: Stream) -> APIAuthenticatorBase:
        """Build the right authenticator from a stream's tap config.

        Three modes, in priority order:

        1. **Proxy refresh** — ``oauth_credentials.refresh_proxy_url`` is set.
           Used by the Matatika catalog "Connect with Microsoft" button. The
           proxy holds Matatika's ``client_secret``; the tap only needs the
           refresh token.
        2. **Direct delegated user** — ``refresh_token`` is set and the
           operator provides their own ``client_id``/``client_secret``.
        3. **Service principal** — ``client_credentials`` flow, tenant-scoped.
        """
        config = dict(stream.config)

        proxy_url = _first_present(config, PROXY_URL_KEYS)
        if proxy_url:
            refresh_token = _first_present(config, REFRESH_TOKEN_KEYS)
            if not refresh_token:
                msg = (
                    "oauth_credentials.refresh_proxy_url is set but no "
                    "refresh_token was provided."
                )
                raise ValueError(msg)
            return ProxyRefreshAuthenticator(
                proxy_url=proxy_url,
                refresh_token=refresh_token,
                proxy_auth_header=_first_present(config, PROXY_AUTH_KEYS),
            )

        tenant_id = config.get("tenant_id") or "common"
        auth_endpoint = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        return cls(
            tap_config=config,
            auth_endpoint=auth_endpoint,
            oauth_scopes=POWERBI_SCOPE,
        )

    @override
    @property
    def oauth_request_body(self) -> dict:
        """Build the OAuth token request body.

        Branches on whether ``refresh_token`` is configured: delegated-user
        refresh flow vs. service-principal client_credentials flow.
        """
        config = self._config
        if config.get("refresh_token"):
            return {
                "grant_type": "refresh_token",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": config["refresh_token"],
                "scope": f"{POWERBI_SCOPE} offline_access",
            }
        return {
            "grant_type": "client_credentials",
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": POWERBI_SCOPE,
        }
