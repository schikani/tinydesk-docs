#!/bin/sh
# publish.sh - copy the site to the web server (Linux, macOS, WSL).
#
#   SERVER=me@myserver DEST=/var/www/tinydesk tools/publish.sh
#
# rsync sends only what changed and removes files that are gone from site/.
# Check the links first: python3 tools/check_links.py
set -e
: "${SERVER:?set SERVER, e.g. SERVER=me@myserver}"
DEST="${DEST:-/var/www/tinydesk}"
cd "$(dirname "$0")/.."
python3 tools/check_links.py
rsync -avz --delete --exclude '.DS_Store' site/ "$SERVER:$DEST/"
echo "published to $SERVER:$DEST"
