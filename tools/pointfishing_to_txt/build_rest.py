# -*- coding: utf-8 -*-
"""낚시터·낚시포인트·어획·조사정점·해상금지구역 -> TXT"""
from build_txt import *

SIDO_FIX = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도"}


def region_of(addr):
    """주소 문자열에서 '시도 시군구' 형태의 행정구역을 뽑아낸다."""
    a = clean(addr)
    for s in ("서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
              "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "강원도", "충청북도",
              "충청남도", "전북특별자치도", "전라북도", "전라남도", "전남광주통합특별시",
              "경상북도", "경상남도", "제주특별자치도"):
        if a.startswith(s):
            rest = a[len(s):].strip().split(" ")
            sgg = rest[0] if rest and rest[0].endswith(("시", "군", "구")) else ""
            return " ".join(x for x in (SIDO_FIX.get(s, s), sgg) if x)
    return ""


def sido_of(addr):
    a = clean(addr)
    for s in ("서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
              "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "강원도", "충청북도",
              "충청남도", "전북특별자치도", "전라북도", "전라남도", "전남광주통합특별시",
              "경상북도", "경상남도", "제주특별자치도"):
        if a.startswith(s):
            return SIDO_FIX.get(s, s)
    return ""


# ---------------------------------------------------------------- 02 경기도 금지구역
def gyeonggi_ban():
    header, rows = read_csv("경기도낚시금지및제한구역지정현황.csv")
    blocks = []
    for r in rows:
        gu = clean(r["구분"])
        b = Block("[낚시%s] 경기도 %s %s" % (gu, clean(r["시군명"]), clean(r["명칭"])))
        b.raw("행정구역: 경기도 %s" % clean(r["시군명"]))
        b.raw("구역구분: 낚시%s" % gu)
        b.add("지정일자", fmt_date(r["지정일자"]))
        b.add("지정권자", r["지정권자"])
        b.raw("적용기간: %s ~ %s" % (fmt_date(r["지정시작일자"]), fmt_date(r["지정종료일자"])))
        b.add("지정사유", r["지정사유"],
              lambda v: "%s 용수 수질보전" % v if v in ("농업용", "생활용", "공업용") else v)
        b.raw("자료출처: 경기도 낚시금지 및 제한구역 지정 현황 (경기도 제공)")
        blocks.append(b)
    hd = head("경기도 낚시금지구역·낚시제한구역 지정 현황",
              "경기도 시·군별 낚시 금지/제한 저수지·하천 목록",
              "공공데이터포털 - 경기도 낚시금지 및 제한구역 지정현황",
              len(blocks),
              "구역구분(금지/제한), 시군명, 저수지·하천 명칭, 지정일자, 지정권자, 적용기간, 지정사유")
    write_txt("02_낚시금지구역_경기도.txt", hd, blocks)


