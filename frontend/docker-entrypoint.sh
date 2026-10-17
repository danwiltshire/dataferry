#!/bin/sh
set -e

# Runs as one of nginx's /docker-entrypoint.d/ scripts (sourced by the base
# image's own entrypoint before it starts nginx), so it must not exec/replace
# the process itself. Regenerates env.js from the container's actual env vars
# at start, so the API base URL is configurable without rebuilding the bundle.
cat > /usr/share/nginx/html/env.js <<EOF
window.__ENV__ = {
  API_BASE_URL: "${API_BASE_URL:-http://localhost:8000}",
};
EOF

