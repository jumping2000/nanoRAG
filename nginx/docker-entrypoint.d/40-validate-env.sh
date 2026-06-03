#!/bin/sh
set -eu

HTPASSWD_FILE="/etc/nginx/auth/.htpasswd"

if [ ! -f "$HTPASSWD_FILE" ]; then
  echo "Missing htpasswd file at $HTPASSWD_FILE" >&2
  exit 1
fi

if [ ! -s "$HTPASSWD_FILE" ]; then
  echo "htpasswd file is empty: $HTPASSWD_FILE" >&2
  exit 1
fi

: "${MCP_API_KEY:?MCP_API_KEY must be set for /mcp exposure}"

MCP_HTTP_URL="${MCP_HTTP_URL:-http://mcp:${MCP_HTTP_PORT:-8100}/mcp}"
case "$MCP_HTTP_URL" in
  http://*|https://*) ;;
  *)
    echo "MCP_HTTP_URL must start with http:// or https://" >&2
    exit 1
    ;;
esac

export MCP_HTTP_URL