# ---------------------------------------------------------------- 03 해상 낚시금지구역(SHP)
def sea_ban():
    base = SRC / "해양수산부 국립해양조사원_낚시금지구역_20250813"
    d = (base / "TL_RESARE_ENS.dbf").read_bytes()
    numrec, hdrlen, reclen = struct.unpack("<IHH", d[4:12])
    fields, off = [], 32
    while d[off] != 0x0D:
        fields.append((d[off:off + 11].split(b"\x00")[0].decode("euc-kr"), d[off + 16]))
        off += 32
    attrs = []
    for i in range(numrec):
        rec, pos, row = d[hdrlen + i * reclen: hdrlen + (i + 1) * reclen], 1, {}
        for nm, fl in fields:
            row[nm] = clean(rec[pos:pos + fl].decode("euc-kr", "replace"))
            pos += fl
        attrs.append(row)

    # SHP 폴리곤 -> 대표(중심) 좌표 + 경계 범위
    shp = (base / "TL_RESARE_ENS.shp").read_bytes()
    geoms, pos = [], 100
    while pos < len(shp):
        _, clen = struct.unpack(">II", shp[pos:pos + 8])
        body = shp[pos + 8: pos + 8 + clen * 2]
        pos += 8 + clen * 2
        if len(body) < 36 or struct.unpack("<I", body[:4])[0] != 5:
            geoms.append(None)
            continue
        xmin, ymin, xmax, ymax = struct.unpack("<4d", body[4:36])
        geoms.append((utmk_to_wgs84(xmin, ymin), utmk_to_wgs84(xmax, ymax),
                      utmk_to_wgs84((xmin + xmax) / 2, (ymin + ymax) / 2)))

    LABEL = [("gid", "공간정보아이디"), ("obj_sn", "객체일련번호"), ("inst_cd", "기관코드"),
             ("fbctn_ymd", "제작일자"), ("clsf_cd", "분류코드"), ("enc_lv", "전자해도레벨"),
             ("enc_no", "전자해도번호"), ("chrct_cd", "특성코드"), ("korn_nm", "한글명"),
             ("eng_nm", "영문명"), ("korn_etc_i", "한글기타정보"), ("eng_etc_in", "영문기타정보"),
             ("stts_cd", "상태코드"), ("lmt_rgn_cd", "제한지역코드"), ("lmt_artcl_", "제한항목지정코드")]
    blocks = []
    for i, a in enumerate(attrs):
        nm = a.get("korn_nm") or a.get("eng_nm") or "해상 낚시금지구역 %s" % a.get("obj_sn")
        g = geoms[i] if i < len(geoms) else None
        b = Block("[해상 낚시금지구역] %s (국립해양조사원 전자해도)" % nm)
        b.raw("구역구분: 해상(바다) 낚시금지구역 - 전자해도 등재 구역")
        if g:
            b.raw("대표좌표(WGS84): 위도 %.5f, 경도 %.5f" % (g[2][0], g[2][1]))
            b.raw("구역 경계 범위: 위도 %.5f~%.5f, 경도 %.5f~%.5f"
                  % (g[0][0], g[1][0], g[0][1], g[1][1]))
        for k, lab in LABEL:
            b.add(lab, a.get(k, ""), (fmt_date if k == "fbctn_ymd" else None))
        b.raw("자료출처: 해양수산부 국립해양조사원_낚시금지구역(TL_RESARE_ENS, 2025-08-13)")
        blocks.append(b)
    hd = head("해양수산부 국립해양조사원 해상 낚시금지구역(전자해도)",
              "전자해도(ENC)에 등재된 바다 낚시금지구역 공간정보",
              "공공데이터포털 - 해양수산부 국립해양조사원_낚시금지구역 SHP(TL_RESARE_ENS)",
              len(blocks),
              "구역명, 대표좌표(WGS84), 경계범위, 전자해도번호·레벨, 분류/특성/제한 코드, 제작일자")
    hd.insert(-1, "# ※ 원본 좌표계는 EPSG:5179(Korea 2000 / Unified CS)이며 WGS84 위경도로 변환해 수록했다.")
    write_txt("03_해상_낚시금지구역_국립해양조사원.txt", hd, blocks)


# ---------------------------------------------------------------- 04 전국 낚시터
def fishing_spots_national():
    header, rows = read_csv("낚시터정보.csv")
    blocks = []
    for r in rows:
        nm = clean(r["낚시터명"]) or "명칭미상"
        addr = clean(r["소재지도로명주소"]) or clean(r["소재지지번주소"])
        sido = region_of(addr)
        tail = "%s %s" % (sido, nm) if sido else nm
        b = Block("[낚시터] %s" % tail)
        if sido:
            b.raw("행정구역: %s" % sido)
        b.add("낚시터 유형", r["낚시터유형"])
        b.add("소재지(도로명)", r["소재지도로명주소"])
        b.add("소재지(지번)", r["소재지지번주소"])
        if clean(r["WGS84위도"]) and clean(r["WGS84경도"]):
            b.raw("좌표(WGS84): 위도 %s, 경도 %s" % (clean(r["WGS84위도"]), clean(r["WGS84경도"])))
        b.add("전화번호", r["낚시터전화번호"])
        b.add("수면적(㎡)", r["수면적"])
        b.add("주요어종", r["주요어종"])
        b.add("최대수용인원", r["최대수용인원"], lambda v: "%s명" % v if v.isdigit() else v)
        b.add("이용요금", r["이용요금"])
        b.raw("자료출처: 전국 낚시터 정보 표준데이터 (공공데이터포털)")
        blocks.append(b)

        b2 = Block("[낚시터 시설·이용정보] %s" % tail)
        if sido:
            b2.raw("행정구역: %s" % sido)
        b2.add("소재지", addr)
        b2.add("주요어종", r["주요어종"])
        b2.add("수상시설물 유형", r["수상시설물유형"])
        b2.add("주요 포인트", r["주요포인트"])
        b2.add("안전시설 현황", r["안전시설현황"], lambda v: v.replace("+", ", "))
        b2.add("편익시설 현황", r["편익시설현황"], lambda v: v.replace("+", ", "))
        b2.add("주변 관광지", r["주변관광지"], lambda v: v.replace("+", ", "))
        b2.add("관리기관", r["관리기관명"])
        b2.add("관리기관 전화", r["관리기관전화번호"])
        b2.add("데이터기준일자", fmt_date(r["데이터기준일자"]))
        if len(b2.lines) > 2:
            b2.raw("자료출처: 전국 낚시터 정보 표준데이터 (공공데이터포털)")
            blocks.append(b2)
    hd = head("전국 낚시터 정보 (표준데이터)",
              "전국 등록 낚시터의 위치·어종·요금·시설 정보",
              "공공데이터포털 - 전국낚시터정보표준데이터(낚시터정보.csv)",
              len(rows),
              "낚시터명, 유형, 주소, 위경도, 전화번호, 수면적, 주요어종, 최대수용인원, 이용요금, 안전·편익시설, 주변관광지, 관리기관")
    hd.insert(-1, "# ※ 낚시터 1곳당 '기본정보' 단락과 '시설·이용정보' 단락으로 나누어 수록했다.")
    write_txt("04_낚시터_전국.txt", hd, blocks)


