#!/bin/bash
# Shared implementation of the make target fill-toolkit-translations, see
# makefile/l10n.mk. Adds translations shipped by the toolkits to the app's PO
# file. Only msgids present in the app's POT template are added, existing
# (non-fuzzy) translations of the app are never changed.
#
# Conflicts, i.e. existing translations differing from the toolkit's, are
# reported as warnings and left alone unless --force is given. With --check
# nothing is written, missing and conflicting translations are only listed.
#
# Usage: fill-toolkit-translations.sh [--force] [--check] LANG TEMPLATE APP_PO TOOLKIT_PO...
set -e

force=false check=false
while [ $# -gt 0 ]; do
  case "$1" in
    --force) force=true; shift ;;
    --check) check=true; shift ;;
    --) shift; break ;;
    -*) echo "fill-toolkit-translations: unknown option $1" >&2; exit 1 ;;
    *) break ;;
  esac
done

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

mkdir "$work/in"
if [ -f "$app_po" ]; then
  cp "$app_po" "$work/in/app"
else
  msginit --no-translator --locale="$lang" --input="$template" --output-file="$work/in/app"
fi

# Toolkit translations restricted to msgids of the template.
msgcat --use-first -o "$work/in/all-toolkit" "${sources[@]}"
msgmerge --quiet --no-fuzzy-matching -o "$work/merged.po" "$work/in/all-toolkit" "$template"
msgattrib --translated --no-fuzzy --no-obsolete -o "$work/in/toolkit" "$work/merged.po"
msgattrib --translated --no-fuzzy --no-obsolete -o "$work/in/keep" "$work/in/app"

# List the msgids of a PO file, skipping the header entry.
list_ids() {
  [ -f "$1" ] || return 0
  msgattrib --no-wrap "$1" | awk '/^msgid "/ && $0 != "msgid \"\"" { print "  " substr($0, 7) }'
}

# Like list_ids, but with the msgstr lines.
list_entries() {
  [ -f "$1" ] || return 0
  msgattrib --no-wrap "$1" | awk '/^msgid "/ { skip = ($0 == "msgid \"\""); if (!skip) print "  " $0; next } (/^msgstr "/ || /^"/) && !skip { print "    " $0 }'
}

# msgcat without --use-first flags entries with differing msgstrs as fuzzy.
(cd "$work/in" && msgcat -o ../joined.po keep toolkit)
msgattrib --only-fuzzy --no-wrap -o "$work/conflicts.po" "$work/joined.po"
msgcomm --less-than=2 -o "$work/only.po" "$work/in/toolkit" "$work/in/keep"
msgcomm --more-than=1 -o "$work/missing.po" "$work/only.po" "$work/in/toolkit"

echo "Missing translations available from the toolkits ($lang):"
list_ids "$work/missing.po"
if [ -n "$(list_entries "$work/conflicts.po")" ]; then
  if $force; then
    echo "Conflicting translations, overwritten by the toolkit's ($lang):" >&2
  else
    echo "WARNING: conflicting translations, app translation kept, use --force to overwrite ($lang):" >&2
  fi
  # The msgstr holds the app's and the toolkit's translation, separated by markers.
  list_entries "$work/conflicts.po" >&2
fi

$check && exit 0

if $force; then
  msgcat --use-first -o "$work/result.po" "$work/in/toolkit" "$work/in/keep" "$work/in/app"
else
  msgcat --use-first -o "$work/result.po" "$work/in/keep" "$work/in/toolkit" "$work/in/app"
fi
mkdir -p "$(dirname "$app_po")"
cat "$work/result.po" > "$app_po"
