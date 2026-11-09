#!/usr/bin/env bash
# Builds social-sim.zip for upload at claude.ai (Settings > Skills).
# SKILL.md must sit directly inside the single top-level folder: social-sim/SKILL.md
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/social-sim.zip"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
D="$TMP/social-sim"
mkdir -p "$D/data"
cp -r "$ROOT/.claude/skills/social-sim/." "$D/"
cp -r "$ROOT/bin" "$ROOT/src" "$ROOT/pyproject.toml" "$D/"
touch "$D/data/.gitkeep"
find "$D" -name __pycache__ -prune -exec rm -rf {} +
rm -f "$OUT"
(cd "$TMP" && zip -qr "$OUT" social-sim)
unzip -l "$OUT" | grep -E "SKILL.md|bin/socialsim"
