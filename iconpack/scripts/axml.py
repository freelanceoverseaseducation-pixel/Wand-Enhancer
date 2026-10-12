"""Minimal Android binary XML (AXML) writer.

Implements the subset needed for AndroidManifest.xml and res/xml resources:
string pool (UTF-8), resource-id map, namespace events, elements with typed
attributes and CDATA text nodes. Layout mirrors AOSP ResourceTypes.h.
"""
import struct

RES_XML_TYPE = 0x0003
RES_STRING_POOL_TYPE = 0x0001
RES_XML_RESOURCE_MAP_TYPE = 0x0180
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
RES_XML_CDATA_TYPE = 0x0104

UTF8_FLAG = 0x00000100

TYPE_REFERENCE = 0x01
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12

NO_VALUE = 0xFFFFFFFF

ANDROID_NS = "http://schemas.android.com/apk/res/android"

# android.R.attr ids used by the manifest
ATTR_IDS = {
    "theme": 0x01010000,
    "label": 0x01010001,
    "icon": 0x01010002,
    "name": 0x01010003,
    "enabled": 0x0101000E,
    "hasCode": 0x0101000C,
    "exported": 0x01010010,
    "screenOrientation": 0x0101001E,
    "minSdkVersion": 0x0101020C,
    "versionCode": 0x0101021B,
    "versionName": 0x0101021C,
    "targetSdkVersion": 0x01010270,
    "allowBackup": 0x01010280,
}


class Node:
    def __init__(self, tag, ns=None, text=None):
        self.tag = tag
        self.ns = ns  # None or "android"
        self.attrs = []  # (ns, name, value) where value is (kind, data)
        self.children = []
        self.text = text

    def attr(self, name, value, ns="android"):
        self.attrs.append((ns, name, value))
        return self

    def add(self, node):
        self.children.append(node)
        return node


def s(value):
    return ("str", value)


def i(value):
    return ("int", value)


def b(value):
    return ("bool", value)


def ref(value):
    return ("ref", value)


class _Pool:
    def __init__(self):
        self.strings = []
        self.index = {}

    def add(self, value):
        if value not in self.index:
            self.index[value] = len(self.strings)
            self.strings.append(value)
        return self.index[value]


def _enc_len(n):
    if n > 127:
        return bytes(((n >> 8) | 0x80, n & 0xFF))
    return bytes((n,))


def _pool_chunk(pool):
    strings = pool.strings
    offsets = []
    data = bytearray()
    for st in strings:
        raw = st.encode("utf-8")
        offsets.append(len(data))
        data += _enc_len(len(st)) + _enc_len(len(raw)) + raw + b"\x00"
    str_count = len(strings)
    offsets_bytes = struct.pack(f"<{str_count}I", *offsets) if str_count else b""
    header_size = 28
    strings_start = header_size + len(offsets_bytes)
    chunk = bytearray()
    chunk += struct.pack(
        "<HHIIIIII",
        RES_STRING_POOL_TYPE, header_size, 0, str_count, 0, UTF8_FLAG, strings_start, 0,
    )
    chunk += offsets_bytes
    chunk += data
    while len(chunk) % 4:
        chunk += b"\x00"
    struct.pack_into("<I", chunk, 4, len(chunk))
    return bytes(chunk)


def _chunk(ctype, payload):
    size = 8 + len(payload)
    return struct.pack("<HHI", ctype, 8, size) + payload


def _event(etype, *fields):
    return struct.pack(f"<HHIII{'I' * len(fields)}", etype, 16, 16 + 8 + 4 * len(fields), 1, NO_VALUE, *fields)


def _res_value(kind, data, raw):
    if kind == "str":
        dtype = TYPE_STRING
    elif kind == "int":
        dtype = TYPE_INT_DEC
    elif kind == "bool":
        dtype = TYPE_INT_BOOLEAN
        data = 0xFFFFFFFF if data else 0
    elif kind == "ref":
        dtype = TYPE_REFERENCE
    else:
        raise ValueError(kind)
    return struct.pack("<I", raw) + struct.pack("<HBBI", 8, 0, dtype, data & 0xFFFFFFFF)


def write_axml(root, android_ns=True):
    pool = _Pool()

    # 1) attribute-name strings with resource ids come first (map order)
    attr_names = []

    def collect(node):
        for ns, name, _ in node.attrs:
            if ns == "android" and name in ATTR_IDS and name not in attr_names:
                attr_names.append(name)
        for c in node.children:
            collect(c)

    collect(root)
    for n in attr_names:
        pool.add(n)
    n_mapped = len(attr_names)

    # 2) everything else
    pool.add("android")
    pool.add(ANDROID_NS)

    def reg(node):
        pool.add(node.tag)
        for ns, name, val in node.attrs:
            if not (ns == "android" and name in attr_names):
                pool.add(name)
            if val[0] == "str":
                pool.add(val[1])
        if node.text is not None:
            pool.add(node.text)
        for c in node.children:
            reg(c)

    reg(root)

    out = bytearray()
    out += _pool_chunk(pool)

    # resource id map
    ids = [ATTR_IDS[n] for n in attr_names]
    if ids:
        out += _chunk(RES_XML_RESOURCE_MAP_TYPE, struct.pack(f"<{len(ids)}I", *ids))

    if android_ns:
        out += _event(RES_XML_START_NAMESPACE_TYPE, pool.index["android"], pool.index[ANDROID_NS])

    def emit(node):
        nonlocal out
        ns_idx = pool.index["android"] if node.ns == "android" else NO_VALUE
        attrs = node.attrs
        payload = struct.pack("<HHH HHH", 0x14, 0x14, len(attrs), 0, 0, 0)
        ev = bytearray()
        ev += struct.pack("<HHIII", RES_XML_START_ELEMENT_TYPE, 16, 0, 1, NO_VALUE)
        ev += struct.pack("<II", ns_idx, pool.index[node.tag])
        ev += payload
        for ns, name, val in attrs:
            ans = pool.index[ANDROID_NS] if ns == "android" else NO_VALUE
            name_idx = pool.index[name]
            kind, data = val
            if kind == "str":
                raw = data = pool.index[val[1]]
            else:
                raw = NO_VALUE
            ev += struct.pack("<II", ans, name_idx)
            ev += _res_value(kind, data, raw)
        struct.pack_into("<I", ev, 4, len(ev))
        out += ev
        if node.text is not None:
            tidx = pool.index[node.text]
            cd = bytearray(struct.pack("<HHIII", RES_XML_CDATA_TYPE, 16, 0, 1, NO_VALUE))
            cd += struct.pack("<HBBi", 8, 0, TYPE_STRING, tidx)
            struct.pack_into("<I", cd, 4, len(cd))
            out += bytes(cd)
        for c in node.children:
            emit(c)
        ee = struct.pack("<HHIIIII", RES_XML_END_ELEMENT_TYPE, 16, 24, 1, NO_VALUE, ns_idx, pool.index[node.tag])
        out += ee

    emit(root)

    if android_ns:
        out += _event(RES_XML_END_NAMESPACE_TYPE, pool.index["android"], pool.index[ANDROID_NS])

    header = struct.pack("<HHI", RES_XML_TYPE, 8, 8 + len(out))
    return header + bytes(out)
