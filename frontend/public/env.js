// Local dev default; the Docker image regenerates this file at container
// start (see docker-entrypoint.sh) so the API base URL is configurable
// without rebuilding the static bundle.
window.__ENV__ = {
  API_BASE_URL: "http://localhost:8000",
};
