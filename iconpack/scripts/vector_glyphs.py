"""Hand-crafted vector glyphs for system apps (no brand SVG available).

Each function returns a mode-'L' PIL mask at the requested size where 255 = glyph.
Glyphs are drawn centered in the canvas with ~78% footprint, intended to be
scaled down by the renderer to the pack's glyph size.
"""
from PIL import Image, ImageDraw, ImageChops, ImageFilter
import math


def _new(size):
    return Image.new("L", (size, size), 0)


def _rot_paste(base, layer, angle):
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, expand=False)
    return ImageChops.lighter(base, layer)


def _ring(size, r_out, r_in, cx=None, cy=None):
    cx, cy = (size / 2, size / 2) if cx is None else (cx, cy)
    m = _new(size)
    d = ImageDraw.Draw(m)
    d.ellipse([cx - r_out, cy - r_out, cx + r_out, cy + r_out], fill=255)
    d.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], fill=0)
    return m


def glyph_phone(size):
    """Handset: thick arc band with rounded caps."""
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    cx, cy = s * 0.5, s * 0.56
    r_out, r_in = s * 0.36, s * 0.20
    # annular sector (arc band) on the left/bottom side
    d.pieslice([cx - r_out, cy - r_out, cx + r_out, cy + r_out], 110, 250, fill=255)
    d.pieslice([cx - r_in, cy - r_in, cx + r_in, cy + r_in], 0, 360, fill=0)
    # rounded caps at the two arc ends
    rm = (r_out + r_in) / 2
    cap_r = (r_out - r_in) / 2
    for ang in (110, 250):
        a = math.radians(ang)
        ex, ey = cx + rm * math.cos(a), cy + rm * math.sin(a)
        d.ellipse([ex - cap_r, ey - cap_r, ex + cap_r, ey + cap_r], fill=255)
    # rotate the whole handset like a classic phone icon
    return m.rotate(45, resample=Image.BICUBIC)


def glyph_messages(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = s * 0.12, s * 0.16, s * 0.88, s * 0.68
    r = s * 0.13
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=255)
    # tail
    tx = s * 0.30
    d.polygon([(tx, y1 - 2), (tx + s * 0.16, y1 - 2), (tx - s * 0.04, y1 + s * 0.14)], fill=255)
    return m


