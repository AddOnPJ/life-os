#!/usr/bin/env python3
"""dashboard/template.html に status/dashboard.json を埋め込み、dashboard/index.html を作る（公開用）。"""
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
t = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
d = (ROOT / "status" / "dashboard.json").read_text(encoding="utf-8").replace("</", "<\\/")
(ROOT / "dashboard" / "index.html").write_text(t.replace("__SNAPSHOT__", d), encoding="utf-8")
print("dashboard/index.html")