# ---------------------------------------------------------------- 05 경기도 낚시터
def fishing_spots_gyeonggi():
    header, rows = read_csv("경기도_낚시터현황.csv")
    blocks = []
    for r in rows:
        nm = clean(r["낚시터명"])
        b = Block("[낚시터] 경기도 %s %s" % (clean(r["시군명"]), nm))
        b.raw("행정구역: 경기도 %s" % clean(r["시군명"]))
        b.add("등록구분", r["등록구분명"])
        b.add("집계년도", r["집계년도"], lambda v: "%s년" % v)
        b.add("낚시터 면적", r["낚시터면적(ha)"], lambda v: "%s ha" % v)
        b.add("이용료", r["이용료(원)"], lambda v: "%s원" % v)
        b.add("도로명주소", r["낚시터위치도로명주소"])
        b.add("지번주소", r["낚시터위치지번주소"])
        b.add("우편번호", r["낚시터위치우편번호"])
        if clean(r["WGS84위도"]) and clean(r["WGS84경도"]):
            b.raw("좌표(WGS84): 위도 %s, 경도 %s" % (clean(r["WGS84위도"]), clean(r["WGS84경도"])))
        b.raw("자료출처: 경기도 낚시터 현황 (경기도 제공)")
        blocks.append(b)
    hd = head("경기도 낚시터 현황",
              "경기도 시·군별 등록 낚시터 목록(면적·이용료·주소·좌표)",
              "공공데이터포털 - 경기도_낚시터현황",
              len(blocks),
              "시군명, 낚시터명, 등록구분, 면적(ha), 이용료, 도로명·지번주소, WGS84 위경도")
    write_txt("05_낚시터_경기도.txt", hd, blocks)


# ---------------------------------------------------------------- 06 낚시터 허가현황
def fishing_spots_permit():
    header, rows = read_csv("해양수산부_수산정보_낚시터_기본 정보_20251104.csv")
    blocks = []
    for r in rows:
        nm = clean(r["사업장_명"])
        sido = clean(r["시도 명"])
        b = Block("[낚시터 허가현황] %s %s" % (sido, nm))
        b.raw("행정구역: %s" % sido)
        b.add("위치", r["위치"])
        b.add("수면 면적(ha)", r["수면_면적"])
        b.add("이용 수면 구분", r["이용_수면_구분"])
        b.add("허가번호", r["허가_번호"])
        s, e = fmt_date(r["허가_시작_일자"]), fmt_date(r["허가_종료_일자"])
        if s or e:
            b.raw("허가기간: %s ~ %s" % (s or "미상", e or "미상"))
        facil = []
        for lab, key in (("수상시설물 합계", "수상_시설물_합계"), ("잔교형 낚시터", "잔교_형_낚시터_수"),
                         ("수상 낚시터", "수상_낚시터_수"), ("연안 방갈로", "연안_방갈로_수"),
                         ("수상 방갈로", "수상_방갈로_수"), ("관리 선박", "관리_선박_수")):
            v = clean(r[key])
            if v and v != "0":
                facil.append("%s %s개" % (lab, v))
        b.raw("시설 현황: %s" % (", ".join(facil) if facil else "등록된 수상시설물 없음"))
        b.raw("자료출처: 해양수산부 수산정보 낚시터 기본정보 (2025-11-04 기준)")
        blocks.append(b)
    hd = head("해양수산부 낚시터업 허가 낚시터 기본정보",
              "낚시터업 허가를 받은 전국 낚시터의 허가기간·수면적·시설 현황",
              "공공데이터포털 - 해양수산부_수산정보_낚시터_기본 정보(2025-11-04)",
              len(blocks),
              "시도, 사업장명, 위치, 수면면적, 이용수면구분, 허가번호·허가기간, 수상시설물/잔교형/방갈로/관리선박 수")
    write_txt("06_낚시터_허가현황_해양수산부.txt", hd, blocks)


