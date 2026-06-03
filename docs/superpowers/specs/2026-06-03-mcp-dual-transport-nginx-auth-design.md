# MCP Dual Transport With Nginx-Authenticated Public Access

**Date:** 2026-06-03  
**Status:** approved -> spec written  
**Scope:** Docker Compose public topology, MCP transport model, authentication boundaries

## Goal

Introduce a Docker Compose topology where `nginx` is the only public entry point, protects the UI and the backend HTTP API with Basic Auth backed by an `htpasswd` file, and exposes `/mcp` as a separate path protected only by `X-API-Key` validated against `MCP_API_KEY`.

The MCP runtime must support two transports:

- `stdio` for local or standalone MCP clients
- `streamable-http` for the dedicated MCP service used behind `nginx` in Docker Compose

## Decisions

1. `nginx` becomes the only public front door in Docker Compose.
2. The backend remains an HTTP API service, but it is reached publicly through `nginx`, not directly.
3. The MCP HTTP path is no longer proxied through the backend application layer.
4. Docker Compose runs MCP as a dedicated service in `streamable-http` mode.
5. `/mcp` is excluded from Basic Auth and requires only `X-API-Key`.
6. UI and non-MCP backend API routes require Basic Auth.
7. Basic Auth credentials are supplied to `nginx` through a mounted `htpasswd` file.
8. The MCP server itself does not implement HTTP authentication.
9. Invalid MCP transport configuration fails at startup with no implicit fallback.

## Non-Goals

- Implement authentication inside the MCP upstream service
- Route public MCP traffic through the backend application as a Python proxy
- Expose MCP on a separate public host or public port in Compose
- Support a silent fallback from one MCP transport to another when configuration is invalid
- Require `nginx` for manual local development outside Compose

## Architecture

The public Compose topology is:

- `nginx` published to the host
- `frontend` reachable only on the internal Docker network
- `backend` reachable only on the internal Docker network
- `mcp` reachable only on the internal Docker network
- shared data services and volumes unchanged

Traffic policy:

- `nginx -> frontend`: Basic Auth required
- `nginx -> backend`: Basic Auth required
- `nginx -> mcp` for `/mcp`: `X-API-Key` required, no Basic Auth

Runtime model:

- `stdio`: the MCP process runs as a local stdio server for direct MCP clients
- `streamable-http`: the MCP process runs as a dedicated HTTP service intended for Compose behind `nginx`

This removes the current ambiguity where the backend both serves application APIs and acts as the public MCP bridge.

## Compose Changes

### New or clarified service roles

- `nginx`: public reverse proxy and authentication boundary
- `frontend`: Next.js UI service behind `nginx`
- `backend`: FastAPI application service behind `nginx`
- `mcp`: dedicated MCP service running `streamable-http`

### Exposure rules

- Only `nginx` publishes ports to the host
- `frontend`, `backend`, and `mcp` do not publish public ports in the standard Compose path
- Internal service-to-service communication remains available on the Compose network

### Mounted auth material

- `nginx` mounts an `htpasswd` file read-only
- `nginx` receives `MCP_API_KEY` for `/mcp` request validation

## Authentication Policy

### UI and application API

All public UI routes and public backend HTTP API routes require Basic Auth at `nginx`.

Expected behavior:

- missing credentials -> `401 Unauthorized`
- wrong credentials -> `401 Unauthorized`
- valid credentials -> request forwarded to `frontend` or `backend`

### MCP HTTP path

`/mcp` is handled by a dedicated `nginx` location that does not inherit Basic Auth. It performs only `X-API-Key` validation against `MCP_API_KEY`.

Expected behavior:

- missing `X-API-Key` -> reject before proxying
- wrong `X-API-Key` -> reject before proxying
- valid `X-API-Key` -> request forwarded to the `mcp` upstream

The MCP upstream remains unaware of authentication and focuses only on MCP protocol handling and tool dispatch.

## MCP and Proxy Configuration Contract

The configuration contract is split on purpose.

### MCP runtime resolver

The MCP runtime uses a small Python-side resolver that validates only the variables needed to start the MCP server itself:

- `MCP_TRANSPORT`: `stdio` or `streamable-http`, default `stdio`
- `MCP_HTTP_PORT`: HTTP listen port for `streamable-http`, default `8100`

Rules:

