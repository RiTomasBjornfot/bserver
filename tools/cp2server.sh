#!/usr/bin/env bash
set -euo pipefail

DEST_HOST="SRV-L055-T"          # eller cytoserver om du har alias
DEST_USER="u93142@sp.se"
DEST_DIR="/home/u93142@sp.se/servers/hypelignum/indata"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") [-o <save_dir>] <send_file>

Examples:
  $(basename "$0") ./data/input.csv
  $(basename "$0") -o /home/u93142@sp.se/servers/hypelignum/indata ./data/input.csv

Options:
  -o <save_dir>  Remote katalog där filen sparas
  -h             Visa denna hjälp
EOF
}

while getopts ":o:h" opt; do
  case "$opt" in
    o) DEST_DIR="$OPTARG" ;;
    h) usage; exit 0 ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage; exit 2 ;;
    :) echo "Option -$OPTARG requires an argument" >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

if [[ -z "$DEST_DIR" ]]; then
  echo "Error: save_dir cannot be empty." >&2
  exit 2
fi

SRC="$1"

if [[ ! -f "$SRC" ]]; then
  echo "Error: file not found: $SRC" >&2
  exit 1
fi

echo "Uploading: $SRC"
echo "To: ${DEST_HOST}:${DEST_DIR}/ (as user: ${DEST_USER})"

# Skapa katalogen (om den redan finns gör mkdir -p inget)
ssh -o User="${DEST_USER}" "${DEST_HOST}" "mkdir -p \"${DEST_DIR}\""

# Upload (INGA citattecken runt remote path)
scp -p -o User="${DEST_USER}" "$SRC" "${DEST_HOST}:${DEST_DIR%/}/"

echo "Done."
