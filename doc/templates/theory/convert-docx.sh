#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

BASE_DIR="$PWD"
ATTACH_ROOT="attachments"

# Ensure base attachment dir exists
mkdir -p "$ATTACH_ROOT"

# Find all .docx files under BASE_DIR (recursively), handling spaces safely
find "$BASE_DIR" -type f -name '*.docx' -print0 | while IFS= read -r -d '' docx; do
  # Relative path (without BASE_DIR/ prefix if present)
  rel="$docx"
  case "$rel" in
    "$BASE_DIR"/*) rel="${rel#"$BASE_DIR"/}" ;;
  esac

  # Strip extension
  rel_noext="${rel%.*}"

  # Build a filesystem-safe prefix from the relative path:
  # - lowercase
  # - replace any non [a-z0-9] with '-'
  # - collapse multiple '-' and trim leading/trailing '-'
  prefix="$(printf '%s' "$rel_noext" \
            | tr '[:upper:]' '[:lower:]' \
            | sed -E 's/[^a-z0-9]+/-/g; s/-+/-/g; s/^-+//; s/-+$//')"

  media_dir="$ATTACH_ROOT/$prefix"
  mkdir -p "$media_dir"

  # Output Markdown path: same folder next to the .docx, same basename with .md. No spaces in filename.
  md_out="${docx%.*}.md"
  md_out=$(echo "$md_out" | sed 's/ /-/g')

  echo "Converting: $docx"
  echo "  -> Markdown: $md_out"
  echo "  -> Media:    $media_dir"

  pandoc -t markdown_strict \
    --extract-media="$media_dir" \
    "$docx" \
    -o "$md_out"
done

echo "Done."
