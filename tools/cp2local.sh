#!/usr/bin/env bash
set -euo pipefail

# ====== CONFIG: ändra dessa ======
REMOTE_USER="u93142@sp.se"          # remote användare
REMOTE_HOST="srv-l055-t"            # remote host (DNS eller IP)
REMOTE_PORT="22"                    # SSH-port (22 om standard)
# ===============================

usage() {
  cat <<EOF
Usage:
  $(basename "$0") <path> [-o <local_dir>] [-p]

Examples:
  $(basename "$0") /home/u93142@sp.se/https_hello/cert.pem
  $(basename "$0") /var/log/syslog -o ~/Downloads
  $(basename "$0") /etc/nginx/nginx.conf -p   # behåll katalogstruktur

Options:
  -o <local_dir>  Spara i angiven lokal katalog (default: .)
  -p              Behåll katalogstruktur under local_dir (skapar mappar)
  -h              Visa denna hjälp
EOF
}

LOCAL_DIR="."
PRESERVE_PATH="0"

# Parse options
while getopts ":o:ph" opt; do
  case "$opt" in
    o) LOCAL_DIR="$OPTARG" ;;
    p) PRESERVE_PATH="1" ;;
    h) usage; exit 0 ;;
    \?) echo "Unknown option: -$OPTARG" >&2; usage; exit 2 ;;
    :)  echo "Option -$OPTARG requires an argument" >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

REMOTE_PATH="$1"

# Basic sanity checks
if [[ "$REMOTE_PATH" != /* ]]; then
  echo "❌ Remote path måste vara absolut (börja med /). Du angav: $REMOTE_PATH" >&2
  exit 2
fi

mkdir -p "$LOCAL_DIR"

REMOTE="${REMOTE_USER}@${REMOTE_HOST}"

if [[ "$PRESERVE_PATH" == "1" ]]; then
  # Skapa lokal katalogstruktur under LOCAL_DIR
  # Ex: /etc/nginx/nginx.conf -> LOCAL_DIR/etc/nginx/nginx.conf
  REL_PATH="${REMOTE_PATH#/}"  # ta bort ledande /
  DEST_DIR="$(dirname "$LOCAL_DIR/$REL_PATH")"
  mkdir -p "$DEST_DIR"
  DEST_PATH="$LOCAL_DIR/$REL_PATH"

  echo "⬇️  Hämtar (bevarar path): $REMOTE:$REMOTE_PATH -> $DEST_PATH"
  scp -P "$REMOTE_PORT" "$REMOTE:$REMOTE_PATH" "$DEST_PATH"
else
  echo "⬇️  Hämtar: $REMOTE:$REMOTE_PATH -> $LOCAL_DIR/"
  scp -P "$REMOTE_PORT" "$REMOTE:$REMOTE_PATH" "$LOCAL_DIR/"
fi

echo "✅ Klar."

