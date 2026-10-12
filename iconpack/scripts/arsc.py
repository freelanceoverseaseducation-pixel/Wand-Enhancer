"""Minimal resources.arsc writer.

Builds a resource table with a single package holding N resource types,
each mapping entries to string values (file paths in the APK). Used so that
launchers can resolve the pack's icons and xml via Resources.getIdentifier().
"""
import struct

RES_TABLE_TYPE = 0x0002
RES_STRING_POOL_TYPE = 0x0001
RES_TABLE_PACKAGE_TYPE = 0x0200
RES_TABLE_TYPE_SPEC_TYPE = 0x0202
RES_TABLE_TYPE_TYPE = 0x0201

UTF8_FLAG = 0x00000100
NO_ENTRY = 0xFFFFFFFF
TYPE_STRING = 0x03


def _utf16_pool(strings):
    """UTF-16 string pool (required for package type/key pools)."""
    offsets = []
    data = bytearray()
    for st in strings:
        encoded = st.encode("utf-16-le")
        offsets.append(len(data))
        n = len(st)
        if n > 0x7FFF:
            data += struct.pack("<H", ((n >> 16) | 0x8000))
            data += struct.pack("<H", n & 0xFFFF)
        else:
            data += struct.pack("<H", n)
        data += encoded
        data += b"\x00\x00"
    count = len(strings)
    off_bytes = struct.pack(f"<{count}I", *offsets) if count else b""
    header_size = 28
    strings_start = header_size + len(off_bytes)
    chunk = struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, header_size, 0, count, 0, 0, strings_start, 0)
    chunk += off_bytes + bytes(data)
    chunk = bytearray(chunk)
    while len(chunk) % 4:
        chunk += b"\x00"
    struct.pack_into("<I", chunk, 4, len(chunk))
    return bytes(chunk)


def _utf8_pool(strings):
    """UTF-8 global value string pool."""
    def enc_len(n):
        return bytes(((n >> 8) | 0x80, n & 0xFF)) if n > 127 else bytes((n,))

    offsets = []
    data = bytearray()
    for st in strings:
        raw = st.encode("utf-8")
        offsets.append(len(data))
        data += enc_len(len(st)) + enc_len(len(raw)) + raw + b"\x00"
    count = len(strings)
    off_bytes = struct.pack(f"<{count}I", *offsets) if count else b""
    header_size = 28
    strings_start = header_size + len(off_bytes)
    chunk = bytearray(struct.pack("<HHIIIIII", RES_STRING_POOL_TYPE, header_size, 0, count, 0, UTF8_FLAG, strings_start, 0))
    chunk += off_bytes + data
    while len(chunk) % 4:
        chunk += b"\x00"
    struct.pack_into("<I", chunk, 4, len(chunk))
    return bytes(chunk)


def build(global_strings, package_name, types):
    """types: list of (type_name, [(entry_name, value_string_or_None), ...])"""
    global_pool = _utf8_pool(global_strings)
    gidx = {v: k for k, v in enumerate(global_strings)}

    type_names = [t[0] for t in types]
    key_pool_strings = []
    for _, entries in types:
        for name, _ in entries:
            if name not in key_pool_strings:
                key_pool_strings.append(name)
    type_pool = _utf16_pool(type_names)
    key_pool = _utf16_pool(key_pool_strings)
    kidx = {v: k for k, v in enumerate(key_pool_strings)}

    pkg_id = 0x7F
    # package header is 0x120 bytes
    pkg_header = bytearray(0x120)
    type_chunks = bytearray()
    CFG_SIZE = 36
    TYPE_HEADER = 8 + 8 + 4 + CFG_SIZE  # chunk hdr + id/flags/counts + entriesStart + config

    for type_i, (type_name, entries) in enumerate(types):
        type_id = type_i + 1
        entry_count = len(entries)
        # type spec chunk (chunk header 8 bytes + id/res0/res1/entryCount 8 bytes)
        spec = bytearray(struct.pack("<HHI", RES_TABLE_TYPE_SPEC_TYPE, 16, 16 + 4 * entry_count))
        spec += struct.pack("<BBHI", type_id, 0, 0, entry_count)
        spec += struct.pack(f"<{entry_count}I", *([0] * entry_count))
        type_chunks += spec

        # entries data
        offsets = []
        entry_data = bytearray()
        for name, value in entries:
            offsets.append(len(entry_data))
            entry_data += struct.pack("<HHI", 8, 0, kidx[name])
            if value is None:
                entry_data += struct.pack("<HBBi", 8, 0, 0, -1)
            else:
                entry_data += struct.pack("<HBBi", 8, 0, TYPE_STRING, gidx[value])
        entries_start = TYPE_HEADER + 4 * entry_count
        tc = bytearray(struct.pack("<HHI", RES_TABLE_TYPE_TYPE, TYPE_HEADER, 0))
        tc += struct.pack("<BBHI", type_id, 0, 0, entry_count)
        tc += struct.pack("<I", entries_start)
        cfg = bytearray(CFG_SIZE)
        struct.pack_into("<I", cfg, 0, CFG_SIZE)
        tc += cfg
        tc += struct.pack(f"<{entry_count}I", *offsets)
        tc += entry_data
        struct.pack_into("<I", tc, 4, len(tc))
        type_chunks += bytes(tc)

    struct.pack_into("<HHI", pkg_header, 0, RES_TABLE_PACKAGE_TYPE, 0x120, 0)
    struct.pack_into("<I", pkg_header, 8, pkg_id)
    name_u16 = package_name.encode("utf-16-le")
    pkg_header[12:12 + len(name_u16)] = name_u16
    # global value pool lives in the table chunk; package holds type/key pools
    type_off = 0x120
    key_off = type_off + len(type_pool)
    # layout: id@8, name@12..268, typeStrings@268(0x10C), lastPublicType@272, keyStrings@276(0x114), lastPublicKey@280
    struct.pack_into("<I", pkg_header, 0x10C, type_off)
    struct.pack_into("<I", pkg_header, 0x110, len(type_names))
    struct.pack_into("<I", pkg_header, 0x114, key_off)
    struct.pack_into("<I", pkg_header, 0x118, len(key_pool_strings))
    pkg_size = 0x120 + len(type_pool) + len(key_pool) + len(type_chunks)
    struct.pack_into("<I", pkg_header, 4, pkg_size)

    table = bytearray(struct.pack("<HHII", RES_TABLE_TYPE, 12, 0, 1))
    table += global_pool
    table += pkg_header
    table += type_pool
    table += key_pool
    table += type_chunks
    struct.pack_into("<I", table, 4, len(table))
    return bytes(table)
