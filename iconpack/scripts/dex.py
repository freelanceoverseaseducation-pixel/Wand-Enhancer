"""Minimal DEX file writer.

Emits a classes.dex containing a single Activity subclass that shows a
short instructions screen (ScrollView + TextView) so opening the pack from
the app drawer gives useful guidance instead of a crash.
"""
import hashlib
import struct
import zlib

T_ACTIVITY = "Landroid/app/Activity;"
T_CONTEXT = "Landroid/content/Context;"
T_BUNDLE = "Landroid/os/Bundle;"
T_VIEW = "Landroid/view/View;"
T_SCROLL = "Landroid/widget/ScrollView;"
T_TEXT = "Landroid/widget/TextView;"
T_CHSEQ = "Ljava/lang/CharSequence;"

INFO_TEXT = (
    "Aura Icons is installed!\n\n"
    "To apply the pack:\n"
    "1. Install a launcher with icon-pack support (e.g. Nova Launcher or Lawnchair from the Play Store).\n"
    "2. Open the launcher settings.\n"
    "3. Go to Icon style / Icon theme and pick 'Aura Icons'.\n\n"
    "Note: the stock Honor launcher cannot use third-party icon packs."
)

ACC_PUBLIC = 0x1
ACC_CONSTRUCTOR = 0x10000


class _Dex:
    def __init__(self):
        self.strings = []
        self.sidx = {}
        self.types = []
        self.tidx = {}
        self.protos = []
        self.pidx = {}
        self.methods = []
        self.midx = {}

    def S(self, v):
        if v not in self.sidx:
            self.sidx[v] = len(self.strings)
            self.strings.append(v)
        return self.sidx[v]

    def T(self, v):
        self.S(v)
        if v not in self.tidx:
            self.tidx[v] = len(self.types)
            self.types.append(v)
        return self.tidx[v]

    def P(self, ret, params):
        key = (ret, tuple(params))
        if key not in self.pidx:
            self.S(ret)
            for p in params:
                self.S(p)
            self.S(_shorty(ret, params))
            self.pidx[key] = len(self.protos)
            self.protos.append(key)
        return self.pidx[key]

    def M(self, cls, name, ret, params):
        key = (cls, name, (ret, tuple(params)))
        if key not in self.midx:
            self.midx[key] = len(self.methods)
            self.methods.append(key)
        return self.midx[key]


