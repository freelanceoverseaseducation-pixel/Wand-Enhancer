# Aura Icons — Android icon pack

A custom icon pack for Android (44 themed apps + system icons), built for a
**Honor X9B**. Crisp, true-to-brand glyphs on colored squircle backgrounds.

`output/AuraIcons-v1.0.apk` is a normal, signed Android app — install it like
any APK and pick it in a supporting launcher.

## Install on your Honor X9B

1. Get `output/AuraIcons-v1.0.apk` onto the phone (download it from this chat,
   or copy it over USB / Drive / WhatsApp-to-yourself).
2. Open it with the **Files** app → tap the APK → allow
   *Install unknown apps* for that source → **Install**.
   (It is signed with a self-generated key, that is normal for side-loaded packs.)
3. **Important:** the stock Honor launcher cannot apply third-party icon packs.
   Install a launcher with icon-pack support from the Play Store, e.g.
   **Nova Launcher** or **Lawnchair** (both free).
4. Apply the pack:
   - **Nova Launcher:** long-press home → *Settings → Look & feel → Icon style → Icon theme → Aura Icons*.
   - **Lawnchair:** *Settings → Iconography → Icon pack → Aura Icons*.
   - **Smart Launcher / others:** look for *Icon packs / Icon theme* in settings.

Opening **Aura Icons** from the app drawer shows an in-app instructions screen.

## What's inside

- 44 app icons (WhatsApp, Instagram, YouTube, TikTok, Facebook, Messenger, X,
  Snapchat, Telegram, Discord, Spotify, Netflix, Amazon, Prime Video, Reddit,
  Pinterest, LinkedIn, PayPal, Uber, Airbnb, Booking, Flipkart, PhonePe,
  GPay, Paytm, Swiggy, Zomato, Chrome, Gmail, Maps, Drive, Photos, Play Store…)
  plus system icons (Phone, Messages, Camera, Gallery, Clock, Calculator,
  Calendar, Files, Settings, Contacts).
- `res/xml/appfilter.xml` — component→drawable mapping used by launchers.
- `res/xml/drawable.xml`, `themeinfo.xml`, `themecfg.xml` for launcher pickers.
- Signed with APK Signature Scheme v1 + v2 + v3 (key in `keystore/`).

## Rebuild from source

The whole pack is generated — no Android Studio/SDK needed. The build pipeline
is pure Python + Node: binary `AndroidManifest.xml` (AXML) writer,
`resources.arsc` writer, a minimal DEX writer for the instructions activity,
an aligned ZIP packer and `apk_sign_ts` for signing.

```bash
# one time setup
python3 -m venv .venv
.venv/bin/pip install pillow numpy svgelements androguard cryptography
cd iconpack && npm install          # apk_sign_ts

# build (renders icons, assembles, signs, verifies)
bash scripts/build_all.sh
```

- Icon art: brand glyphs from the vendored simple-icons SVGs
  (`vendor/icons`, CC0-style brand assets) + hand-drawn system glyphs
  (`scripts/vector_glyphs.py`), rendered by `scripts/render_icons.py`.
- To add an app: add an entry (slug + components) to `pack.json` and re-run
  the build. If the brand SVG isn't vendored yet, re-run
  `scripts/vendor_assets.py` with a simple-icons checkout.
- `scripts/verify_apk.py` re-parses everything (manifest, resources, dex,
  zip alignment, signatures) so a bad APK never reaches the phone.

### Versioning / updates

Bump `version_code`/`version_name` in `pack.json`, rebuild, and install the new
APK over the old one (same signing key, so no uninstall needed).
