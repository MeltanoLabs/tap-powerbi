"""PowerBI Authentication."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from singer_sdk.authenticators import OAuthAuthenticator, SingletonMeta

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from singer_sdk.streams import Stream

POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


class PowerBIAuthenticator(OAuthAuthenticator, metaclass=SingletonMeta):
    """Authenticator for Power BI supporting both service-principal and refresh-token flows."""

    @classmethod
    def create_for_stream(cls, stream: Stream) -> PowerBIAuthenticator:
        """Build an authenticator from a stream's tap config.

        The Power BI token endpoint is tenant-scoped; ``common`` is used when
        no tenant is configured (valid for the delegated-user refresh-token
        flow).
        """
        tenant_id = stream.config.get("tenant_id") or "common"
        auth_endpoint = (
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        )
        return cls(
            stream=stream,
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
        config = self.config
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