# ---------------------------------------------------------------- 07/08 낚시포인트
def parse_methods(s):
    """'▶감성돔 - 릴찌/ 장대' -> [(어종, [기법...])]"""
    out = []
    for part in [p.strip() for p in clean(s).split("▶") if p.strip()]:
        if "-" in part:
            fish, how = part.split("-", 1)
            out.append((fish.strip(), [x.strip() for x in how.split("/") if x.strip()]))
        else:
            out.append((part, []))
    return out


def points(fname, kind, name_keys, lat_key, lon_key, outname, title, desc, extra=None):
    header, rows = read_csv(fname)
    blocks = []
    for r in rows:
        area = clean(r[name_keys[0]])
        spot = clean(r[name_keys[1]])
        region = clean(r["행정구역명"])
        b = Block("[%s] %s %s - %s" % (kind, region, area, spot))
        b.raw("행정구역: %s" % region)
        b.raw("포인트 권역: %s" % area)
        b.raw("포인트명: %s" % spot)
        lat = dms_to_dec(r.get(lat_key, ""))
        lon = dms_to_dec(r.get(lon_key, ""))
        if lat is None or lon is None:
            wl, wo = point_wgs(r["공간정보"])
            lat = lat if lat is not None else wl
            lon = lon if lon is not None else wo
        if lat and lon:
            b.raw("좌표(WGS84): 위도 %.6f, 경도 %.6f" % (lat, lon))
        b.add("수심 범위", r["수심범위내용"], lambda v: "%s m" % v)
        b.add("바닥 재질(주원료)", r["주원료내용"])
        b.add("추천 물때(조수)", r["조수물때내용"])
        ms = parse_methods(r["낚시방법대상내용"])
        if ms:
            b.raw("대상어종: %s" % ", ".join(f for f, _ in ms))
            for fish, how in ms:
                if how:
                    b.raw("  - %s 낚시기법: %s" % (fish, ", ".join(how)))
        if extra:
            for lab, key in extra:
                b.add(lab, r.get(key, ""))
        b.raw("자료출처: %s" % desc)
        blocks.append(b)
    hd = head(title, kind + " 위치·수심·물때·대상어종·낚시기법 정보", desc, len(blocks),
              "행정구역, 포인트 권역·명칭, WGS84 위경도, 수심범위, 바닥재질, 조수물때, 대상어종별 낚시기법")
    hd.insert(-1, "# ※ 원본 공간정보(EPSG:5179)를 WGS84 위경도로 변환해 수록했다.")
    write_txt(outname, hd, blocks)


