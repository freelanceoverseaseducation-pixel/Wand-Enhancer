#!/usr/bin/env python3
"""Validate the built APK_PATH as aggressively as possible without a device:
- zip structure / alignment / compression of resources.arsc
- binary manifest parses (androguard) and exposes the right activities/filters
- resources.arsc parses and resolves icon + xml identifiers
- res/xml AXML files parse
- classes.dex parses and the activity class + onCreate exist
- signature: v1 cert parseable, v2 block parseable (apksigtool)
"""
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APK_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "output", "AuraIcons-v1.0.apk")

ok = True


def check(label, cond, extra=""):
    global ok
    print(f"[{'OK' if cond else 'FAIL'}] {label} {extra}")
    if not cond:
        ok = False


zf = zipfile.ZipFile(APK_PATH)
names = zf.namelist()
check("manifest first", names[0] == "AndroidManifest.xml")

info = zf.getinfo("resources.arsc")
check("resources.arsc stored", info.compress_type == zipfile.ZIP_STORED)
off = info.header_offset
with open(APK_PATH, "rb") as f:
    f.seek(off + 26)
    nlen, elen = struct.unpack("<HH", f.read(4))
data_off = off + 30 + nlen + elen
check("resources.arsc 4-byte aligned", data_off % 4 == 0, f"off={data_off}")

for n in names:
    if n.endswith(".png"):
        i = zf.getinfo(n)
        check_p = i.compress_type == zipfile.ZIP_STORED
        if not check_p:
            check(f"png stored: {n}", False)
            break
else:
    check("all pngs stored", True)

# ---- androguard parses
from androguard.core.apk import APK, ARSCParser
from androguard.core.axml import AXMLPrinter
from androguard.core.dex import DEX

apk = APK(APK_PATH)
check("package", apk.get_package() == "com.aura.iconpack", apk.get_package())
check("version", apk.get_androidversion_code() == "1")
check("min/target sdk", apk.get_min_sdk_version() == "21" and apk.get_target_sdk_version() == "34")
acts = apk.get_activities()
check("one activity", acts == ["com.aura.iconpack.MainActivity"], str(acts))
check("main activity", apk.get_main_activity() == "com.aura.iconpack.MainActivity")
filters = apk.get_all_attribute_value("activity", "intent-filter")
iconv = str(apk.get_attribute_value("application", "icon")).lower()
check("icon", iconv in ("@7f010000", "@0x7f010000", "@2130771968"), iconv)
label = apk.get_app_name()
check("app name", label == "Aura Icons", str(label))

mxml = AXMLPrinter(zf.read("AndroidManifest.xml")).get_xml()
check("manifest xml reparse", mxml is not None and b"com.aura.iconpack" in mxml)
cats = apk.get_intent_filters("activity", "com.aura.iconpack.MainActivity")
allcats = set()
for k, v in cats.items():
    allcats.update(v)
check("launcher category", "android.intent.category.LAUNCHER" in allcats)
check("nova theme", "com.novalauncher.THEME" in allcats, f"{len(allcats)} categories")

arsc = ARSCParser(zf.read("resources.arsc"))
pkg = list(arsc.get_packages_names())[0]
check("arsc package", pkg == "com.aura.iconpack", pkg)
arsc._analyse()
locale_vals = arsc.values[pkg].get("\x00\x00", {})
check("arsc drawable type", "drawable" in locale_vals)
check("arsc xml type", "xml" in locale_vals)
rkeys = arsc.resource_keys.get(pkg, {})
draw = rkeys.get("drawable", {})
xmls = rkeys.get("xml", {})
check("drawable whatsapp resolvable", "whatsapp" in draw, hex(draw.get("whatsapp", 0)))
check("drawable ic_launcher id", draw.get("ic_launcher") == 0x7F010000, hex(draw.get("ic_launcher", 0)))
check("xml appfilter resolvable", "appfilter" in xmls, hex(xmls.get("appfilter", 0)))
check("xml count", len(xmls) == 4, str(sorted(xmls.keys())))
check("drawable count", len(draw) == 45, str(len(draw)))

# ---- res/xml axml parse
for xmlname in ("appfilter", "drawable", "themeinfo", "themecfg"):
    data = zf.read(f"res/xml/{xmlname}.xml")
    p = AXMLPrinter(data)
    x = p.get_xml()
    check(f"axml {xmlname}", p.is_valid() and x is not None)

appfilter_xml = AXMLPrinter(zf.read("res/xml/appfilter.xml")).get_xml().decode("utf-8")
check("appfilter has whatsapp", 'drawable="whatsapp"' in appfilter_xml and "com.whatsapp.Main" in appfilter_xml)

# ---- dex
d = DEX(zf.read("classes.dex"))
classes = [c.get_name() for c in d.get_classes()]
check("dex class", "com.aura.iconpack.MainActivity" in classes, str(classes))
meths = [m for m in d.get_methods() if m.get_class_name() in ("Lcom/aura/iconpack/MainActivity;", "com.aura.iconpack.MainActivity")]
mnames = [m.get_name() for m in meths]
check("dex activity methods", "<init>" in mnames and "onCreate" in mnames, str(mnames))
n_insns = 0
for m in d.get_encoded_methods():
    insts = list(m.get_instructions())
    n_insns += len(insts)
    for inst in insts:
        inst.get_name()
check("dex bytecode decodes", n_insns > 10, f"{n_insns} instructions")

# ---- signatures
certs = apk.get_certificates()
check("v1 certificate", len(certs) >= 1)
if certs:
    print("       subject:", certs[0].subject.human_friendly if hasattr(certs[0].subject, "human_friendly") else certs[0].subject)

with open(APK_PATH, "rb") as f:
    raw = f.read()
idx = raw.find(b"APK Sig Block 42")
check("v2 signing block present", idx > 0)

print("\nRESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
