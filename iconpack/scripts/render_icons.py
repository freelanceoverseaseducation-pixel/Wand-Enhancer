#!/usr/bin/env python3
"""Render the Aura Icons pack PNGs.

Pipeline per icon:
  brand SVG (or hand-crafted vector glyph) -> supersampled polygon mask
  -> squircle background (solid or gradient) -> composite -> 192px PNG.
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageChops

from vector_glyphs import SYSTEM_GLYPHS, aura_launcher_glyph

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "generated")
SS = 2  # supersampling factor
RASTER = 512 * SS


# ---------------------------------------------------------------- svg -> mask
def _edges(poly, ox, oy, scale):
    pts = [(ox + x * scale, oy + y * scale) for x, y in poly]
    pts.append(pts[0])
    edges = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if y0 == y1:
            continue
        if y0 > y1:
            x0, y0, x1, y1 = x1, y1, x0, y0
            d = -1.0
        else:
            d = 1.0
        edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), d))
    return edges


def rasterize_winding(polys, transform, size, rule="nonzero"):
    """Scanline rasterizer with nonzero / evenodd fill rules at `size` resolution."""
    (ox, oy), scale = transform
    edges = []
    for poly in polys:
        edges.extend(_edges(poly, ox, oy, scale))
    buf = np.zeros((size, size), dtype=np.int32)
    if not edges:
        return Image.fromarray(buf.astype(np.uint8), "L")
    ys0 = np.array([e[0] for e in edges])
    ys1 = np.array([e[1] for e in edges])
    xs = np.array([e[2] for e in edges])
    sl = np.array([e[3] for e in edges])
    dr = np.array([e[4] for e in edges])
    y_min = max(0, int(math.floor(ys0.min())))
    y_max = min(size, int(math.ceil(ys1.max())))
    for y in range(y_min, y_max):
        yc = y + 0.5
        hit = (ys0 <= yc) & (yc < ys1)
        if not hit.any():
            continue
        hx = xs[hit] + (yc - ys0[hit]) * sl[hit]
        hd = dr[hit]
        order = np.argsort(hx)
        hx, hd = hx[order], hd[order]
        # per-column winding: edges whose crossing lies left of/at column edge
        pxs = np.floor(hx).astype(np.int64)
        np.clip(pxs, 0, size - 1, out=pxs)
        delta = np.bincount(pxs, weights=hd, minlength=size).astype(np.int32)
        winding = np.cumsum(delta)
        if rule == "nonzero":
            fill = winding != 0
        else:
            parity = np.cumsum(np.bincount(pxs, minlength=size)) % 2
            fill = parity == 1
        buf[y][fill] += 1
    return Image.fromarray(np.where(buf > 0, 255, 0).astype(np.uint8), "L")


def polys_to_mask(polys, transform):
    """Rasterize polygons at RASTER resolution with proper nonzero winding fill."""
    return rasterize_winding(polys, transform, RASTER, rule="nonzero")


def fit_transform(bbox, glyph_px):
    """viewBox(24x24) bbox -> (offset, scale) centering the glyph in RASTER space."""
    minx, miny, maxx, maxy = bbox
    w, h = maxx - minx, maxy - miny
    scale = glyph_px / max(w, h)
    cx, cy = RASTER / 2, RASTER / 2
    ox = cx - (minx + w / 2) * scale
    oy = cy - (miny + h / 2) * scale
    return (ox, oy), scale


# ---------------------------------------------------------------- backgrounds
def squircle_mask(size, power=4.0):
    ax = np.linspace(-1.0, 1.0, size)
    X, Y = np.meshgrid(ax, ax)
    m = (np.abs(X) ** power + np.abs(Y) ** power) <= 1.0
    return Image.fromarray((m * 255).astype(np.uint8), "L")


def solid_bg(size, hexcolor):
    img = Image.new("RGB", (size, size), hexcolor)
    return img


def gradient_bg(size, stops, angle=45.0):
    """stops: list of (t, '#RRGGBB'); linear gradient at given angle."""
    ax = np.linspace(0.0, 1.0, size)
    X, Y = np.meshgrid(ax, ax)
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    proj = X * dx + Y * dy
    proj = (proj - proj.min()) / max(1e-9, (proj.max() - proj.min()))
    rgb = np.zeros((size, size, 3), dtype=np.float64)
    ts = [s[0] for s in stops]
    cs = np.array([[int(s[1][i:i + 2], 16) for i in (1, 3, 5)] for s in stops], dtype=np.float64)
    flat = proj.ravel()
    idx = np.clip(np.searchsorted(ts, flat) - 1, 0, len(ts) - 2)
    t0, t1 = np.array(ts)[idx], np.array(ts)[idx + 1]
    f = ((flat - t0) / np.maximum(1e-9, t1 - t0))[:, None]
    c0, c1 = cs[idx], cs[idx + 1]
    rgb = (c0 + (c1 - c0) * f).reshape(size, size, 3)
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


INSTAGRAM_STOPS = [(0.0, "#FEDA75"), (0.25, "#FA7E1E"), (0.5, "#D62976"), (0.75, "#962FBF"), (1.0, "#4F5BD4")]
AURA_STOPS = [(0.0, "#4338CA"), (0.55, "#7C3AED"), (1.0, "#C026D3")]


# ---------------------------------------------------------------- composition
def compose_icon(bg_img, glyph_mask_512, glyph_color="#FFFFFF", out_size=192):
    size = 512
    mask = squircle_mask(size).resize((size, size), Image.LANCZOS)
    bg = bg_img.resize((size, size), Image.LANCZOS)
    glyph = glyph_mask_512.resize((size, size), Image.LANCZOS)
    glyph = ImageChops.multiply(glyph, mask)
    img = bg.convert("RGBA")
    gcol = Image.new("RGBA", (size, size), glyph_color)
    img = Image.composite(gcol, img, glyph)
    img.putalpha(mask)
    return img.resize((out_size, out_size), Image.LANCZOS)


def _polys_from_paths(paths):
    polys = []
    for path in paths:
        cur = None
        for seg in path.segments():
            tname = type(seg).__name__
            if tname == "Move":
                if cur is not None and len(cur) >= 3:
                    polys.append(cur)
                cur = [tuple(seg.end)] if hasattr(seg, "end") else []
            elif tname == "Close":
                if cur is not None and len(cur) >= 3:
                    polys.append(cur)
                cur = None
            else:
                if cur is None:
                    cur = [tuple(seg.start)] if hasattr(seg, "start") else []
                try:
                    length = seg.length(error=5) if hasattr(seg, "length") else 8
                except Exception:
                    length = 8
                n = max(6, min(64, int(length / 0.6)))
                pts = seg.npoint(np.linspace(0.0, 1.0, n))
                cur.extend((float(x), float(y)) for x, y in pts)
        if cur is not None and len(cur) >= 3:
            polys.append(cur)
    return polys


_HANDSET = {}


def _whatsapp_handset():
    """Reuse WhatsApp's handset subpath as the system 'phone' glyph."""
    if _HANDSET:
        return _HANDSET["polys"], _HANDSET["bbox"]
    from svgelements import SVG, Path

    svg_path = os.path.join(ROOT, "vendor", "icons", "whatsapp.svg")
    svg = SVG.parse(svg_path)
    paths = [e for e in svg.elements(lambda e: isinstance(e, Path))]
    polys = _polys_from_paths(paths)
    # handset = smallest subpath (~half the icon width, centered)
    best = min(polys, key=lambda p: (max(x for x, _ in p) - min(x for x, _ in p)))
    xs = [x for x, _ in best]
    ys = [y for x, y in best]
    bbox = (min(xs), min(ys), max(xs), max(ys))
    _HANDSET["polys"], _HANDSET["bbox"] = [best], bbox
    return [best], bbox


