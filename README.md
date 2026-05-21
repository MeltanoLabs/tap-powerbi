# tap-powerbi

`tap-powerbi` is a Singer tap for [Microsoft Power BI](https://learn.microsoft.com/en-us/rest/api/power-bi/).

Built with the [Meltano Tap SDK](https://sdk.meltano.com) for Singer Taps.

## Installation

Install from GitHub:

```bash
uv tool install git+https://github.com/MeltanoLabs/tap-powerbi.git@v0.1.0
```

## Configuration

### Accepted Config Options

| Setting | Required | Default | Description |
|---|---|---|---|
| `tenant_id` | conditional | — | Azure AD tenant ID. Required for service-principal auth. |
| `client_id` | yes | — | Azure AD application (client) ID. |
| `client_secret` | conditional | — | Azure AD application client secret. Omit when using the Matatika OAuth proxy (the proxy holds it). |
| `refresh_token` | conditional | — | OAuth refresh token. Provide instead of `tenant_id` for delegated-user auth, or together with `oauth_credentials.refresh_proxy_url` for the proxy flow. |
| `oauth_credentials.refresh_proxy_url` | conditional | — | Matatika OAuth proxy URL. When set, the tap POSTs the refresh token to this URL and the proxy returns a fresh access token. Used by the catalog "Connect with Microsoft" button. |
| `oauth_credentials.refresh_proxy_url_auth` | no | — | Authorization header value sent on the proxy refresh request (e.g. `Bearer …`). |
| `workspace_ids` | no | — | Optional array of workspace IDs to restrict discovery to. |
| `start_date` | no | — | Earliest timestamp for incremental streams (`dataset_refreshes`). |
| `api_url` | no | `https://api.powerbi.com/v1.0/myorg` | Power BI REST API base URL. Override for sovereign clouds (e.g. `https://api.powerbigov.us/v1.0/myorg`). |
| `admin_mode` | no | `false` | Use `/admin/*` routes for tenant-wide visibility. Requires `Tenant.Read.All` permission. Enriches `groups`, `datasets`, `reports`, `dashboards`, `dataflows` with admin-only fields (`createdDateTime`, `modifiedBy`, `users`, etc.). |

One of three `settings_group_validation` groups must be fully set:

- **Service principal:** `tenant_id`, `client_id`, `client_secret`
- **Delegated user (direct):** `client_id`, `client_secret`, `refresh_token`
- **Delegated user (Matatika OAuth proxy):** `oauth_credentials.refresh_proxy_url`, `refresh_token`, `client_id` — no `client_secret`; the proxy holds it.

A full list of supported settings and capabilities is available by running:

```bash
tap-powerbi --about
```

### Configure using environment variables

This Singer tap will automatically import any environment variables within the working directory's
`.env` if the `--config=ENV` is provided, such that config values will be considered if a matching
environment variable is set either in the terminal context or in the `.env` file.

### Source Authentication and Authorization

Three auth modes are supported.

#### Service principal (recommended for unattended runs)

1. Register an application in **Azure Active Directory**; capture its **Tenant ID**, **Client ID**, and **Client Secret**.
2. Grant the application Power BI REST API permissions (`Tenant.Read.All` or per-workspace permissions, depending on scope).
3. In the **Power BI Admin Portal → Tenant settings**, enable "Service principals can use Power BI APIs" and add the principal (or a security group containing it).
4. Add the principal to each workspace you want to sync.

#### Delegated user — direct (refresh token)

1. Register an application in Azure AD; capture its **Client ID** and **Client Secret**.
2. Run an OAuth consent flow once to mint a **Refresh Token**.
3. Provide `client_id`, `client_secret`, and `refresh_token` — leave `tenant_id` empty.

#### Delegated user — Matatika OAuth proxy ("Connect with Microsoft" button)

The Matatika catalog UI mints a refresh token using Matatika's own Azure AD application via PKCE. Microsoft binds refresh tokens to the client that minted them, so the tap cannot exchange the token directly — instead it POSTs the refresh token to a Matatika-hosted **OAuth proxy** that holds Matatika's `client_secret` and returns a fresh access token.

1. Click **Connect with Microsoft** in the Matatika catalog; the refresh token is captured for you.
2. The catalog YAML provides `client_id` (Matatika's Azure AD app), `refresh_token`, and `oauth_credentials.refresh_proxy_url`. **Do not** set `client_secret` — the proxy holds it.
3. Optionally, set `oauth_credentials.refresh_proxy_url_auth` if the proxy requires an `Authorization` header on the refresh call.

## Streams

Streams are grouped by Power BI REST API operation group.

| Stream | Path | Replication | Replication Key |
|---|---|---|---|
| **Workspace content** | | | |
| `groups` | `/groups` | Full Table | — |
| `datasets` | `/groups/{group_id}/datasets` | Full Table | — |
| `reports` | `/groups/{group_id}/reports` | Full Table | — |
| `dashboards` | `/groups/{group_id}/dashboards` | Full Table | — |
| `dataflows` | `/groups/{group_id}/dataflows` | Full Table | — |
| `dataset_refreshes` | `/groups/{group_id}/datasets/{dataset_id}/refreshes` | Incremental | `endTime` |
| `imports` | `/groups/{group_id}/imports` | Incremental | `updatedDateTime` |
| **Apps** | | | |
| `apps` | `/apps` | Full Table | — |
| `app_reports` | `/apps/{app_id}/reports` | Full Table | — |
| `app_dashboards` | `/apps/{app_id}/dashboards` | Full Table | — |
| **Deployment pipelines** | | | |
| `pipelines` | `/pipelines` | Full Table | — |
| `pipeline_stages` | `/pipelines/{pipeline_id}/stages` | Full Table | — |
| `pipeline_operations` | `/pipelines/{pipeline_id}/operations` | Incremental | `executionStartTime` |
| **Gateways** | | | |
| `gateways` | `/gateways` | Full Table | — |
| `gateway_datasources` | `/gateways/{gateway_id}/datasources` | Full Table | — |
| **Capacities** | | | |
| `capacities` | `/capacities` | Full Table | — |

### Caveats

- `dataset_refreshes` is automatically skipped for datasets where `isRefreshable=false`.
- `apps`, `app_reports`, `app_dashboards` — Power BI's `GET /apps` endpoint **does not support service-principal auth**. These streams require the delegated-user (refresh-token) flow.
- `gateways`, `gateway_datasources` — Power BI returns only gateways for which the caller has **gateway admin permissions**, regardless of Power BI tenant role. Add the principal as a gateway admin in the Power BI service to populate these streams.
- `admin_mode=true` switches `groups`, `datasets`, `reports`, `dashboards`, `dataflows`, `capacities` to their `/admin/*` route equivalents, populating audit fields (`createdDateTime`, `modifiedBy`, `users`, etc.). Requires `Tenant.Read.All`.

## Usage

You can easily run `tap-powerbi` by itself or in a pipeline using [Meltano](https://meltano.com/).

### Executing the Tap Directly

```bash
tap-powerbi --version
tap-powerbi --help
tap-powerbi --config CONFIG --discover > ./catalog.json
```

## Developer Resources

Follow these instructions to contribute to this project.

### Initialize your Development Environment

Prerequisites:

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
```

### Create and Run Tests

```bash
uv run pytest
```

The SDK's standard tap/stream tests run against the live Power BI API when credentials are present in the environment. In CI (where `CI=true`), they are skipped and only the local unit tests execute.

You can also test the `tap-powerbi` CLI interface directly using `uv run`:

```bash
uv run tap-powerbi --help
```

### Testing with [Meltano](https://www.meltano.com)

_**Note:** This tap will work in any Singer environment and does not require Meltano.
Examples here are for convenience and to streamline end-to-end orchestration scenarios._

```bash
# Install meltano
uv tool install meltano

# Test invocation
meltano invoke tap-powerbi --version

# Run a test EL pipeline
meltano run tap-powerbi target-jsonl
```

### SDK Dev Guide

See the [dev guide](https://sdk.meltano.com/en/latest/dev_guide.html) for more instructions on how to use the SDK to
develop your own taps and targets.
