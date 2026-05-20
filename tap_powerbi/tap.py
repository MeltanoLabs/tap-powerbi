"""PowerBI tap class."""

from __future__ import annotations

import sys

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_powerbi import streams

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class TapPowerBI(Tap):
    """Singer tap for Power BI."""

    name = "tap-powerbi"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "tenant_id",
            th.StringType,
            secret=True,
            title="Tenant ID",
            description=(
                "Azure AD tenant ID. Required for the service-principal "
                "(client_credentials) auth flow."
            ),
        ),
        th.Property(
            "client_id",
            th.StringType(nullable=False),
            required=True,
            secret=True,
            title="Client ID",
            description="Azure AD application (client) ID.",
        ),
        th.Property(
            "client_secret",
            th.StringType(nullable=False),
            required=True,
            secret=True,
            title="Client Secret",
            description="Azure AD application client secret.",
        ),
        th.Property(
            "refresh_token",
            th.StringType,
            secret=True,
            title="Refresh Token",
            description=(
                "OAuth refresh token. Provide instead of tenant_id to use the "
                "delegated-user auth flow."
            ),
        ),
        th.Property(
            "workspace_ids",
            th.ArrayType(th.StringType),
            title="Workspace IDs",
            description=(
                "Optional list of Power BI workspace (group) IDs to restrict "
                "discovery to. Empty = all workspaces visible to the principal."
            ),
        ),
        th.Property(
            "start_date",
            th.DateTimeType,
            title="Start Date",
            description=(
                "Earliest timestamp for incremental streams "
                "(e.g. dataset_refreshes)."
            ),
        ),
        th.Property(
            "api_url",
            th.StringType(nullable=False),
            default="https://api.powerbi.com/v1.0/myorg",
            title="API URL",
            description=(
                "Power BI REST API base URL. Override for sovereign clouds "
                "(e.g. https://api.powerbigov.us/v1.0/myorg)."
            ),
        ),
        th.Property(
            "admin_mode",
            th.BooleanType,
            default=False,
            title="Admin Mode",
            description=(
                "Use /admin/* routes for tenant-wide visibility. Requires "
                "Tenant.Read.All permission on the service principal. "
                "Enables admin-only fields (createdDateTime, modifiedBy, "
                "users, etc.) on groups/datasets/reports/dashboards/dataflows."
            ),
        ),
    ).to_dict()

    @override
    def discover_streams(self) -> list[streams.PowerBIStream]:
        return [
            streams.GroupsStream(self),
            streams.DatasetsStream(self),
            streams.ReportsStream(self),
            streams.DashboardsStream(self),
            streams.DataflowsStream(self),
            streams.DatasetRefreshesStream(self),
            streams.CapacitiesStream(self),
            streams.AppsStream(self),
            streams.AppReportsStream(self),
            streams.AppDashboardsStream(self),
            streams.PipelinesStream(self),
            streams.PipelineStagesStream(self),
            streams.PipelineOperationsStream(self),
            streams.GatewaysStream(self),
            streams.GatewayDatasourcesStream(self),
            streams.ImportsStream(self),
        ]


if __name__ == "__main__":
    TapPowerBI.cli()
