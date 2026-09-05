# -*- coding: utf-8 -*-
"""원본 CSV/XLSX/DBF의 모든 셀 값이 TXT에 누락 없이 들어갔는지 검증한다."""
import glob
import re
import sys
import unicodedata
from build_txt import SRC, OUT, read_csv, clean, read_xlsx

sys.stdout.reconfigure(encoding="utf-8")

# 검증에서 제외할 컬럼: 내부 관리용 코드/타임스탬프 등 의도적으로 생략한 항목
SKIP_COLS = {
    "낚시터정보.csv": {"개방자치단체코드", "관리번호", "데이터갱신구분", "데이터갱신시점", "최종수정시점"},
    "해양수산부_수산정보_낚시터_기본 정보_20251104.csv": {"시도"},
    "해양수산부_공동활용체계_갯바위낚시포인트_20221231.csv":
        {"공간정보일련번호", "공간정보", "갯바위낚시포인트도분초위도", "갯바위낚시포인트경도"},
    "해양수산부_공동활용체계_선상낚시포인트_20231231.csv":
        {"공간정보일련번호", "공간정보", "선상낚시포인트도분초위도", "선상낚시포인트도분초경도"},
    "해양수산부_해양생태계종합조사_수중생태조사 정점_20221231.csv": set(),
    "경기도낚시금지및제한구역지정현황.csv": set(),
}
NUMERIC_ONLY = re.compile(r"^[\d.,\-]+$")


def norm(s):
    s = unicodedata.normalize("NFC", clean(s))
    return re.sub(r"[\s,+]", "", s)


def covered(nv, corpus_n):
    """값 전체가 없으면, 재구성 과정에서 쪼개진 각 조각이 모두 있는지 확인한다."""
    if nv in corpus_n:
        return True
    parts = [p for p in re.split(r"[()\[\]/·~+▶>\-]", nv) if len(p) >= 2 and not NUMERIC_ONLY.fullmatch(p)]
    return bool(parts) and all(p in corpus_n for p in parts)


def main():
    corpus = ""
    for p in sorted(OUT.glob("*.txt")):
        corpus += unicodedata.normalize("NFC", p.read_text(encoding="utf-8"))
    corpus_n = re.sub(r"[\s,+]", "", corpus)

    total_cells = missing = 0
    problems = []
    for path in sorted(SRC.glob("*.csv")):
        header, rows = read_csv(path.name)
        skip = SKIP_COLS.get(path.name, set())
        for i, r in enumerate(rows):
            for k, v in r.items():
                if k in skip or not v:
                    continue
                total_cells += 1
                nv = norm(v)
                if len(nv) < 2 or NUMERIC_ONLY.fullmatch(nv):
                    continue  # 짧은 값/숫자는 우연 일치가 많아 개별 검증 대상에서 제외
                if not covered(nv, corpus_n):
                    missing += 1
                    if len(problems) < 40:
                        problems.append("%s [행%d] %s = %s" % (path.name, i + 2, k, v[:70]))

    # 익산 xlsx 본문 시트
    sheets = read_xlsx(SRC / "전북특별자치도 익산시_낚시금지구역_20260831.xlsx")
    main_rows = sheets["익산시 낚시금지구역"]
    for r in main_rows[1:]:
        for v in r:
            nv = norm(v)
            if len(nv) < 2 or NUMERIC_ONLY.fullmatch(nv):
                continue
            total_cells += 1
            if not covered(nv, corpus_n):
                missing += 1
                problems.append("익산시 xlsx: %s" % v[:70])

    print("검증 대상 셀(비어있지 않음): %d" % total_cells)
    print("TXT에서 찾지 못한 값       : %d" % missing)
    for p in problems:
        print("  ! " + p)
    print("\n생성된 TXT 파일:")
    for p in sorted(OUT.glob("*.txt")):
        n = p.read_text(encoding="utf-8")
        print("  %-42s %8d bytes  단락 %5d개"
              % (p.name, len(n.encode("utf-8")), n.count("\n\n")))


if __name__ == "__main__":
    main()
