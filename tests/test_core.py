"""Tests standard tap features using the built-in SDK tests library."""

import json
import os

import pytest
from requests import Response
from singer_sdk.testing import get_tap_test_class

from tap_powerbi import streams
from tap_powerbi.client import PowerBIPaginator
from tap_powerbi.tap import TapPowerBI

CI = "CI" in os.environ


SAMPLE_CONFIG = {
    "client_id": os.environ.get("TAP_POWERBI_CLIENT_ID", "test-client"),
    "client_secret": os.environ.get("TAP_POWERBI_CLIENT_SECRET", "test-secret"),
    "tenant_id": os.environ.get("TAP_POWERBI_TENANT_ID", "test-tenant"),
    "start_date": "2024-01-01T00:00:00Z",
    "admin_mode": False,
}


# Run standard built-in tap tests from the SDK:
TestTapPowerBI = get_tap_test_class(
    tap_class=TapPowerBI,
    config=SAMPLE_CONFIG,
    include_tap_tests=not CI,
    include_stream_tests=not CI,
    include_stream_attribute_tests=not CI,
)


# Schema-key parity per stream class. Updates here mirror the Power BI
# REST API docs (https://learn.microsoft.com/en-us/rest/api/power-bi/);
# bump these sets when a stream's schema is changed intentionally.
EXPECTED_SCHEMA_KEYS: dict[type, set[str]] = {
    streams.GroupsStream: {
        "id", "name", "isReadOnly", "isOnDedicatedCapacity", "capacityId",
        "dataflowStorageId", "defaultDatasetStorageFormat",
        "type", "state", "hasWorkspaceLevelSettings", "users",
    },
    streams.DatasetsStream: {
        "id", "group_id", "name", "description", "webUrl", "addRowsAPIEnabled",
        "ContentProviderType", "configuredBy", "isRefreshable",
        "isEffectiveIdentityRequired", "isEffectiveIdentityRolesRequired",
        "isInPlaceSharingEnabled", "isOnPremGatewayRequired",
        "targetStorageMode", "createdDate", "createReportEmbedURL",
        "qnaEmbedURL", "upstreamDataflows", "queryScaleOutSettings", "users",
    },
    streams.ReportsStream: {
        "id", "group_id", "appId", "name", "description", "webUrl",
        "embedUrl", "datasetId", "reportType", "format", "isOwnedByMe",
        "originalReportId", "createdDateTime", "modifiedDateTime",
        "createdBy", "modifiedBy", "users",
    },
    streams.DashboardsStream: {
        "id", "group_id", "appId", "displayName", "isReadOnly", "webUrl",
        "embedUrl", "users",
    },
    streams.DataflowsStream: {
        "objectId", "group_id", "name", "description", "modelUrl",
        "configuredBy", "users", "modifiedBy", "modifiedDateTime",
    },
    streams.DatasetRefreshesStream: {
        "requestId", "group_id", "dataset_id", "refreshType", "startTime",
        "endTime", "status", "serviceExceptionJson", "refreshAttempts",
    },
    streams.CapacitiesStream: {
        "id", "displayName", "sku", "state", "region",
        "capacityUserAccessRight", "admins", "tenantKeyId",
    },
    streams.AppsStream: {
        "id", "name", "description", "publishedBy", "lastUpdate",
    },
    streams.AppReportsStream: {
        "id", "app_id", "appId", "name", "description", "webUrl", "embedUrl",
        "datasetId", "reportType", "originalReportId",
    },
    streams.AppDashboardsStream: {
        "id", "app_id", "appId", "displayName", "isReadOnly", "webUrl",
        "embedUrl",
    },
    streams.PipelinesStream: {"id", "displayName", "description"},
    streams.PipelineStagesStream: {
        "pipeline_id", "order", "workspaceId", "workspaceName",
    },
    streams.PipelineOperationsStream: {
        "id", "pipeline_id", "type", "status", "executionStartTime",
        "executionEndTime", "lastUpdatedTime", "sourceStageOrder",
        "targetStageOrder", "note", "preDeploymentDiffInformation",
        "performedBy",
    },
    streams.GatewaysStream: {
        "id", "name", "type", "gatewayAnnotation", "gatewayStatus",
        "publicKey",
    },
    streams.GatewayDatasourcesStream: {
        "id", "gateway_id", "gatewayId", "datasourceType",
        "connectionDetails", "credentialType", "datasourceName",
        "credentialDetails",
    },
    streams.ImportsStream: {
        "id", "group_id", "name", "importState", "createdDateTime",
        "updatedDateTime", "connectionType", "source", "datasets",
        "reports", "error",
    },
}


@pytest.mark.parametrize(
    "stream_cls",
    list(EXPECTED_SCHEMA_KEYS),
    ids=lambda cls: cls.__name__,
)
def test_schema_keys_match_docs(stream_cls: type) -> None:
    """Schema property keys match the Power BI REST API docs.

    If this test fails, either a field was removed/renamed by accident or
    the Power BI API added a field we should ingest. Update
    ``EXPECTED_SCHEMA_KEYS`` after cross-checking learn.microsoft.com.
    """
    actual = set(stream_cls.schema["properties"])
    assert actual == EXPECTED_SCHEMA_KEYS[stream_cls]


def test_all_streams_have_parity_test() -> None:
    """Every stream registered on the tap is covered by a parity test."""
    tap = TapPowerBI(config=SAMPLE_CONFIG, parse_env_config=False)
    registered = {type(s) for s in tap.discover_streams()}
    covered = set(EXPECTED_SCHEMA_KEYS)
    assert registered == covered, (
        f"Streams missing parity tests: {registered - covered}; "
        f"orphan parity tests: {covered - registered}"
    )


def test_powerbi_paginator() -> None:
    """The paginator follows ``@odata.nextLink`` and stops when absent."""
    paginator = PowerBIPaginator()

    response = Response()
    response._content = json.dumps(  # noqa: SLF001
        {"value": [], "@odata.nextLink": "https://api.powerbi.com/next"}
    ).encode()
    paginator.advance(response)
    assert not paginator.finished
    assert paginator.current_value.geturl() == "https://api.powerbi.com/next"

    response._content = json.dumps({"value": []}).encode()  # noqa: SLF001
    paginator.advance(response)
    assert paginator.finished
