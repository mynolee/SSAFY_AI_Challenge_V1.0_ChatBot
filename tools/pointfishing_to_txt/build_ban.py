# -*- coding: utf-8 -*-
"""지자체별 낚시금지·제한·통제구역 CSV/XLSX -> TXT"""
from build_txt import *

# (파일명, 시도, 시군구, 명칭컬럼, 구분(고정값 또는 '@컬럼명'), 제목보조컬럼)
SPECS = [
    ("강원특별자치도 강릉시_낚시금지 제한 통제구역 현황_20260720.csv",
     "강원특별자치도", "강릉시", "명칭", "@구분", None),
    ("강원특별자치도 춘천시_낚시금제 제한 통제구역 현황_20260722.csv",
     "강원특별자치도", "춘천시", "명칭", "낚시금지구역(상수원보호구역)", None),
    ("경상남도 거창군_낚시금지구역낚시통제구역낚시제한구역현황_20260715.csv",
     "경상남도", "거창군", "하천명또는수계명", "낚시금지·제한구역", None),
    ("경상남도 고성군_낚시통제및금지구역_20260720.csv",
     "경상남도", "고성군", "명칭", "@구분", None),
    ("경상남도 김해시_낚시금지구역지정현황_20260724.csv",
     "경상남도", "김해시", "명칭", "@구분", None),
    ("경상남도 창녕군_낚시_금지구역_현황_20260722.csv",
     "@시도", "@시군구", "지정구역 명칭", "낚시금지구역", None),
    ("경상남도 합천군_낚시금지제한통제 구역현황_20260715.csv",
     "@시도명", "@시군구명", "대상지명", "@구역구분", None),
    ("경상북도 고령군_낚시금지제한통제구역현황_20260716.csv",
     "@시도명", "@시군구명", "명칭", "@제한유형", None),
    ("경상북도 김천시_낚시금지구역 지정현황_20260713.csv",
     "경상북도", "김천시", "명칭(호소명)", "낚시금지구역", None),
    ("경상북도 영양군_낚시금지구역현황_20260720.csv",
     "경상북도", "영양군", "하천명", "@구분", None),
    ("경상북도 의성군_낚시금지구역_20260710.csv",
     "경상북도", "의성군", "하천명", "낚시금지구역(하천)", None),
    ("경상북도 청송군_낚시 금지제한통제구역 현황_20260714.csv",
     "@시도명", "@시군명", "명칭", "낚시금지구역", None),
    ("부산광역시 수영구_낚시통제구역지정현황_20260813.csv",
     "부산광역시", "수영구", "지정범위(지역)", "@구분", None),
    ("인천광역시_낚시금지 및 제한구역 현황_20240826.csv",
     "인천광역시", "", "하천명", "낚시금지·제한구역", "지정구간"),
    ("전남광주통합특별시 광양시_낚시금지구역_20260820.csv",
     "전남광주통합특별시", "광양시", "낚시금지구역명", "낚시금지구역", None),
    ("전남광주통합특별시 보성군_낚시금지제한구역_20260819.csv",
     "전남광주통합특별시", "보성군", "저수지명", "낚시금지·제한구역", None),
    ("전남광주통합특별시 순천시_낚시금지_20260828.csv",
     "전남광주통합특별시", "순천시", "명칭", "낚시금지구역", None),
    ("전남광주통합특별시 화순군_낚시금지구역_20260821.csv",
     "전남광주통합특별시", "화순군", "명칭", "낚시금지구역", None),
    ("전북특별자치도 김제시_낚시금지 및 제한구역 현황_20260827.csv",
     "전북특별자치도", "김제시", "낚시금지구역 명칭", "낚시금지구역", None),
    ("전북특별자치도 무주군_낚시금지구역_20260820.csv",
     "전북특별자치도", "무주군", "수면 명칭", "@금지구역명", None),
    ("전북특별자치도 장수군_낚시금지및통제구역_20260827.csv",
     "전북특별자치도", "장수군", "수면 명칭", "@구분", None),
    ("전북특별자치도 정읍시_낚시금지구역_20260821.csv",
     "전북특별자치도", "정읍시", "낚시금지구역 명칭", "낚시금지구역", None),
    ("충청남도 공주시_낚시금지구역지정현황_20260723.csv",
     "충청남도", "공주시", "명칭", "@구분", None),
    ("충청남도 논산시_낚시금지구역_20260720.csv",
     "@시도", "@시군구", "명칭", "@지정상태", None),
    ("충청남도 아산시_낚시금지구역_20260728.csv",
     "충청남도", "아산시", "명칭", "@구분", None),
    ("충청북도 증평군_낚시금지구역 현황_20260710.csv",
     "@시도", "@시군구", "명칭", "낚시금지구역", None),
]

