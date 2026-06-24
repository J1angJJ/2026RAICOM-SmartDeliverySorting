#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CAPTURE_DIR="${1:-"$SCRIPT_DIR/capture"}"
OUTPUT_DIR="${2:-"$SCRIPT_DIR/packages"}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_NAME="raicom_capture_${TIMESTAMP}.tar.gz"

if [[ ! -d "$CAPTURE_DIR" ]]; then
  echo "capture directory not found: $CAPTURE_DIR" >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

tar \
  --exclude='*.tmp' \
  --exclude='*.log' \
  -czf "$OUTPUT_DIR/$ARCHIVE_NAME" \
  -C "$(dirname "$CAPTURE_DIR")" \
  "$(basename "$CAPTURE_DIR")"

echo "archive created: $OUTPUT_DIR/$ARCHIVE_NAME"
