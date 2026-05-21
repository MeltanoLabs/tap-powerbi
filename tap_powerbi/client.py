"""REST client handling, including PowerBIStream base class."""

from __future__ import annotations

import sys
from functools import cached_property
from typing import TYPE_CHECKING

from singer_sdk.pagination import BaseHATEOASPaginator
from singer_sdk.streams import RESTStream

from tap_powerbi.auth import PowerBIAuthenticator

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Auth


DEFAULT_API_URL = "https://api.powerbi.com/v1.0/myorg"


class PowerBIPaginator(BaseHATEOASPaginator):
    """Paginator for Power BI's OData ``@odata.nextLink`` envelope."""

    @override
    def get_next_url(self, response: requests.Response) -> str | None:
        return response.json().get("@odata.nextLink")


class PowerBIStream(RESTStream):
    """Base stream class for Power BI."""

    records_jsonpath = "$.value[*]"

    user_path: str = ""
    admin_path: str = ""

    @property
    def admin_mode(self) -> bool:
        """Whether the tap is configured to use ``/admin/*`` routes."""
        return bool(self.config.get("admin_mode"))

    # NB: SDK's ``RESTStream.path`` is a class attribute (``str``), not a
    # property — so ``@override`` would be wrong here.
    @property
    def path(self) -> str:  # type: ignore[override]
        """Resolve to ``admin_path`` when ``admin_mode`` is on; else ``user_path``."""
        if self.admin_mode and self.admin_path:
            return self.admin_path
        return self.user_path

    @override
    @property
    def url_base(self) -> str:
        return self.config.get("api_url", DEFAULT_API_URL)

    @override
    @cached_property
    def authenticator(self) -> Auth:
        return PowerBIAuthenticator.create_for_stream(self)

    @override
    def get_new_paginator(self) -> PowerBIPaginator:
        return PowerBIPaginator()
