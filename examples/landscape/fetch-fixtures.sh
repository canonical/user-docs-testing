#!/usr/bin/env bash
# Fetch the fixtures needed to try the Landscape example locally.
#
# Populates two gitignored folders next to this script:
#   docs/      the Landscape reference documentation under review
#   sources/   the source-of-truth checkouts the review compares against
#
# Public sources are cloned directly. PRIVATE sources (landscape-server, etc.)
# require your own access — clone them yourself into sources/<name>/ (see below).
# Anything not provided is treated by the review as unavailable: required private
# sources make their areas "blocked", optional ones make their areas "unsupported".
set -euo pipefail
cd "$(dirname "$0")"

DOCS_SRC="${LANDSCAPE_DOCS_REPO:-https://github.com/canonical/landscape-documentation.git}"

echo "==> docs/: Landscape reference documentation"
rm -rf docs && mkdir -p docs
tmp="$(mktemp -d)"
git clone --depth 1 --quiet "$DOCS_SRC" "$tmp"
cp -r "$tmp/docs/reference" docs/reference
rm -rf "$tmp"
# The generated HTTP API reference is excluded by the config; drop it here too.
rm -rf docs/reference/api
echo "    fetched $(find docs/reference -name '*.md' | wc -l) reference pages (api excluded)"

echo "==> sources/landscape-client (public)"
rm -rf sources && mkdir -p sources
git clone --depth 1 --quiet https://github.com/canonical/landscape-client.git sources/landscape-client
echo "    cloned landscape-client"

cat <<'EOF'

==> PRIVATE sources (optional — needed for full server-side coverage)
    Clone these yourself if you have access; otherwise their areas are reported
    as blocked (server) or unsupported (charm/ui):

      git clone --depth 1 git@github.com:canonical/landscape-server.git          sources/landscape-server
      git clone --depth 1 git@github.com:canonical/landscape-server-operator.git sources/landscape-server-operator
      git clone --depth 1 git@github.com:canonical/landscape-ui.git              sources/landscape-ui

Done. See README.md to run the review.
EOF
