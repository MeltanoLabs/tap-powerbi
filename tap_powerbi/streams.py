"""Stream type classes for tap-powerbi."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

from singer_sdk import typing as th

from tap_powerbi.client import PowerBIStream

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Iterable

    from singer_sdk.helpers.types import Context


class GroupsStream(PowerBIStream):
    """Workspaces (groups) visible to the principal."""

    name = "groups"
    user_path = "/groups"
    admin_path = "/admin/groups"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("name", th.StringType),
        th.Property("isReadOnly", th.BooleanType),
        th.Property("isOnDedicatedCapacity", th.BooleanType),
        th.Property("capacityId", th.StringType),
        th.Property("dataflowStorageId", th.StringType),
        th.Property("defaultDatasetStorageFormat", th.StringType),
        # Admin-route only (populated when admin_mode=true):
        th.Property("type", th.StringType),
        th.Property("state", th.StringType),
        th.Property("hasWorkspaceLevelSettings", th.BooleanType),
        th.Property("users", th.ArrayType(th.ObjectType())),
    ).to_dict()

    @override
    def get_url_params(
        self,
        context: Context | None,
        next_page_token: Any | None,
    ) -> dict[str, Any]:
        params = super().get_url_params(context, next_page_token)
        # SDK types `get_url_params` as `dict | str`; we only ever return a
        # dict from this stream, so normalise before mutating.
        if not isinstance(params, dict):
            params = {}
        if self.admin_mode:
            # /admin/groups requires $top (max 5000).
            params.setdefault("$top", 5000)
        return params

    @override
    def get_records(self, context: Context | None) -> Iterable[dict[str, Any]]:
        workspace_ids = self.config.get("workspace_ids") or []
        allow = set(workspace_ids)
        for record in super().get_records(context):
            if allow and record.get("id") not in allow:
                continue
            yield record

    @override
    def get_child_context(
        self,
        record: dict,
        context: Context | None,
    ) -> dict:
        return {"group_id": record["id"]}


class DatasetsStream(PowerBIStream):
    """Datasets within a workspace."""

    name = "datasets"
    parent_stream_type = GroupsStream
    user_path = "/groups/{group_id}/datasets"
    admin_path = "/admin/groups/{group_id}/datasets"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("name", th.StringType),
        th.Property("description", th.StringType),
        th.Property("webUrl", th.StringType),
        th.Property("addRowsAPIEnabled", th.BooleanType),
        th.Property("ContentProviderType", th.StringType),
        th.Property("configuredBy", th.StringType),
        th.Property("isRefreshable", th.BooleanType),
        th.Property("isEffectiveIdentityRequired", th.BooleanType),
        th.Property("isEffectiveIdentityRolesRequired", th.BooleanType),
        th.Property("isInPlaceSharingEnabled", th.BooleanType),
        th.Property("isOnPremGatewayRequired", th.BooleanType),
        th.Property("targetStorageMode", th.StringType),
        th.Property("createdDate", th.DateTimeType),
        th.Property("createReportEmbedURL", th.StringType),
        th.Property("qnaEmbedURL", th.StringType),
        th.Property(
            "upstreamDataflows",
            th.ArrayType(
                th.ObjectType(
                    th.Property("groupId", th.StringType),
                    th.Property("targetDataflowId", th.StringType),
                ),
            ),
        ),
        th.Property(
            "queryScaleOutSettings",
            th.ObjectType(
                th.Property("autoSyncReadOnlyReplicas", th.BooleanType),
                th.Property("maxReadOnlyReplicas", th.IntegerType),
            ),
        ),
        th.Property("users", th.ArrayType(th.ObjectType())),
    ).to_dict()

    @override
    def post_process(
        self,
        row: dict,
        context: Context | None = None,
    ) -> dict | None:
        if context:
            row["group_id"] = context.get("group_id")
        return row

    @override
    def get_child_context(
        self,
        record: dict,
        context: Context | None,
    ) -> dict | None:
        # Skip refresh-history sync for datasets that cannot be refreshed.
        if not record.get("isRefreshable"):
            return None
        return {
            "group_id": context["group_id"] if context else record.get("group_id"),
            "dataset_id": record["id"],
        }


class ReportsStream(PowerBIStream):
    """Reports within a workspace."""

    name = "reports"
    parent_stream_type = GroupsStream
    user_path = "/groups/{group_id}/reports"
    admin_path = "/admin/groups/{group_id}/reports"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("appId", th.StringType),
        th.Property("name", th.StringType),
        th.Property("description", th.StringType),
        th.Property("webUrl", th.StringType),
        th.Property("embedUrl", th.StringType),
        th.Property("datasetId", th.StringType),
        th.Property("reportType", th.StringType),
        th.Property("format", th.StringType),
        th.Property("isOwnedByMe", th.BooleanType),
        th.Property("originalReportId", th.StringType),
        # Admin-route only (populated when admin_mode=true):
        th.Property("createdDateTime", th.DateTimeType),
        th.Property("modifiedDateTime", th.DateTimeType),
        th.Property("createdBy", th.StringType),
        th.Property("modifiedBy", th.StringType),
        th.Property("users", th.ArrayType(th.ObjectType())),
    ).to_dict()

    @override
    def post_process(
        self,
        row: dict,
        context: Context | None = None,
    ) -> dict | None:
        if context:
            row["group_id"] = context.get("group_id")
        return row


class DashboardsStream(PowerBIStream):
    """Dashboards within a workspace."""

    name = "dashboards"
    parent_stream_type = GroupsStream
    user_path = "/groups/{group_id}/dashboards"
    admin_path = "/admin/groups/{group_id}/dashboards"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("appId", th.StringType),
        th.Property("displayName", th.StringType),
        th.Property("isReadOnly", th.BooleanType),
        th.Property("webUrl", th.StringType),
        th.Property("embedUrl", th.StringType),
        # Admin-route only:
        th.Property("users", th.ArrayType(th.ObjectType())),
    ).to_dict()

    @override
    def post_process(
        self,
        row: dict,
        context: Context | None = None,
    ) -> dict | None:
        if context:
            row["group_id"] = context.get("group_id")
        return row


class DataflowsStream(PowerBIStream):
    """Dataflows within a workspace."""

    name = "dataflows"
    parent_stream_type = GroupsStream
    user_path = "/groups/{group_id}/dataflows"
    admin_path = "/admin/groups/{group_id}/dataflows"
    primary_keys = ("objectId",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("objectId", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("name", th.StringType),
        th.Property("description", th.StringType),
        th.Property("modelUrl", th.StringType),
        th.Property("configuredBy", th.StringType),
        th.Property("users", th.ArrayType(th.ObjectType())),
        # Admin-route only:
        th.Property("modifiedBy", th.StringType),
        th.Property("modifiedDateTime", th.DateTimeType),
    ).to_dict()

    @override
    def post_process(
        self,
        row: dict,
        context: Context | None = None,
    ) -> dict | None:
        if context:
            row["group_id"] = context.get("group_id")
        return row


class DatasetRefreshesStream(PowerBIStream):
    """Refresh history for a refreshable dataset."""

    name = "dataset_refreshes"
    parent_stream_type = DatasetsStream
    user_path = "/groups/{group_id}/datasets/{dataset_id}/refreshes"
    primary_keys = ("requestId",)
    replication_key = "endTime"

    schema = th.PropertiesList(
        th.Property("requestId", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("dataset_id", th.StringType),
        th.Property("refreshType", th.StringType),
        th.Property("startTime", th.DateTimeType),
        th.Property("endTime", th.DateTimeType),
        th.Property("status", th.StringType),
        th.Property("serviceExceptionJson", th.StringType),
        th.Property(
            "refreshAttempts",
            th.ArrayType(
                th.ObjectType(
                    th.Property("attemptId", th.IntegerType),
                    th.Property("startTime", th.DateTimeType),
                    th.Property("endTime", th.DateTimeType),
                    th.Property("serviceExceptionJson", th.StringType),
                    th.Property("type", th.StringType),
                ),
            ),
        ),
    ).to_dict()

    @override
    def post_process(
        self,
        row: dict,
        context: Context | None = None,
    ) -> dict | None:
        if context:
            row["group_id"] = context.get("group_id")
            row["dataset_id"] = context.get("dataset_id")
        return row


class CapacitiesStream(PowerBIStream):
    """Premium capacities visible to the principal."""

    name = "capacities"
    user_path = "/capacities"
    admin_path = "/admin/capacities"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("displayName", th.StringType),
        th.Property("sku", th.StringType),
        th.Property("state", th.StringType),
        th.Property("region", th.StringType),
        th.Property("capacityUserAccessRight", th.StringType),
        th.Property("admins", th.ArrayType(th.StringType)),
        # Admin-route only:
        th.Property("tenantKeyId", th.StringType),
    ).to_dict()


class AppsStream(PowerBIStream):
    """Installed apps visible to the principal.

    Note: ``GET /apps`` does not support service-principal authentication
    (per Microsoft docs). Requires the delegated-user (refresh-token) flow.
    """

    name = "apps"
    user_path = "/apps"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("name", th.StringType),
        th.Property("description", th.StringType),
        th.Property("publishedBy", th.StringType),
        th.Property("lastUpdate", th.DateTimeType),
    ).to_dict()

    @override
    def get_child_context(
        self,
        record: dict,
        context: Context | None,
    ) -> dict:
        return {"app_id": record["id"]}


class AppReportsStream(PowerBIStream):
    """Reports published in an app."""

    name = "app_reports"
    parent_stream_type = AppsStream
    user_path = "/apps/{app_id}/reports"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("app_id", th.StringType),
        th.Property("appId", th.StringType),
        th.Property("name", th.StringType),
        th.Property("description", th.StringType),
        th.Property("webUrl", th.StringType),
        th.Property("embedUrl", th.StringType),
        th.Property("datasetId", th.StringType),
        th.Property("reportType", th.StringType),
        th.Property("originalReportId", th.StringType),
    ).to_dict()


class AppDashboardsStream(PowerBIStream):
    """Dashboards published in an app."""

    name = "app_dashboards"
    parent_stream_type = AppsStream
    user_path = "/apps/{app_id}/dashboards"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("app_id", th.StringType),
        th.Property("appId", th.StringType),
        th.Property("displayName", th.StringType),
        th.Property("isReadOnly", th.BooleanType),
        th.Property("webUrl", th.StringType),
        th.Property("embedUrl", th.StringType),
    ).to_dict()


class PipelinesStream(PowerBIStream):
    """Deployment pipelines accessible to the principal."""

    name = "pipelines"
    user_path = "/pipelines"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("displayName", th.StringType),
        th.Property("description", th.StringType),
    ).to_dict()

    @override
    def get_child_context(
        self,
        record: dict,
        context: Context | None,
    ) -> dict:
        return {"pipeline_id": record["id"]}


class PipelineStagesStream(PowerBIStream):
    """Stages of a deployment pipeline (Dev/Test/Prod)."""

    name = "pipeline_stages"
    parent_stream_type = PipelinesStream
    user_path = "/pipelines/{pipeline_id}/stages"
    primary_keys = ("pipeline_id", "order")
    replication_key = None

    schema = th.PropertiesList(
        th.Property("pipeline_id", th.StringType, required=True),
        th.Property("order", th.IntegerType, required=True),
        th.Property("workspaceId", th.StringType),
        th.Property("workspaceName", th.StringType),
    ).to_dict()


class PipelineOperationsStream(PowerBIStream):
    """Recent deploy operations on a pipeline (up to 20 most recent)."""

    name = "pipeline_operations"
    parent_stream_type = PipelinesStream
    user_path = "/pipelines/{pipeline_id}/operations"
    primary_keys = ("id",)
    replication_key = "executionStartTime"

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("pipeline_id", th.StringType),
        th.Property("type", th.StringType),
        th.Property("status", th.StringType),
        th.Property("executionStartTime", th.DateTimeType),
        th.Property("executionEndTime", th.DateTimeType),
        th.Property("lastUpdatedTime", th.DateTimeType),
        th.Property("sourceStageOrder", th.IntegerType),
        th.Property("targetStageOrder", th.IntegerType),
        th.Property(
            "note",
            th.ObjectType(
                th.Property("content", th.StringType),
                th.Property("isTruncated", th.BooleanType),
            ),
        ),
        th.Property(
            "preDeploymentDiffInformation",
            th.ObjectType(
                th.Property("newArtifactsCount", th.IntegerType),
                th.Property("differentArtifactsCount", th.IntegerType),
                th.Property("noDifferenceArtifactsCount", th.IntegerType),
            ),
        ),
        th.Property(
            "performedBy",
            th.ObjectType(
                th.Property("userPrincipalName", th.StringType),
                th.Property("principalType", th.StringType),
                th.Property("principalObjectID", th.StringType),
            ),
        ),
    ).to_dict()


class GatewaysStream(PowerBIStream):
    """On-premises data gateways for which the principal is admin.

    Note: ``GET /gateways`` returns only gateways for which the caller
    has *gateway admin* permissions, regardless of Power BI tenant role.
    """

    name = "gateways"
    user_path = "/gateways"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("name", th.StringType),
        th.Property("type", th.StringType),
        th.Property("gatewayAnnotation", th.StringType),
        th.Property("gatewayStatus", th.StringType),
        th.Property(
            "publicKey",
            th.ObjectType(
                th.Property("exponent", th.StringType),
                th.Property("modulus", th.StringType),
            ),
        ),
    ).to_dict()

    @override
    def get_child_context(
        self,
        record: dict,
        context: Context | None,
    ) -> dict:
        return {"gateway_id": record["id"]}


class GatewayDatasourcesStream(PowerBIStream):
    """Data sources configured on a gateway."""

    name = "gateway_datasources"
    parent_stream_type = GatewaysStream
    user_path = "/gateways/{gateway_id}/datasources"
    primary_keys = ("id",)
    replication_key = None

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("gateway_id", th.StringType),
        th.Property("gatewayId", th.StringType),
        th.Property("datasourceType", th.StringType),
        th.Property("connectionDetails", th.StringType),
        th.Property("credentialType", th.StringType),
        th.Property("datasourceName", th.StringType),
        th.Property(
            "credentialDetails",
            th.ObjectType(
                th.Property("useEndUserOAuth2Credentials", th.BooleanType),
            ),
        ),
    ).to_dict()


class ImportsStream(PowerBIStream):
    """``.pbix``/``.xlsx`` upload history per workspace."""

    name = "imports"
    parent_stream_type = GroupsStream
    user_path = "/groups/{group_id}/imports"
    primary_keys = ("id",)
    replication_key = "updatedDateTime"

    schema = th.PropertiesList(
        th.Property("id", th.StringType, required=True),
        th.Property("group_id", th.StringType),
        th.Property("name", th.StringType),
        th.Property("importState", th.StringType),
        th.Property("createdDateTime", th.DateTimeType),
        th.Property("updatedDateTime", th.DateTimeType),
        th.Property("connectionType", th.StringType),
        th.Property("source", th.StringType),
        th.Property("datasets", th.ArrayType(th.ObjectType())),
        th.Property("reports", th.ArrayType(th.ObjectType())),
        th.Property(
            "error",
            th.ObjectType(
                th.Property("code", th.StringType),
                th.Property("details", th.ArrayType(th.ObjectType())),
            ),
        ),
    ).to_dict()