DATE_RE = re.compile(r"일자|일$|기간시작|기간종료|기준일|지정일|해제일|시작일|종료일")


def resolve(spec_val, rec):
    if spec_val and spec_val.startswith("@"):
        return clean(rec.get(spec_val[1:], ""))
    return spec_val or ""


def build():
    blocks, total = [], 0
    for fname, sido_s, sgg_s, name_key, kind_s, sub_key in SPECS:
        header, rows = read_csv(fname)
        origin = fname.rsplit("_", 1)[0] if re.search(r"_\d{8}\.csv$", fname) else fname[:-4]
        for rec in rows:
            sido = resolve(sido_s, rec)
            sgg = resolve(sgg_s, rec)
            kind = resolve(kind_s, rec) or "낚시금지구역"
            if "낚시" not in kind and "구역" not in kind:
                kind = "낚시금지구역(%s)" % kind
            name = clean(rec.get(name_key, "")) or "명칭미상"
            if sub_key and clean(rec.get(sub_key, "")):
                name = "%s (%s)" % (name, clean(rec[sub_key]))
            region = " ".join(x for x in (sido, sgg) if x)
            b = Block("[%s] %s %s" % (kind, region, name))
            b.raw("행정구역: %s" % region)
            used = {name_key, sub_key}
            for k in header:
                if k in used or not clean(rec.get(k, "")):
                    continue
                v = clean(rec[k])
                if v in (sido, sgg) and k != "지정범위":
                    continue
                if DATE_RE.search(k):
                    v = fmt_date(v)
                b.raw("%s: %s" % (k, v))
            b.raw("자료출처: %s (공공데이터포털 지자체 제공)" % origin)
            blocks.append(b)
            total += 1

    # 익산시 (xlsx)
    sheets = read_xlsx(SRC / "전북특별자치도 익산시_낚시금지구역_20260831.xlsx")
    main = sheets["익산시 낚시금지구역"]
    hdr = main[0]
    parcel = {}
    for nm, rows in sheets.items():
        if not nm.endswith("위치정보"):
            continue
        area = sum(int(r[4]) for r in rows[1:] if len(r) > 4 and r[4].isdigit())
        parcel[nm.replace(" 위치정보", "")] = (len(rows) - 1, area)
    for r in main[1:]:
        rec = dict(zip(hdr, r + [""] * (len(hdr) - len(r))))
        nm = rec["낚시금지구역(낚시제한구역)"]
        b = Block("[낚시금지구역] 전북특별자치도 익산시 %s" % nm)
        b.raw("행정구역: 전북특별자치도 익산시")
        for k in hdr:
            v = clean(rec.get(k, ""))
            if not v or k == "낚시금지구역(낚시제한구역)":
                continue
            if k in ("낚시금지 지정일자", "자료기준일") and v.isdigit():
                v = xl_date(v)
            b.raw("%s: %s" % (k, v))
        if nm in parcel:
            n, a = parcel[nm]
            b.raw("지정 필지: %d필지, 합계 면적 약 %s㎡" % (n, format(a, ",")))
        b.raw("자료출처: 전북특별자치도 익산시_낚시금지구역 (2026-08-31 기준)")
        blocks.append(b)
        total += 1

    hd = head("전국 지방자치단체 낚시금지구역·낚시제한구역·낚시통제구역 현황",
              "지역별 낚시 규제(금지/제한/통제) 구역 목록",
              "공공데이터포털 - 각 시·도 및 시·군·구 제공 낚시금지구역 현황 (27개 기관)",
              total,
              "행정구역, 구역명칭, 구분(금지/제한/통제), 근거법령, 지정일자, 지정범위·주소, 지정사유, 금지행위, 담당부서")
    write_txt("01_낚시금지구역_전국_지자체.txt", hd, blocks)


if __name__ == "__main__":
    build()
