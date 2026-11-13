#!/bin/bash
# Shared implementation of the make target fill-toolkit-translations, see
# makefile/l10n.mk. Adds translations shipped by the toolkits to the app's PO
# file. Only msgids present in the app's POT template are added, existing
# (non-fuzzy) translations of the app are never changed.
#
# Usage: fill-toolkit-translations.sh LANG TEMPLATE APP_PO TOOLKIT_PO...
set -e

lang=$1 template=$2 app_po=$3
shift 3

if [ -z "$lang" ] || [ ! -f "$template" ]; then
  echo "fill-toolkit-translations: language and template \"$template\" are required." >&2; exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

sources=()
for po in "$@"; do
  if [ -f "$po" ]; then
    msgattrib --translated --no-fuzzy --no-obsolete -o "$work/$(basename "$po")" "$po"
    sources+=("$work/$(basename "$po")")
  else
    echo "fill-toolkit-translations: skipping missing $po" >&2
  fi
done
if [ ${#sources[@]} -eq 0 ]; then
  echo "fill-toolkit-translations: no toolkit translations found for \"$lang\"." >&2; exit 1
fi

if [ ! -f "$app_po" ]; then
  mkdir -p "$(dirname "$app_po")"
  msginit --no-translator --locale="$lang" --input="$template" --output-file="$app_po"
fi

# Toolkit translations restricted to msgids of the template.
msgcat --use-first -o "$work/toolkit.po" "${sources[@]}"
msgmerge --quiet --no-fuzzy-matching -o "$work/merged.po" "$work/toolkit.po" "$template"
msgattrib --translated --no-fuzzy --no-obsolete -o "$work/wanted.po" "$work/merged.po"
msgattrib --translated --no-fuzzy --no-obsolete -o "$work/keep.po" "$app_po"
msgcat --use-first -o "$work/result.po" "$work/keep.po" "$work/wanted.po" "$app_po"
cat "$work/result.po" > "$app_po"
