# -*- coding: utf-8 -*-
"""pointFishingDB의 모든 원본 데이터(CSV/XLSX/SHP+DBF)를 RAG 적재용 TXT로 변환한다."""
import csv
import datetime as dt
import io
import os
import re
import struct
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tmk import utmk_to_wgs84

SRC = Path(r"C:/ssafy/EnjoyTrip_ChatBot/pointFishingDB")
OUT = Path(r"C:/ssafy/EnjoyTrip_ChatBot/pointFishingDB_txt")
OUT.mkdir(parents=True, exist_ok=True)

NULLS = {"", "-", "해당없음", "없음.", "N/A", "n/a", "null", "NULL", "미상"}
BOM_JUNK = re.compile(r"^[\uFEFF\u7645\u758B\uC6A9\uC6B0]*\ufeff")


def clean(v):
    if v is None:
        return ""
    v = str(v).replace("\r\n", " ").replace("\n", " ").replace("\ufeff", "")
    v = re.sub(r"\s+", " ", v).strip().strip('"').strip()
    return "" if v in NULLS else v


def clean_header(h):
    """cp949로 저장된 UTF-8 BOM 잔재(예: '癤용굾﻿낚시금지구역명')를 헤더 앞에서 제거."""
    if "﻿" in h:
        h = h[h.rindex("﻿") + 1:]
    return h.replace("﻿", "").strip()


def read_csv(name):
    raw = (SRC / name).read_bytes()
    text = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    header = [clean_header(h) for h in rows[0]]
    out = []
    for r in rows[1:]:
        r = list(r) + [""] * (len(header) - len(r))
        rec = {h: clean(v) for h, v in zip(header, r)}
        if any(rec.values()):
            out.append(rec)
    return header, out


def read_xlsx(path):
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
            ss.append("".join(t.text or "" for t in si.iter(ns + "t")))
    names = [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).iter(ns + "sheet")]
    sheets = {}
    for i, nm in enumerate(names, 1):
        fn = "xl/worksheets/sheet%d.xml" % i
        if fn not in z.namelist():
            continue
        rows = []
        for row in ET.fromstring(z.read(fn)).iter(ns + "row"):
            cells = []
            for c in row.iter(ns + "c"):
                v, t = c.find(ns + "v"), c.get("t")
                if v is None:
                    isn = c.find(ns + "is")
                    val = "".join(x.text or "" for x in isn.iter(ns + "t")) if isn is not None else ""
                else:
                    val = ss[int(v.text)] if t == "s" else (v.text or "")
                cells.append(clean(val))
            if any(cells):
                rows.append(cells)
        sheets[nm] = rows
    return sheets


def xl_date(serial):
    try:
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(serial))).isoformat()
    except Exception:
        return str(serial)


def fmt_date(v):
    v = clean(v)
    if re.fullmatch(r"\d{8}", v):
        return "%s-%s-%s" % (v[:4], v[4:6], v[6:])
    if v.startswith("9999"):
        return "제한 없음 (별도 해제 시까지 계속 적용)"
    if v in ("계속", "상시", "연중"):
        return "%s (별도 해제 시까지 계속 적용)" % v
    return v


def dms_to_dec(s):
    m = re.match(r"\s*(\d+)[-\u00b0]\s*(\d+)['\u2019\s-]\s*([\d.]+)[\"\u201d]?\s*([NSEW])?", clean(s))
    if not m:
        return None
    d, mi, se, hemi = m.groups()
    se = se.strip(".") or "0"
    try:
        sec = float(se)
    except ValueError:
        sec = float(se.split(".")[0] + "." + se.split(".")[1])
    val = int(d) + int(mi) / 60 + sec / 3600
    return -val if hemi in ("S", "W") else val


def point_wgs(wkt):
    m = re.match(r"POINT\s*\(([\d.\-]+)\s+([\d.\-]+)\)", clean(wkt))
    if not m:
        return None, None
    return utmk_to_wgs84(float(m.group(1)), float(m.group(2)))


# ---------------------------------------------------------------- 블록 조립
class Block:
    """RAG 청크 1개에 대응하는 레코드 블록."""

    def __init__(self, title):
        self.title = title
        self.lines = []

    def add(self, label, value, transform=None):
        v = clean(value)
        if not v:
            return self
        if transform:
            v = transform(v)
        if v:
            self.lines.append("%s: %s" % (label, v))
        return self

    def raw(self, line):
        if line:
            self.lines.append(line)
        return self

    def render(self):
        return "\n".join([self.title] + self.lines)


def write_txt(fname, header_lines, blocks):
    body = "\n\n".join(b.render() if isinstance(b, Block) else b for b in blocks)
    text = "\n".join(header_lines) + "\n\n" + body + "\n"
    (OUT / fname).write_text(text, encoding="utf-8")
    lens = [len(b.render() if isinstance(b, Block) else b) for b in blocks]
    print("%-46s blocks=%4d  max=%4d  avg=%4d  bytes=%d"
          % (fname, len(blocks), max(lens) if lens else 0,
             sum(lens) // len(lens) if lens else 0, len(text.encode("utf-8"))))
    return len(blocks)


def head(title, desc, source, count, fields):
    return [
        "# %s" % title,
        "# 문서유형: %s" % desc,
        "# 원본출처: %s" % source,
        "# 수록건수: %d건" % count,
        "# 주요항목: %s" % fields,
        "# ※ 아래 각 단락(빈 줄로 구분)은 독립된 1건의 정보이며, 단락 안에 지역·명칭·규제내용이 모두 포함되어 있다.",
        "# " + "-" * 70,
    ]