def glyph_contacts(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    # head
    hr = s * 0.135
    d.ellipse([s * 0.5 - hr, s * 0.18, s * 0.5 + hr, s * 0.18 + 2 * hr], fill=255)
    # shoulders: half ellipse
    d.pieslice([s * 0.5 - s * 0.30, s * 0.46, s * 0.5 + s * 0.30, s * 0.46 + s * 0.58], 180, 360, fill=255)
    return m


def glyph_camera(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    # top bump
    d.rounded_rectangle([s * 0.35, s * 0.19, s * 0.65, s * 0.33], radius=s * 0.04, fill=255)
    # body
    d.rounded_rectangle([s * 0.11, s * 0.28, s * 0.89, s * 0.80], radius=s * 0.09, fill=255)
    # lens punch-out: ring
    d.ellipse([s * 0.5 - s * 0.155, s * 0.54 - s * 0.155, s * 0.5 + s * 0.155, s * 0.54 + s * 0.155], fill=0)
    d.ellipse([s * 0.5 - s * 0.10, s * 0.54 - s * 0.10, s * 0.5 + s * 0.10, s * 0.54 + s * 0.10], fill=255)
    return m


def glyph_gallery(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = s * 0.12, s * 0.16, s * 0.88, s * 0.84
    d.rounded_rectangle([x0, y0, x1, y1], radius=s * 0.09, fill=255)
    # punch inner frame
    d.rounded_rectangle([x0 + s * 0.07, y0 + s * 0.07, x1 - s * 0.07, y1 - s * 0.07], radius=s * 0.05, fill=0)
    # sun
    sr = s * 0.06
    d.ellipse([s * 0.33 - sr, s * 0.35 - sr, s * 0.33 + sr, s * 0.35 + sr], fill=255)
    # mountains (clip to inner area via mask)
    inner = Image.new("L", (s, s), 0)
    di = ImageDraw.Draw(inner)
    di.rounded_rectangle([x0 + s * 0.07, y0 + s * 0.07, x1 - s * 0.07, y1 - s * 0.07], radius=s * 0.05, fill=255)
    mount = Image.new("L", (s, s), 0)
    dm = ImageDraw.Draw(mount)
    dm.polygon([(s * 0.10, s * 0.80), (s * 0.42, s * 0.44), (s * 0.62, s * 0.70), (s * 0.72, s * 0.58), (s * 0.92, s * 0.82), (s * 0.92, s * 0.9), (s * 0.10, s * 0.9)], fill=255)
    mount = ImageChops.multiply(mount.convert("L"), inner)
    m = ImageChops.lighter(m, mount.point(lambda v: 255 if v > 8 else 0))
    return m


def glyph_settings(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    # teeth: 8 stubby rounded rectangles
    tw, th = s * 0.20, s * 0.26
    for i in range(8):
        layer = _new(s)
        dl = ImageDraw.Draw(layer)
        dl.rounded_rectangle([s * 0.5 - tw / 2, s * 0.5 - s * 0.38 - th / 2, s * 0.5 + tw / 2, s * 0.5 - s * 0.38 + th / 2], radius=tw * 0.35, fill=255)
        m = _rot_paste(m, layer, i * 45)
    # body ring
    d2 = ImageDraw.Draw(m)
    d2.ellipse([s * 0.5 - s * 0.31, s * 0.5 - s * 0.31, s * 0.5 + s * 0.31, s * 0.5 + s * 0.31], fill=255)
    d2.ellipse([s * 0.5 - s * 0.125, s * 0.5 - s * 0.125, s * 0.5 + s * 0.125, s * 0.5 + s * 0.125], fill=0)
    return m


def glyph_clock(size):
    s = size
    m = _ring(s, s * 0.39, s * 0.315)
    d = ImageDraw.Draw(m)
    # hour hand (up), minute hand (right)
    w = s * 0.06
    d.rounded_rectangle([s * 0.5 - w / 2, s * 0.5 - s * 0.20, s * 0.5 + w / 2, s * 0.5], radius=w / 2, fill=255)
    layer = _new(s)
    dl = ImageDraw.Draw(layer)
    dl.rounded_rectangle([s * 0.5 - w / 2, s * 0.5 - s * 0.27, s * 0.5 + w / 2, s * 0.5], radius=w / 2, fill=255)
    m = _rot_paste(m, layer, 90)
    d = ImageDraw.Draw(m)
    d.ellipse([s * 0.5 - s * 0.05, s * 0.5 - s * 0.05, s * 0.5 + s * 0.05, s * 0.5 + s * 0.05], fill=255)
    return m


def glyph_calculator(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = s * 0.20, s * 0.10, s * 0.80, s * 0.90
    d.rounded_rectangle([x0, y0, x1, y1], radius=s * 0.08, fill=255)
    # display punch-out
    d.rounded_rectangle([x0 + s * 0.07, y0 + s * 0.07, x1 - s * 0.07, y0 + s * 0.20], radius=s * 0.03, fill=0)
    # button grid punch-outs (3 cols x 3 rows)
    bw = s * 0.075
    for r in range(3):
        for c in range(3):
            bx = s * 0.305 + c * s * 0.155
            by = s * 0.43 + r * s * 0.155
            d.rounded_rectangle([bx - bw, by - bw, bx + bw, by + bw], radius=bw * 0.45, fill=0)
    return m


def glyph_calendar(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = s * 0.13, s * 0.18, s * 0.87, s * 0.86
    d.rounded_rectangle([x0, y0, x1, y1], radius=s * 0.08, fill=255)
    # binder slots
    for bx in (s * 0.32, s * 0.68):
        d.rounded_rectangle([bx - s * 0.035, s * 0.10, bx + s * 0.035, s * 0.26], radius=s * 0.035, fill=255)
    # header separator punch-out
    d.rectangle([x0, y0 + s * 0.17, x1, y0 + s * 0.215], fill=0)
    # date dot punch-outs
    dw = s * 0.045
    for r in range(2):
        for c in range(3):
            bx = s * 0.30 + c * s * 0.20
            by = s * 0.53 + r * s * 0.17
            d.ellipse([bx - dw, by - dw, bx + dw, by + dw], fill=0)
    return m


def glyph_files(size):
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)
    # folder tab + body
    d.rounded_rectangle([s * 0.11, s * 0.20, s * 0.48, s * 0.38], radius=s * 0.05, fill=255)
    d.rounded_rectangle([s * 0.11, s * 0.28, s * 0.89, s * 0.82], radius=s * 0.07, fill=255)
    return m


SYSTEM_GLYPHS = {
    "phone": glyph_phone,
    "messages": glyph_messages,
    "contacts": glyph_contacts,
    "camera": glyph_camera,
    "gallery": glyph_gallery,
    "settings": glyph_settings,
    "clock": glyph_clock,
    "calculator": glyph_calculator,
    "calendar": glyph_calendar,
    "files": glyph_files,
}


def aura_launcher_glyph(size):
    """Sparkle/star mark for the pack's own launcher icon."""
    s = size
    m = _new(s)
    d = ImageDraw.Draw(m)

    def sparkle(cx, cy, R):
        # concave 4-point star via quadratic-ish polygons (dense sampling)
        pts = []
        n = 240
        for i in range(n):
            t = i / n * 2 * math.pi
            # radius modulation: pinch toward 0 between cardinal points
            k = abs(math.cos(2 * t)) ** 0.62
            rr = R * (0.06 + 0.94 * k)
            pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
        d.polygon(pts, fill=255)

    sparkle(s * 0.46, s * 0.54, s * 0.32)
    sparkle(s * 0.75, s * 0.24, s * 0.10)
    return m
