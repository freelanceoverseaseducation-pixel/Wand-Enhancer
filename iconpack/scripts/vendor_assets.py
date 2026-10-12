#!/usr/bin/env python3
"""Vendor the exact SVG glyphs + brand colors we need into the repo,
so the icon pack build is fully reproducible without network access."""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV = "/tmp/simple-icons-develop"
V13 = "/tmp/si13"


def load_colors(base):
    out = {}
    for rel in ("data/simple-icons.json", "_data/simple-icons.json"):
        j = os.path.join(base, rel)
        if os.path.exists(j):
            data = json.load(open(j))
            icons = data["icons"] if isinstance(data, dict) else data
            if icons and "slug" in icons[0]:
                for it in icons:
                    out[it["slug"]] = it.get("hex", "").lower()
            else:
                # newer schema: title/hex; resolve slugs via slugs.md table
                title_hex = {it["title"]: it.get("hex", "").lower() for it in icons}
                md = os.path.join(base, "slugs.md")
                if os.path.exists(md):
                    import re
                    for m in re.finditer(r"^\|\s*`(.+?)`\s*\|\s*`(.+?)`\s*\|\s*$", open(md).read(), re.M):
                        title, slug = m.group(1), m.group(2)
                        if title in title_hex:
                            out[slug] = title_hex[title]
            break
    return out


def main():
    pack = json.load(open(os.path.join(ROOT, "pack.json")))
    colors = load_colors(DEV)
    colors.update(load_colors(V13))  # v13 fills gaps

    vendor_dir = os.path.join(ROOT, "vendor", "icons")
    os.makedirs(vendor_dir, exist_ok=True)

    baked = {}
    missing = []
    for icon in pack["icons"]:
        slug = icon.get("slug")
        if not slug:
            continue
        src_base = V13 if icon.get("source") == "v13" else DEV
        src = os.path.join(src_base, "icons", f"{slug}.svg")
        if not os.path.exists(src):
            # fall back to the other tree
            other = DEV if src_base is V13 else V13
            if os.path.exists(os.path.join(other, "icons", f"{slug}.svg")):
                src = os.path.join(other, "icons", f"{slug}.svg")
            else:
                missing.append(slug)
                continue
        shutil.copy(src, os.path.join(vendor_dir, f"{icon['drawable']}.svg"))
        hexv = colors.get(slug, "")
        if hexv:
            baked[icon["drawable"]] = "#" + hexv.upper()

    with open(os.path.join(ROOT, "vendor", "brand_colors.json"), "w") as f:
        json.dump(baked, f, indent=2, sort_keys=True)

    print(f"vendored {len(baked)} svgs/colors")
    if missing:
        print("MISSING:", missing)
        sys.exit(1)


if __name__ == "__main__":
    main()
