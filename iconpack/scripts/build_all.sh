#!/usr/bin/env bash
# One-command rebuild of the Aura Icons APK.
# Requirements: python venv with pillow/numpy/svgelements/androguard/cryptography,
# node with apk_sign_ts (npm install in iconpack/).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-/home/user/.venv/bin/python}

echo "== rendering icons =="
"$PY" scripts/render_icons.py > /dev/null
echo "== assembling unsigned apk =="
"$PY" scripts/build_apk.py
echo "== signing (v1+v2+v3) =="
node scripts/sign_apk.mjs output/aura-unsigned.apk "output/AuraIcons-v${VERSION_NAME:-1.0}.apk" keystore
rm -f output/aura-unsigned.apk
echo "== verifying =="
"$PY" scripts/verify_apk.py "output/AuraIcons-v${VERSION_NAME:-1.0}.apk"
echo "DONE"