# ---------------------------------------------------------------- 09 어획정보
def catch_info():
    SPECS = [
        ("전북특별자치도_군산해역 어획 정보_20171116.csv", "구분", "전북특별자치도 군산해역", "2017-11-16"),
        ("전북특별자치도_군산 어획된 품종별 현황(개체수 및 현존량)_20190605.csv", "어획 품종",
         "전북특별자치도 군산해역", "2019-06-05"),
        ("전북특별자치도_부안해역 어획정보_20171116.csv", "구분", "전북특별자치도 부안해역", "2017-11-16"),
        ("전북특별자치도_부안 어획 품종별 현황(개체수 및 현존량)_20190605.csv", "품종 구분",
         "전북특별자치도 부안해역", "2019-06-05"),
    ]
    blocks = []
    for fname, key, area, base in SPECS:
        header, rows = read_csv(fname)
        months = []
        for h in header[1:]:
            m = re.match(r"(\d+)월", h)
            if m:
                months.append((m.group(1), h, "개체수" in h))
        for r in rows:
            sp = clean(r[key])
            if not sp:
                continue
            kor = re.sub(r"\s*\(.*?\)\s*", "", sp).strip()
            sci = (re.search(r"\((.*?)\)", sp).group(1) if "(" in sp else "")
            b = Block("[해역 어획정보] %s - %s (%s 조사)" % (area, kor, base[:4]))
            b.raw("조사해역: %s" % area)
            b.raw("어종(품종): %s%s" % (kor, " / 학명 %s" % sci if sci else ""))
            per = {}
            for mon, h, is_count in months:
                v = clean(r.get(h, ""))
                if v in ("", "0", "0.0"):
                    continue
                per.setdefault(mon, {})["개체수" if is_count else "현존량"] = v
            if per:
                for mon in sorted(per, key=int):
                    d = per[mon]
                    b.raw("  %s월: 개체수 %s마리, 현존량 %s kg"
                          % (mon, d.get("개체수", "0"), d.get("현존량", "0")))
                b.raw("어획 확인 월: %s월" % "·".join(sorted(per, key=int)))
            else:
                b.raw("  조사 기간(3·5·7·9·11월) 중 어획 실적 없음")
            b.raw("자료출처: %s 어획정보 (전북특별자치도, %s 기준)" % (area, base))
            blocks.append(b)
    hd = head("전북 군산·부안 해역 월별 어획 품종 현황",
              "해역별·월별 어획 어종의 개체수 및 현존량(생물량) 조사 결과",
              "공공데이터포털 - 전북특별자치도 군산/부안 해역 어획정보(2017-11-16, 2019-06-05)",
              len(blocks),
              "조사해역, 어종(국명·학명), 3·5·7·9·11월별 개체수(마리)와 현존량(kg)")
    hd.insert(-1, "# ※ 어느 해역에서 어떤 어종이 어느 시기에 잡히는지 판단하는 근거 자료다.")
    write_txt("09_해역별_어획정보_군산_부안.txt", hd, blocks)


# ---------------------------------------------------------------- 10 수중생태조사 정점
def survey_stations():
    header, rows = read_csv("해양수산부_해양생태계종합조사_수중생태조사 정점_20221231.csv")
    blocks = []
    for r in rows:
        lat, lon = dms_to_dec(r["위도"]), dms_to_dec(r["경도"])
        b = Block("[해양생태 조사정점] %s (정점번호 %s)" % (clean(r["정점명"]), clean(r["정점번호"])))
        b.raw("원본 좌표(도분초): 위도 %s, 경도 %s" % (clean(r["위도"]), clean(r["경도"])))
        if lat and lon:
            b.raw("좌표(WGS84 십진도): 위도 %.6f, 경도 %.6f" % (lat, lon))
        b.add("조사년도", r["조사년도"], lambda v: "%s년" % v)
        b.add("일련번호", r["일련번호"])
        b.raw("자료출처: 해양수산부 해양생태계종합조사 수중생태조사 정점 (2022-12-31 기준)")
        blocks.append(b)
    hd = head("해양생태계 종합조사 수중생태조사 정점",
              "국가 해양생태계 종합조사의 수중생태 조사 지점 좌표 목록",
              "공공데이터포털 - 해양수산부_해양생태계종합조사_수중생태조사 정점(2022-12-31)",
              len(blocks),
              "정점명, 정점번호, 위경도(도분초 및 십진도), 조사년도")
    write_txt("10_해양생태계_수중생태조사정점.txt", hd, blocks)


if __name__ == "__main__":
    gyeonggi_ban()
    sea_ban()
    fishing_spots_national()
    fishing_spots_gyeonggi()
    fishing_spots_permit()
    points("해양수산부_공동활용체계_갯바위낚시포인트_20221231.csv", "갯바위 낚시포인트",
           ("포인트지역명", "포인트명"), "갯바위낚시포인트도분초위도", "갯바위낚시포인트경도",
           "07_갯바위낚시포인트_전국.txt", "전국 갯바위 낚시포인트",
           "해양수산부 공동활용체계 갯바위낚시포인트 (2022-12-31 기준)")
    points("해양수산부_공동활용체계_선상낚시포인트_20231231.csv", "선상 낚시포인트",
           ("포인트명1", "포인트명2"), "선상낚시포인트도분초위도", "선상낚시포인트도분초경도",
           "08_선상낚시포인트_전국.txt", "전국 선상 낚시포인트",
           "해양수산부 공동활용체계 선상낚시포인트 (2023-12-31 기준)",
           extra=[("고시내용", "고시내용")])
    catch_info()
    survey_stations()
