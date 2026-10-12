#!/usr/bin/env python3
"""Assemble the Aura Icons APK: binary manifest, resources.arsc, res/xml
AXML files, classes.dex, icon PNGs -> aligned ZIP -> signed by sign_apk.mjs."""
import io
import json
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import arsc
import axml
import dex

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "generated")
OUT = os.path.join(ROOT, "output")


def build_manifest(pack):
    root = axml.Node("manifest")
    root.attr("package", axml.s(pack["package"]), ns=None)
    root.attr("versionCode", axml.i(pack["version_code"]))
    root.attr("versionName", axml.s(pack["version_name"]))

    sdk = root.add(axml.Node("uses-sdk"))
    sdk.attr("minSdkVersion", axml.i(pack["min_sdk"]))
    sdk.attr("targetSdkVersion", axml.i(pack["target_sdk"]))

    app = root.add(axml.Node("application"))
    app.attr("label", axml.s(pack["pack_name"]))
    app.attr("icon", axml.ref(0x7F010000))  # drawable/ic_launcher (entry 0)
    app.attr("allowBackup", axml.b(False))
    app.attr("hasCode", axml.b(True))

    activity = app.add(axml.Node("activity"))
    activity.attr("name", axml.s(pack["package"] + ".MainActivity"))
    activity.attr("label", axml.s(pack["pack_name"]))
    activity.attr("exported", axml.b(True))

    filters = [
        [("android.intent.action.MAIN",), ["android.intent.category.LAUNCHER"]],
        [("android.intent.action.MAIN",), ["org.adw.launcher.THEMES"]],
        [("android.intent.action.MAIN",), ["com.novalauncher.THEME"]],
        [("android.intent.action.MAIN",), ["com.anddoes.launcher.THEME"]],
        [("android.intent.action.MAIN",), ["com.teslacoilsw.launcher.THEME"]],
        [("android.intent.action.MAIN",), ["com.fede.launcher.THEME"]],
        [("android.intent.action.MAIN",), ["com.gau.go.launcherex.theme"]],
        [("android.intent.action.MAIN",), ["com.sonymobile.home.ICON_PACK"]],
        [("android.intent.action.MAIN",), ["com.huawei.android.launcher.ICON_THEME"]],
        [("org.adw.launcher.icons.ACTION_PICK_ICON",), ["android.intent.category.DEFAULT"]],
    ]
    for actions, cats in filters:
        f = activity.add(axml.Node("intent-filter"))
        for a in actions:
            f.add(axml.Node("action")).attr("name", axml.s(a))
        for c in cats:
            f.add(axml.Node("category")).attr("name", axml.s(c))
    return axml.write_axml(root)


def build_res_xml(pack):
    files = {}

    # appfilter.xml
    root = axml.Node("resources")
    ver = root.add(axml.Node("version"))
    ver.text = "1"
    for icon in pack["icons"]:
        for comp in icon.get("components", []):
            it = root.add(axml.Node("item"))
            it.attr("component", axml.s(comp), ns=None)
            it.attr("drawable", axml.s(icon["drawable"]), ns=None)
    files["appfilter"] = axml.write_axml(root, android_ns=False)

    # drawable.xml
    root = axml.Node("resources")
    ver = root.add(axml.Node("version"))
    ver.text = "1"
    cat = root.add(axml.Node("category"))
    cat.attr("title", axml.s("All"), ns=None)
    for icon in pack["icons"]:
        it = root.add(axml.Node("item"))
        it.attr("drawable", axml.s(icon["drawable"]), ns=None)
    files["drawable"] = axml.write_axml(root, android_ns=False)

    # themeinfo.xml
    root = axml.Node("themeInfo")
    for tag, val, is_int in [
        ("packageName", pack["package"], False),
        ("versionName", pack["version_name"], False),
        ("versionCode", str(pack["version_code"]), False),
        ("themeName", pack["pack_name"], False),
    ]:
        n = root.add(axml.Node(tag))
        n.text = val
    files["themeinfo"] = axml.write_axml(root, android_ns=False)

    # themecfg.xml
    root = axml.Node("theme")
    info = root.add(axml.Node("info"))
    info.text = pack["package"]
    title = root.add(axml.Node("title"))
    title.text = pack["pack_name"]
    files["themecfg"] = axml.write_axml(root, android_ns=False)
    return files


def build_arsc(pack, xml_names):
    global_strings = []
    gset = {}

    def g(path):
        if path not in gset:
            gset[path] = len(global_strings)
            global_strings.append(path)
        return path

    drawable_entries = [("ic_launcher", g("res/drawable-nodpi/ic_launcher.png"))]
    for icon in pack["icons"]:
        drawable_entries.append((icon["drawable"], g(f"res/drawable-nodpi/{icon['drawable']}.png")))
    xml_entries = [(name, g(f"res/xml/{name}.xml")) for name in xml_names]
    return arsc.build(global_strings, pack["package"], [("drawable", drawable_entries), ("xml", xml_entries)])


def assemble(pack):
    os.makedirs(OUT, exist_ok=True)
    manifest = build_manifest(pack)
    xml_files = build_res_xml(pack)
    arsc_bytes = build_arsc(pack, list(xml_files))
    dex_bytes = dex.build([dex.SimpleActivity(pack["package"] + ".MainActivity", "Landroid/app/Activity;", dex.INFO_TEXT)])

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(zipfile.ZipInfo("AndroidManifest.xml"), manifest, zipfile.ZIP_STORED)
        info = zipfile.ZipInfo("resources.arsc")
        z.writestr(info, arsc_bytes, zipfile.ZIP_STORED)
        z.writestr(zipfile.ZipInfo("classes.dex"), dex_bytes, zipfile.ZIP_DEFLATED)
        # launcher icon
        z.writestr(zipfile.ZipInfo("res/drawable-nodpi/ic_launcher.png"),
                   open(os.path.join(GEN, "ic_launcher.png"), "rb").read(), zipfile.ZIP_STORED)
        for icon in pack["icons"]:
            z.writestr(zipfile.ZipInfo(f"res/drawable-nodpi/{icon['drawable']}.png"),
                       open(os.path.join(GEN, "icons", f"{icon['drawable']}.png"), "rb").read(),
                       zipfile.ZIP_STORED)
        for name, data in xml_files.items():
            z.writestr(zipfile.ZipInfo(f"res/xml/{name}.xml"), data, zipfile.ZIP_DEFLATED)
    unsigned = os.path.join(OUT, "aura-unsigned.apk")
    with open(unsigned, "wb") as f:
        f.write(buf.getvalue())
    return unsigned


if __name__ == "__main__":
    pack = json.load(open(os.path.join(ROOT, "pack.json")))
    unsigned = assemble(pack)
    print("unsigned apk:", unsigned, os.path.getsize(unsigned), "bytes")