def render_pack(pack):
    os.makedirs(os.path.join(OUT, "icons"), exist_ok=True)
    style = pack["style"]
    out_size = style["output"]
    glyph_scale = style["glyph_scale"]

    colors = {}
    bc = os.path.join(ROOT, "vendor", "brand_colors.json")
    if os.path.exists(bc):
        colors = json.load(open(bc))

    names = []
    for icon in pack["icons"]:
        name = icon["drawable"]
        kind = icon.get("kind")
        glyph_col = icon.get("glyph_color", "#FFFFFF")

        gs = icon.get("glyph_scale", glyph_scale)
        if kind == "system":
            if name == "phone":
                polys, bbox = _whatsapp_handset()
                transform = fit_transform(bbox, 512 * gs * SS)
                gmask = polys_to_mask(polys, transform)
                gmask = gmask.resize((512, 512), Image.LANCZOS)
            else:
                gmask = SYSTEM_GLYPHS[name](512)
            bgc = icon["bg"]
            bg = solid_bg(512, bgc)
        else:
            svg_path = os.path.join(ROOT, "vendor", "icons", f"{name}.svg")
            from svgelements import SVG, Path
            svg = SVG.parse(svg_path)
            paths = [e for e in svg.elements(lambda e: isinstance(e, Path))]
            minx, miny, maxx, maxy = 1e9, 1e9, -1e9, -1e9
            for p in paths:
                b = p.bbox()
                minx, miny = min(minx, b[0]), min(miny, b[1])
                maxx, maxy = max(maxx, b[2]), max(maxy, b[3])
            transform = fit_transform((minx, miny, maxx, maxy), 512 * gs * SS)
            gmask = polys_to_mask(_polys_from_paths(paths), transform)
            gmask = gmask.resize((512, 512), Image.LANCZOS)

            bgspec = icon.get("bg")
            if bgspec == "gradient_instagram":
                bg = gradient_bg(512, INSTAGRAM_STOPS, angle=45.0)
            else:
                hexv = bgspec or colors.get(name, "#3B82F6")
                bg = solid_bg(512, hexv)

        img = compose_icon(bg, gmask, glyph_col, out_size)
        img.save(os.path.join(OUT, "icons", f"{name}.png"))
        names.append(name)
        print("rendered", name)
    return names


def render_launcher(pack):
    bg = gradient_bg(512, AURA_STOPS, angle=45.0)
    gmask = aura_launcher_glyph(512)
    img = compose_icon(bg, gmask, "#FFFFFF", pack["style"]["output"])
    os.makedirs(OUT, exist_ok=True)
    img.save(os.path.join(OUT, "ic_launcher.png"))
    print("rendered ic_launcher")


def render_preview(pack):
    names = [i["drawable"] for i in pack["icons"]]
    cols = 8
    cell, pad = 128, 24
    rows = math.ceil((len(names) + 1) / cols)
    w = pad + cols * (cell + pad)
    h = pad + rows * (cell + pad)
    sheet = Image.new("RGB", (w, h), "#0B1020")
    launcher = Image.open(os.path.join(OUT, "ic_launcher.png"))
    sheet.paste(launcher, (pad, pad), launcher)
    for idx, name in enumerate(names):
        icon = Image.open(os.path.join(OUT, "icons", f"{name}.png"))
        r = (idx + 1) // cols
        c = (idx + 1) % cols
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad)
        sheet.paste(icon, (x, y), icon)
    sheet.save(os.path.join(OUT, "preview.png"))
    print("rendered preview")


if __name__ == "__main__":
    pack = json.load(open(os.path.join(ROOT, "pack.json")))
    render_pack(pack)
    render_launcher(pack)
    render_preview(pack)