- `MCP_TRANSPORT` must accept only the two allowed values
- `MCP_HTTP_PORT` must parse as an integer and be valid for binding
- no implicit fallback is allowed after configuration errors

### Proxy configuration inputs

The public proxy contract is owned by `nginx` startup configuration:

- `MCP_HTTP_URL`: optional explicit upstream URL override for deployments that do not use the standard internal Compose target
- `MCP_API_KEY`: deployment secret used by `nginx` for `/mcp` validation

Rules:

- `MCP_HTTP_URL` must be well-formed when provided
- `MCP_API_KEY` must be available to `nginx` whenever `/mcp` is exposed publicly

Responsibility boundaries:

- MCP runtime decides how it exposes the protocol
- `nginx` decides how public traffic is authenticated and routed
- backend application code does not participate in public MCP HTTP proxying

## Runtime Flows

### `stdio`

1. A local MCP client launches the MCP process directly.
2. The resolver selects `stdio`.
3. The MCP server starts on standard input and output.
4. Tool requests are dispatched directly inside the MCP runtime.

### `streamable-http`

1. The `mcp` service starts with `MCP_TRANSPORT=streamable-http`.
2. The resolver validates the HTTP port and starts the MCP server on the internal network.
3. A client sends an MCP HTTP request to `/mcp` on the public `nginx` host.
4. `nginx` validates `X-API-Key` against `MCP_API_KEY`.
5. If validation succeeds, `nginx` proxies the request to the `mcp` upstream.
6. The MCP upstream handles the request and dispatches the selected tool.

## Error Handling

Startup failures:

- invalid `MCP_TRANSPORT` -> fail immediately with an allowed-values message
- invalid `MCP_HTTP_PORT` in HTTP mode -> fail immediately
- bind failure in HTTP mode -> fail immediately
- malformed `MCP_HTTP_URL` -> fail immediately

Proxy failures:

- missing or invalid Basic Auth on UI/app API -> `401`
- missing or invalid `X-API-Key` on `/mcp` -> reject before proxying
- unavailable MCP upstream -> clear gateway error from `nginx`

Logging requirements:

- `MCP_API_KEY` must never be written to logs
- rendered configs or diagnostics must not print secrets in clear text

## Implementation Surfaces

Expected areas of change:

- `docker-compose.yml`
- new `nginx` configuration and mounted auth file path conventions
- MCP runtime entrypoint and configuration resolver
- backend MCP-related code and tests to remove or reduce the public proxy role
- documentation in `README.md`, `docs/mcp-server.md`, and Docker/development docs

## Testing

### Unit tests

- MCP config resolver defaults
- MCP config resolver invalid values
- MCP runtime startup selection for `stdio` vs `streamable-http`

### Integration tests

- `nginx` returns `401` for UI/API without valid Basic Auth
- `nginx` forwards UI/API with valid Basic Auth
- `/mcp` rejects missing `X-API-Key`
- `/mcp` rejects wrong `X-API-Key`
- `/mcp` forwards valid requests to the `mcp` service
- backend public contract no longer documents or depends on acting as the MCP HTTP proxy

### Deployment smoke checks

- only `nginx` publishes host ports in the standard Compose setup
- `frontend`, `backend`, and `mcp` remain reachable internally
- MCP tools are callable through `/mcp` with valid `X-API-Key`

## Documentation Updates

### `docs/mcp-server.md`

- describe the two transports with their distinct roles
- explain that Compose exposes MCP through `nginx`, not through the backend
- document `X-API-Key` authentication on `/mcp`
- document manual `stdio` startup for local standalone clients

### `README.md`

- update Compose topology and public entrypoint description
- document Basic Auth for UI/app API
- document the mounted `htpasswd` requirement

### Docker and development docs

- explain the `nginx` service role
- explain how to provide the `htpasswd` file in Compose
- describe the dedicated `mcp` service in HTTP mode

## Migration Notes

- Backward compatibility with the current backend `/mcp` proxy model is not required.
- Existing documentation that says the backend publicly exposes `/mcp` must be updated.
- Manual local development outside Compose remains supported without requiring `nginx`.

## Verification Checklist

- the public entrypoint is always `nginx` in Compose
- UI and non-MCP API routes require Basic Auth
- `/mcp` requires only `X-API-Key`
- MCP HTTP traffic no longer relies on backend application proxying
- the MCP server never enforces HTTP auth itself
- invalid configuration fails explicitly with no fallback