def _uleb(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _shorty(ret, params):
    def ch(t):
        return t if t in "VIFDSBCZ" else "L"

    return "".join([ch(ret)] + [ch(t) for t in params])


class SimpleActivity:
    def __init__(self, class_name, superclass, text):
        self.class_name = class_name
        self.superclass = superclass
        self.text = text
        self.access = ACC_PUBLIC
        self.source = "MainActivity.java"

    def register(self, d):
        for t in (self.class_name, self.superclass, T_BUNDLE, T_SCROLL, T_TEXT, T_CONTEXT, T_VIEW, T_CHSEQ):
            d.T(t)
        for t in ("V", "I", "F"):
            d.T(t)
        d.S(self.source)
        for s in ("<init>", "onCreate", "setBackgroundColor", "setText", "setTextSize",
                  "setTextColor", "setPadding", "addView", "setContentView"):
            d.S(s)
        d.S(self.text)
        d.M(self.superclass, "<init>", "V", ())
        d.M(self.superclass, "onCreate", "V", (T_BUNDLE,))
        d.M(self.superclass, "setContentView", "V", (T_VIEW,))
        d.M(T_SCROLL, "<init>", "V", (T_CONTEXT,))
        d.M(T_SCROLL, "setBackgroundColor", "V", ("I",))
        d.M(T_SCROLL, "addView", "V", (T_VIEW,))
        d.M(T_TEXT, "<init>", "V", (T_CONTEXT,))
        d.M(T_TEXT, "setText", "V", (T_CHSEQ,))
        d.M(T_TEXT, "setTextSize", "V", ("F",))
        d.M(T_TEXT, "setTextColor", "V", ("I",))
        d.M(T_TEXT, "setPadding", "V", ("I", "I", "I", "I"))
        d.P("V", ())
        d.P("V", (T_BUNDLE,))
        d.P("V", (T_CONTEXT,))
        d.P("V", (T_VIEW,))
        d.P("V", (T_CHSEQ,))
        d.P("V", ("I",))
        d.P("V", ("F",))
        d.P("V", ("I", "I", "I", "I"))

    def emit(self, d, code_blobs):
        """Returns a descriptor; code blobs are appended to code_blobs."""
        m_init = d.M(self.superclass, "<init>", "V", ())
        m_oncreate = d.M(self.superclass, "onCreate", "V", (T_BUNDLE,))
        m_scroll_init = d.M(T_SCROLL, "<init>", "V", (T_CONTEXT,))
        m_scroll_bg = d.M(T_SCROLL, "setBackgroundColor", "V", ("I",))
        m_text_init = d.M(T_TEXT, "<init>", "V", (T_CONTEXT,))
        m_settext = d.M(T_TEXT, "setText", "V", (T_CHSEQ,))
        m_setsize = d.M(T_TEXT, "setTextSize", "V", ("F",))
        m_setcolor = d.M(T_TEXT, "setTextColor", "V", ("I",))
        m_setpad = d.M(T_TEXT, "setPadding", "V", ("I", "I", "I", "I"))
        m_addview = d.M(T_SCROLL, "addView", "V", (T_VIEW,))
        m_setcontent = d.M(self.superclass, "setContentView", "V", (T_VIEW,))

        # ---- <init>()V : super(); return
        ii = bytearray()
        ii += struct.pack("<HHH", (1 << 12) | 0x70, m_init, 0)
        ii += struct.pack("<H", 0x000E)
        init_blob = self._code_item(1, 1, 1, ii)

        # ---- onCreate(Bundle)V
        ins = bytearray()
        # invoke-super {p0,p1}, Activity.onCreate  (p0=v7, p1=v8)
        ins += struct.pack("<HHH", (2 << 12) | (8 << 8) | 0x6F, m_oncreate, 7 | (8 << 4))
        # v0 = new ScrollView(this)
        ins += struct.pack("<HH", 0x22 | (0 << 8), d.tidx[T_SCROLL])
        ins += struct.pack("<HHH", (2 << 12) | (7 << 8) | 0x70, m_scroll_init, 0 | (7 << 4))
        # v0.setBackgroundColor(0xFF0F1626)
        ins += struct.pack("<HHH", 0x14 | (1 << 8), 0x1626, 0xFF0F)
        ins += struct.pack("<HHH", (2 << 12) | (1 << 8) | 0x6E, m_scroll_bg, 0 | (1 << 4))
        # v1 = new TextView(this)
        ins += struct.pack("<HH", 0x22 | (1 << 8), d.tidx[T_TEXT])
        ins += struct.pack("<HHH", (2 << 12) | (7 << 8) | 0x70, m_text_init, 1 | (7 << 4))
        # v1.setText(INFO_TEXT)
        ins += struct.pack("<HH", 0x1A | (2 << 8), d.sidx[self.text])
        ins += struct.pack("<HHH", (2 << 12) | (2 << 8) | 0x6E, m_settext, 1 | (2 << 4))
        # v1.setTextSize(18.0f)
        ins += struct.pack("<HHH", 0x14 | (3 << 8), 0x0000, 0x4190)
        ins += struct.pack("<HHH", (2 << 12) | (3 << 8) | 0x6E, m_setsize, 1 | (3 << 4))
        # v1.setTextColor(0xFFE7ECF6)
        ins += struct.pack("<HHH", 0x14 | (3 << 8), 0xECF6, 0xFFE7)
        ins += struct.pack("<HHH", (2 << 12) | (3 << 8) | 0x6E, m_setcolor, 1 | (3 << 4))
        # v1.setPadding(56,48,56,48)
        for reg, val in ((3, 56), (4, 48), (5, 56), (6, 48)):
            ins += struct.pack("<HH", 0x13 | (reg << 8), val)
        ins += struct.pack("<HHH", (5 << 12) | (6 << 8) | 0x6E, m_setpad,
                           1 | (3 << 4) | (4 << 8) | (5 << 12))
        # v0.addView(v1)
        ins += struct.pack("<HHH", (2 << 12) | (1 << 8) | 0x6E, m_addview, 0 | (1 << 4))
        # setContentView(v0)
        ins += struct.pack("<HHH", (2 << 12) | (0 << 8) | 0x6E, m_setcontent, 7 | (0 << 4))
        ins += struct.pack("<H", 0x000E)
        oncreate_blob = self._code_item(9, 2, 5, ins)

        n0 = len(code_blobs)
        code_blobs.append(init_blob)
        code_blobs.append(oncreate_blob)
        return {
            "my_init": d.M(self.class_name, "<init>", "V", ()),
            "my_oncreate": d.M(self.class_name, "onCreate", "V", (T_BUNDLE,)),
            "blobs": (n0, n0 + 1),
        }

    @staticmethod
    def _code_item(regs, ins, outs, insns):
        # u2 registers, u2 ins, u2 outs, u2 tries, u32 debug_off, u32 insns_size
        return struct.pack("<HHHHII", regs, ins, outs, 0, 0, len(insns) // 2) + bytes(insns)


def build(classes):
    d = _Dex()
    for c in classes:
        c.register(d)

    # ---- sort tables per dex spec
    d.strings.sort()
    d.sidx = {v: k for k, v in enumerate(d.strings)}
    d.types.sort(key=lambda t: d.sidx[t])
    d.tidx = {v: k for k, v in enumerate(d.types)}
    d.protos.sort(key=lambda p: (d.sidx[p[0]], [d.sidx[t] for t in p[1]]))
    d.pidx = {v: k for k, v in enumerate(d.protos)}
    d.methods.sort(key=lambda m: (d.tidx[m[0]], d.sidx[m[1]], d.pidx[(m[2][0], tuple(m[2][1]))]))
    d.midx = {v: k for k, v in enumerate(d.methods)}

    code_blobs = []
    descs = [c.emit(d, code_blobs) for c in classes]

    # ---- section layout
    header_size = 0x70
    n_str, n_type, n_proto, n_meth, n_class = len(d.strings), len(d.types), len(d.protos), len(d.methods), len(classes)
    str_ids_off = header_size
    type_ids_off = str_ids_off + 4 * n_str
    proto_ids_off = type_ids_off + 4 * n_type
    method_ids_off = proto_ids_off + 12 * n_proto
    class_defs_off = method_ids_off + 8 * n_meth
    data_off = class_defs_off + 32 * n_class

    data = bytearray()

    def align4():
        while (data_off + len(data)) % 4:
            data.append(0)

    align4()
    code_offs = []
    for blob in code_blobs:
        align4()
        code_offs.append(data_off + len(data))
        data += blob

    tl_offs = {}
    proto_tl = []
    for (ret, params) in d.protos:
        if params:
            key = tuple(params)
            if key not in tl_offs:
                align4()
                tl_offs[key] = data_off + len(data)
                data += struct.pack("<I", len(params))
                for t in params:
                    data += struct.pack("<H", d.tidx[t])
            proto_tl.append(tl_offs[key])
        else:
            proto_tl.append(0)

    str_offs = []
    for s in d.strings:
        str_offs.append(data_off + len(data))
        data += _uleb(len(s)) + s.encode("utf-8") + b"\x00"

    cd_offs = []
    for c, desc in zip(classes, descs):
        cd = bytearray()
        cd += _uleb(0) + _uleb(0)  # no fields
        cd += _uleb(1) + _uleb(1)  # direct + virtual method counts
        cd += _uleb(desc["my_init"])  # direct: <init>
        cd += _uleb(ACC_PUBLIC | ACC_CONSTRUCTOR)
        cd += _uleb(code_offs[desc["blobs"][0]])
        cd += _uleb(desc["my_oncreate"])  # virtual: onCreate
        cd += _uleb(ACC_PUBLIC)
        cd += _uleb(code_offs[desc["blobs"][1]])
        cd_offs.append(data_off + len(data))
        data += cd

    align4()
    map_off = data_off + len(data)
    sections = [(0x0000, 0, 1),
                (0x0001, str_ids_off, n_str),
                (0x0002, type_ids_off, n_type),
                (0x0003, proto_ids_off, n_proto),
                (0x0005, method_ids_off, n_meth),
                (0x0006, class_defs_off, n_class)]
    if code_offs:
        sections.append((0x2001, code_offs[0], len(code_offs)))
    if tl_offs:
        sections.append((0x1001, min(tl_offs.values()), len(tl_offs)))
    sections.append((0x2002, str_offs[0], n_str))
    sections.append((0x2000, cd_offs[0], len(cd_offs)))  # TYPE_CLASS_DATA_ITEM
    sections.append((0x1000, map_off, 1))
    sections.sort(key=lambda s: s[1])
    data += struct.pack("<I", len(sections))
    for t, off, sz in sections:
        data += struct.pack("<HHII", t, 0, sz, off)

    file_size = data_off + len(data)

    out = bytearray()
    out += b"dex\n035\x00"
    out += struct.pack("<I", 0)
    out += b"\x00" * 20
    out += struct.pack("<IIIIII", file_size, header_size, 0x12345678, 0, 0, map_off)
    out += struct.pack("<II", n_str, str_ids_off)
    out += struct.pack("<II", n_type, type_ids_off)
    out += struct.pack("<II", n_proto, proto_ids_off)
    out += struct.pack("<II", 0, 0)
    out += struct.pack("<II", n_meth, method_ids_off)
    out += struct.pack("<II", n_class, class_defs_off)
    out += struct.pack("<II", len(data), data_off)

    for _ in d.strings:
        out += struct.pack("<I", 0)
    for t in d.types:
        out += struct.pack("<I", d.sidx[t])
    for (ret, params), tl in zip(d.protos, proto_tl):
        out += struct.pack("<III", d.sidx[_shorty(ret, params)], d.tidx[ret], tl)
    for (cls, name, proto) in d.methods:
        out += struct.pack("<HHI", d.tidx[cls], d.pidx[proto], d.sidx[name])
    for c, cd_off in zip(classes, cd_offs):
        out += struct.pack("<IIIIIIII", d.tidx[c.class_name], c.access, d.tidx[c.superclass],
                           0, d.sidx[c.source], 0, cd_off, 0)
    out += data

    for i, off in enumerate(str_offs):
        struct.pack_into("<I", out, str_ids_off + 4 * i, off)

    out[12:32] = hashlib.sha1(bytes(out[32:])).digest()
    struct.pack_into("<I", out, 8, zlib.adler32(bytes(out[12:])) & 0xFFFFFFFF)
    return bytes(out)
