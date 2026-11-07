"""
11/09 설계 보고 — 데이터베이스 정의서(각주 2: ER-Diagram 을 반영하는 테이블 정의서 + 조별 특화 비즈니스 로직 고도화 방안)
  .venv/bin/python scripts/build_table_spec_xlsx.py docs/03-3_테이블정의서.xlsx

교수님 예시 양식이 없는 산출물이라 03-2(표준용어 정의서) 예시와 같은 모양(맑은 고딕, 제목 16 굵게, 머리글 채움)으로 만든다.
  1 테이블 목록      28개 테이블: 업무 영역, 논리명·물리명, 설명, 슈퍼타입/서브타입
  2 테이블 정의      테이블별 컬럼: 논리명(03-2 표준용어와 일치)·물리명·타입·NULL·키·기본값·설명·참조
  3 관계(외래키)     외래키 43개: 자식 → 부모, 삭제 규칙, ERD 관계 설명
  4 DB 객체          뷰·트리거·프로시저와 역할
  5 비즈니스 로직 고도화 방안   조별 특화 시나리오 A·B, 비즈니스 규칙 BR-01~30 과 구현 객체, 가정(팀 결정) 24개
모든 내용은 실제 DB(information_schema) 에서 읽는다.
"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import openpyxl
import pymysql
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from si_pms_terms import AREAS, ENTITY, term_of  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "03-3_테이블정의서.xlsx"
DB = "si_pms"

conn = pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
                       user=os.environ.get("DB_ADMIN_USER", "root"), password=os.environ.get("DB_ADMIN_PASSWORD", "root1234"),
                       database="information_schema", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()


def q(sql, *a):
    cur.execute(sql, a)
    return cur.fetchall()


TABLES = {r["t"]: r for r in q("SELECT table_name t, table_comment c FROM tables WHERE table_schema=%s AND table_type='BASE TABLE'", DB)}
COLS = q("""SELECT c.table_name t, c.column_name c, c.column_type ty, c.is_nullable n, c.column_key k, c.column_default d, c.column_comment cm, c.extra x
            FROM columns c JOIN tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
            WHERE c.table_schema=%s AND t.table_type = 'BASE TABLE' ORDER BY c.table_name, c.ordinal_position""", DB)
FKS = q("""SELECT k.table_name t, k.column_name c, k.referenced_table_name rt, k.referenced_column_name rc, r.delete_rule dr, k.constraint_name cn
           FROM key_column_usage k JOIN referential_constraints r ON r.constraint_schema=k.table_schema AND r.constraint_name=k.constraint_name
           WHERE k.table_schema=%s AND k.referenced_table_name IS NOT NULL ORDER BY k.table_name, k.ordinal_position""", DB)
UKS = q("""SELECT table_name t, index_name i, GROUP_CONCAT(column_name ORDER BY seq_in_index) cols FROM statistics
           WHERE table_schema=%s AND index_name<>'PRIMARY' AND non_unique=0 GROUP BY table_name, index_name""", DB)
IDX = q("""SELECT table_name t, index_name i, GROUP_CONCAT(column_name ORDER BY seq_in_index) cols FROM statistics
           WHERE table_schema=%s AND index_name<>'PRIMARY' AND non_unique=1 AND index_name NOT LIKE 'fk_%%' GROUP BY table_name, index_name""", DB)
CHECKS = q("SELECT c.constraint_name cn, t.table_name t, c.check_clause cl FROM check_constraints c JOIN table_constraints t USING (constraint_schema, constraint_name) WHERE c.constraint_schema=%s", DB)
VIEWS = q("SELECT table_name v FROM views WHERE table_schema=%s ORDER BY 1", DB)
TRIGGERS = q("SELECT trigger_name n, action_timing ti, event_manipulation ev, event_object_table tb FROM triggers WHERE trigger_schema=%s ORDER BY event_object_table, action_timing, event_manipulation", DB)
ROUTINES = q("SELECT routine_name n, routine_type ty FROM routines WHERE routine_schema=%s ORDER BY 1", DB)
assert set(TABLES) == set(ENTITY), set(TABLES) ^ set(ENTITY)
assert len(FKS) == 43, len(FKS)

FK_OF = {(f["t"], f["c"]): f for f in FKS}
UK_OF = {}
for u in UKS:
    for c in u["cols"].split(","):
        UK_OF.setdefault((u["t"], c), []).append(u["cols"])
PK_COUNT = {t: sum(1 for r in COLS if r["t"] == t and r["k"] == "PRI") for t in TABLES}
SUPER = {"employee": ("슈퍼타입", "emp_type"), "evaluation": ("슈퍼타입", "eval_type")}
SUB = {"developer": "employee", "staff": "employee", "customer_eval": "evaluation", "pm_eval": "evaluation", "peer_eval": "evaluation"}
ORDER = [t for a in AREAS for t in ENTITY if ENTITY[t][1] == a]

# ------------------------------------------------------------------ 서식 (03-2 예시: 맑은 고딕, 제목 16 굵게 + 아래 굵은선, 머리글 채움)
F = lambda **k: Font(name="맑은 고딕", size=k.pop("size", 10), bold=k.pop("bold", False), color=k.pop("color", None))
HDR_FILL, SEC_FILL, TBL_FILL = PatternFill("solid", fgColor="FFF2CC"), PatternFill("solid", fgColor="DDEBF7"), PatternFill("solid", fgColor="E2EFDA")
thin, med = Side(style="thin", color="808080"), Side(style="medium")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)
CENTER, LEFT = Alignment(horizontal="center", vertical="center", wrap_text=True), Alignment(horizontal="left", vertical="center", wrap_text=True)

wb = openpyxl.Workbook()
wb.remove(wb.active)


def sheet(name, title, widths):
    ws = wb.create_sheet(name)
    ws["B2"] = title
    ws["B2"].font, ws["B2"].alignment = F(size=16, bold=True), Alignment(vertical="center")
    ws.row_dimensions[2].height = 27
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.column_dimensions["A"].width = 2.5
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation, ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = "landscape", 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    return ws


def header(ws, r, labels, fill=HDR_FILL, size=10):
    for i, text in enumerate(labels):
        c = ws.cell(row=r, column=2 + i, value=text)
        c.font, c.fill, c.alignment, c.border = F(size=size, bold=True), fill, CENTER, BOX
    ws.row_dimensions[r].height = 20


def row(ws, r, values, center_cols=(), fill=None, height=None):
    for i, v in enumerate(values):
        c = ws.cell(row=r, column=2 + i, value=v)
        c.font, c.border = F(), BOX
        c.alignment = CENTER if i in center_cols else LEFT
        if fill:
            c.fill = fill
    if height:
        ws.row_dimensions[r].height = height


def note(ws, r, text, ncols):
    ws.cell(row=r, column=2, value=text).font = F(size=9, color="666666")
    ws.cell(row=r, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=1 + ncols)


def lines_of(text, width_chars):
    return max(1, sum(max(1, -(-len(s) // width_chars)) for s in str(text).split("\n")))


# ================================================================== 1. 테이블 목록
ws = sheet("테이블 목록", "테이블 정의서 — 테이블 목록", {"B": 5, "C": 11, "D": 18, "E": 22, "F": 52, "G": 16, "H": 8})
note(ws, 3, f"SI-PMS · 테이블 {len(TABLES)}개 · 외래키 {len(FKS)}개 · 뷰 {len(VIEWS)}개 · 트리거 {len(TRIGGERS)}개 · 프로시저 {len(ROUTINES)}개 "
             "(실제 DB information_schema 에서 생성, DDL: db/init/01_schema.sql). 논리명은 03-2 표준용어 정의서와 일치. ERD: 2차_설계보고_1109/ERD/", 7)
ws.row_dimensions[3].height = 30
header(ws, 4, ["No", "업무 영역", "테이블 (논리명)", "물리명", "설명", "슈퍼타입/서브타입", "컬럼 수"])
for i, t in enumerate(ORDER):
    kind = ""
    if t in SUPER:
        kind = f"슈퍼타입 (판별자 {SUPER[t][1]})"
    elif t in SUB:
        kind = f"서브타입 of {ENTITY[SUB[t]][0]}"
    row(ws, 5 + i, [i + 1, ENTITY[t][1], ENTITY[t][0], t, TABLES[t]["c"], kind, sum(1 for r in COLS if r["t"] == t)], center_cols=(0, 1, 3, 6))
ws.freeze_panes = "B5"

# ================================================================== 2. 테이블 정의
ws = sheet("테이블 정의", "테이블 정의서 — 테이블별 컬럼 정의", {"B": 5, "C": 22, "D": 22, "E": 20, "F": 6, "G": 9, "H": 16, "I": 54, "J": 24})
note(ws, 3, "키: PK 기본키 · FK 외래키 · UK 고유키(UNIQUE). 참조: FK 가 가리키는 부모 테이블.컬럼. "
             "논리명은 03-2 표준용어 정의서의 용어와 같다. 열거형(ENUM) 값의 뜻은 03-2 표준코드 시트 참고.", 9)
ws.row_dimensions[3].height = 30
r = 5
for i, t in enumerate(ORDER):
    ws.cell(row=r, column=2, value=f"T{i + 1:02d}  {ENTITY[t][0]}  ({t})").font = F(size=11, bold=True)
    ws.cell(row=r, column=2).fill = TBL_FILL
    ws.cell(row=r, column=2).alignment = LEFT
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    extra = []
    if t in SUPER:
        extra.append(f"슈퍼타입 · 판별자 {SUPER[t][1]}")
    if t in SUB:
        extra.append(f"서브타입 of {ENTITY[SUB[t]][0]} (PK = FK)")
    desc = TABLES[t]["c"] + ("  |  " + " · ".join(extra) if extra else "")
    c = ws.cell(row=r, column=7, value=f"{ENTITY[t][1]}  |  {desc}")
    c.font, c.fill, c.alignment = F(), TBL_FILL, LEFT
    ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=10)
    for col in range(2, 11):
        ws.cell(row=r, column=col).border = Border(top=med, bottom=thin, left=thin if col == 2 else None, right=thin if col == 10 else None)
    ws.row_dimensions[r].height = 22
    r += 1
    header(ws, r, ["No", "컬럼 (논리명)", "물리명", "타입", "NULL", "키", "기본값", "설명", "참조"], size=9)
    r += 1
    for j, col in enumerate([x for x in COLS if x["t"] == t]):
        keys = []
        if col["k"] == "PRI":
            keys.append("PK")
        if (t, col["c"]) in FK_OF:
            keys.append("FK")
        if (t, col["c"]) in UK_OF:
            keys.append("UK" + ("(복합)" if any("," in u for u in UK_OF[(t, col["c"])]) else ""))
        fk = FK_OF.get((t, col["c"]))
        ref = f"{ENTITY[fk['rt']][0]}.{fk['rc']}" + (" (ON DELETE CASCADE)" if fk["dr"] == "CASCADE" else "") if fk else ""
        default = col["d"] if col["d"] is not None else ""
        if "auto_increment" in (col["x"] or ""):
            default = "AUTO_INCREMENT"
        elif "on update" in (col["x"] or "").lower():
            default = f"{default} (수정 시 갱신)"
        ty = col["ty"].replace("enum(", "ENUM(")
        term, _ = term_of(col)
        row(ws, r, [j + 1, term, col["c"], ty, "Y" if col["n"] == "YES" else "N", " ".join(keys), default, col["cm"], ref], center_cols=(0, 4, 5))
        ws.row_dimensions[r].height = max(16, 13 * max(lines_of(col["cm"], 40), lines_of(ty, 22)) + 3)
        r += 1
    chk = [c for c in CHECKS if c["t"] == t]
    idx = [x for x in IDX if x["t"] == t]
    uks = [u for u in UKS if u["t"] == t]
    extra = []
    if uks:
        extra.append("UNIQUE: " + ", ".join(f"{u['i']}({u['cols']})" for u in uks))
    if chk:
        extra.append("CHECK: " + "; ".join(f"{c['cn']} {c['cl']}" for c in chk))
    if idx:
        extra.append("INDEX: " + ", ".join(f"{x['i']}({x['cols']})  ← 대표 시나리오 S2 성능 향상(커버링 인덱스)" if x["i"] == "idx_assignment_period" else f"{x['i']}({x['cols']})" for x in idx))
    if extra:
        note(ws, r, "\n".join(extra), 9)
        ws.row_dimensions[r].height = 13 * sum(lines_of(e, 120) for e in extra) + 4
        r += 1
    r += 1
ws.freeze_panes = "B5"

# ================================================================== 3. 관계(외래키)
ws = sheet("관계(외래키)", "테이블 정의서 — 관계 (외래키)", {"B": 5, "C": 22, "D": 22, "E": 22, "F": 20, "G": 16, "H": 30, "I": 50})
note(ws, 3, "ERD(IE 표기)의 관계선 하나가 외래키 하나에 대응한다. 1:N 관계는 모두 1측 Partial(자식이 없는 부모 허용), N측은 FK NOT NULL 이면 Total. "
             "슈퍼타입-서브타입은 PK=FK 1:1 관계이며 ⊗ 배타·완전 참여.", 8)
ws.row_dimensions[3].height = 30
header(ws, 4, ["No", "자식 테이블", "FK 컬럼", "부모 테이블", "부모 컬럼", "삭제 규칙", "제약 이름", "관계 설명"])
COL_NULL = {(c["t"], c["c"]): c["n"] == "YES" for c in COLS}
for i, f in enumerate(FKS):
    if f["t"] in SUB and f["rt"] == SUB[f["t"]]:
        kind = f"슈퍼타입-서브타입 (1:1, 배타·완전). {ENTITY[f['rt']][0]} 1 — {ENTITY[f['t']][0]} 0..1"
    else:
        n_side = "0..N" if True else ""
        opt = "FK NULL 허용 (0..1 : 0..N)" if COL_NULL[(f["t"], f["c"])] else "FK NOT NULL (1 : 0..N)"
        kind = f"{ENTITY[f['rt']][0]} 1 —< {ENTITY[f['t']][0]} {n_side}  ·  {opt}"
    row(ws, 5 + i, [i + 1, f"{ENTITY[f['t']][0]} ({f['t']})", f["c"], f"{ENTITY[f['rt']][0]} ({f['rt']})", f["rc"], f["dr"], f["cn"], kind], center_cols=(0, 5))
ws.freeze_panes = "B5"

# ================================================================== 4. DB 객체
ws = sheet("DB 객체", "테이블 정의서 — 뷰 · 트리거 · 프로시저", {"B": 5, "C": 30, "D": 22, "E": 22, "F": 70})
note(ws, 3, "무결성 규칙(BR)은 화면이 아니라 DB 의 트리거·프로시저가 지킨다. 화면을 거치지 않는 SQL 적재에도 같은 규칙이 적용된다. (db/init/02_logic.sql)", 5)
header(ws, 4, ["No", "객체", "유형", "대상 테이블", "역할"])
VIEW_ROLE = {"v_employee": "직원 + 서브타입 + 계정을 합친 조회용 (주민번호 마스킹 포함)", "v_assignment_detail": "투입 + 프로젝트 + 발주처 + 직무 조인 (경력 이력 화면)",
             "v_eval_score": "평가 1건의 항목별 평점 가중 평균 (평가유형·상태·제출일 포함)",
             "v_project_eval_summary": "피평가자별 고객/PM/동료 평균과 가중 종합점수·인센티브 등급 (S4·S5)",
             "v_change_request": "변경요청 ⋈ 프로젝트 ⋈ 발주처 ⋈ 담당자 ⋈ PM ⋈ 최신 검토안 ⋈ 결정자 ⋈ 동의 담당자 ⋈ 적용이력 (S7)",
             "v_training_plan": "역량개선계획 ⋈ 직원 ⋈ 프로젝트 ⋈ 평가 종합 ⋈ 추천 과정 ⋈ 담당자 ⋈ 최근 신청·일정. 이수 상태는 신청 이력에서 계산 (S8)"}
TRG_ROLE = {"trg_employee_bi": "사번 자동 채번 (BR-02)", "trg_project_bi": "프로젝트번호 자동 채번 (BR-02)",
            "trg_assignment_bi": "투입 검증 (BR-01,03~07)", "trg_assignment_bu": "투입 수정 검증 (BR-01,03~07)",
            "trg_evaluation_bi": "평가 등록 검증 (BR-08,09)", "trg_customer_eval_bi": "고객 평가 검증·피평가자당 1건 (BR-10,11,12)",
            "trg_pm_eval_bi": "PM 평가 검증 (BR-10,13)", "trg_peer_eval_bi": "동료 평가 검증 (BR-10,14)",
            "trg_developer_bu": "등급 변경일 갱신 (BR-15)", "trg_developer_au": "등급 변경 이력 기록 (BR-15)",
            "trg_developer_bi": "개발자 서브타입 = 판별자 DEV, 지원직과 배타 (BR-30)", "trg_staff_bi": "지원직 서브타입 = 판별자 STAFF, 개발자와 배타 (BR-30)",
            "trg_employee_bu": "서브타입이 있는 직원의 판별자 변경 금지 (BR-30)",
            "trg_change_request_bi": "변경요청 검증·요청번호 채번 (BR-16,17,18)", "trg_change_review_bi": "검토안 등록 검증 (BR-18,19,21,22)",
            "trg_change_review_bu": "검토안 결정·동의 검증, 결정 후 수정 금지 (BR-19~22)", "trg_change_review_ai": "요청 상태 갱신",
            "trg_change_review_au": "요청 상태 갱신", "trg_change_history_bi": "반영 가능 여부 검증 (BR-19,23)",
            "trg_change_history_ai": "요청 상태 APPLIED", "trg_development_plan_bi": "계획 대상·담당자 검증 (BR-24,25)",
            "trg_enrollment_bi": "신청 검증: 추천 과정·시작 전·중복·정원 (BR-26~29)", "trg_enrollment_bu": "취소·수료 시점 검증 (BR-29)"}
SP_ROLE = {"sp_next_seq": "연도별 일련번호 채번 (행 잠금으로 동시 가입에도 중복 없음, BR-02)", "sp_validate_assignment": "투입 규칙 검증 공통 로직 (BR-01,03~07)",
           "sp_validate_change_review": "검토안 등록·결정·동의 공통 검증 (BR-18~22)", "sp_sync_change_status": "최신 검토안 기준 변경요청 상태 계산",
           "sp_apply_change": "변경 반영: 검증 → 이력 기록 → 종료예정일·계약금액 변경 (BR-23)",
           "sp_register_employee": "직원 + 서브타입 한 번에 등록, 실패 시 직원 행 제거 (BR-30 전체 참여)"}
r = 5
for v in VIEWS:
    row(ws, r, [r - 4, v["v"], "VIEW", "", VIEW_ROLE.get(v["v"], "")], center_cols=(0, 2)); r += 1
for t in TRIGGERS:
    row(ws, r, [r - 4, t["n"], f"{t['ti']} {t['ev']} 트리거", t["tb"], TRG_ROLE.get(t["n"], "")], center_cols=(0, 2)); r += 1
for p in ROUTINES:
    row(ws, r, [r - 4, p["n"], p["ty"], "", SP_ROLE.get(p["n"], "")], center_cols=(0, 2)); r += 1
missing = [v["v"] for v in VIEWS if v["v"] not in VIEW_ROLE] + [t["n"] for t in TRIGGERS if t["n"] not in TRG_ROLE] + [p["n"] for p in ROUTINES if p["n"] not in SP_ROLE]
assert not missing, missing
ws.freeze_panes = "B5"

# ================================================================== 5. 비즈니스 로직 고도화 방안
ws = sheet("비즈니스 로직 고도화 방안", "조별 특화 비즈니스 로직 고도화 방안", {"B": 8, "C": 26, "D": 60, "E": 46, "F": 30})
note(ws, 3, "Problem Description 의 기본 업무(인력·투입·평가) 위에 더한 것: ① 조별 특화 시나리오 2개 ② 데이터 무결성 규칙(BR) 30개 — 모두 DB 트리거·프로시저로 강제 "
             "③ 문제 설명에 없어 팀이 정한 가정 24개. 검증: db/demo/constraint_tests.sql (위반 32건 모두 DB 가 거부).", 5)
ws.row_dimensions[3].height = 30
r = 5


def section(title):
    global r
    c = ws.cell(row=r, column=2, value=title)
    c.font, c.fill, c.alignment = F(size=12, bold=True), SEC_FILL, LEFT
    ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 22
    r += 1


section("1. 조별 특화 시나리오")
header(ws, r, ["구분", "시나리오", "업무 흐름", "신규 엔터티 (ERD)", "화면 · 데모"]); r += 1
SCEN = [
    ("A", "고객사 변경요청 및 승인 관리",
     "① 발주처 담당자의 변경요청을 PM 이 접수 (요청번호 자동 채번)\n② PM 이 검토안(영향 분석: 제안 종료예정일·추가 계약금액·의견) 작성, 차수 관리\n"
     "③ 경영진이 내부 승인 / 반려\n④ 승인된 검토안에 고객사 동의 / 거절 기록 (확인 근거 보존)\n⑤ 승인 + 동의된 최신 차수만 계획에 반영 → 프로젝트 종료예정일·계약금액 변경, 변경 전후 값 이력 보존\n"
     "※ 승인 후 내용이 바뀌면 새 차수로 재검토 (이전 차수는 수정 불가)",
     "변경요청 change_request (1) ─< 변경검토안 change_review (N, 차수) ─ 변경적용이력 change_history (0..1)\n"
     "프로젝트에 종료예정일(end_date)과 실제 종료일(actual_end_date)을 분리",
     "변경요청 접수·검토안·동의·반영 화면, 경영진 승인 화면, 변경요청 처리 현황 리포트 (데모 S7, 10개 테이블 조인)\n규칙 BR-16 ~ BR-23"),
    ("B", "프로젝트 평가 기반 역량 개선 및 교육 이수 관리",
     "① 종료 프로젝트의 평가 결과(항목별 평점·평가 내용)와 보유 기술을 교육 담당자(경영관리 직원 중 지정)가 검토\n"
     "② 직원별 역량개선계획 수립: 추천 교육과정 · 개선 목표 · 이수 목표일 (근거 프로젝트 기록)\n③ 직원이 추천 과정의 교육일정에 신청 / 취소 (정원·시작 전 검증)\n"
     "④ 교육 종료 후 담당자가 수료 / 미수료 기록 (취소·미수료 이력 보존, 재수강은 새 신청)\n⑤ 평가 결과 + 교육 이수 현황을 함께 조회",
     "교육과정 training_course (1) ─< 교육일정 training_session (N)\n역량개선계획 development_plan (직원 × 추천 과정, 근거 프로젝트)\n"
     "교육신청 training_enrollment (계획 × 일정, 상태·출석)\n지원직에 교육담당자 지정 여부(is_training_manager)",
     "교육 관리(담당자)·역량개선계획 수립·내 교육(직원) 화면, 교육 이수 현황 리포트 (데모 S8, 9개 테이블 조인)\n규칙 BR-24 ~ BR-29"),
]
for s in SCEN:
    row(ws, r, list(s), center_cols=(0,), height=13 * max(lines_of(s[2], 56), lines_of(s[3], 42), lines_of(s[4], 28)) + 6); r += 1
r += 1

section("2. 데이터 무결성 · 비즈니스 규칙 (DB 트리거 · 프로시저로 강제)")
header(ws, r, ["규칙", "영역", "내용", "구현 객체", "검증"]); r += 1
BRS = [
    ("BR-01", "투입", "프로젝트에는 개발자(developer 서브타입)만 투입 가능", "sp_validate_assignment (trg_assignment_bi/bu), FK → developer", "constraint_tests 거부"),
    ("BR-02", "채번", "사번 E+YY+NNNN, 프로젝트번호 P+YYYY-NNN, 변경요청번호 CR+YYYY-NNN 을 연도별 순번으로 자동 채번", "trg_employee_bi, trg_project_bi, trg_change_request_bi → sp_next_seq (seq_counter 행 잠금)", "가입 시 E26xxxx 부여"),
    ("BR-03", "투입", "투입 기간은 프로젝트 기간 내", "sp_validate_assignment", "거부"),
    ("BR-04", "투입", "동일 직원의 동일 프로젝트 투입 기간은 겹칠 수 없음 (직무 변경은 기간을 나눠 재투입)", "sp_validate_assignment", "거부"),
    ("BR-05", "투입", "같은 기간 개인 투입률 합계 100% 이하 (동시 투입 허용)", "sp_validate_assignment", "거부"),
    ("BR-06", "투입", "같은 기간 프로젝트 PM 은 1명 (기간을 나눠 교체 가능)", "sp_validate_assignment", "거부"),
    ("BR-07", "투입", "직무별 최소 기술등급 (PM 고급↑, PL·분석자·설계자 중급↑, 프로그래머·테스터 초급↑)", "sp_validate_assignment, job_role.min_grade", "거부"),
    ("BR-08", "평가", "평가는 종료(COMPLETED)된 프로젝트에만 등록", "trg_evaluation_bi", "거부"),
    ("BR-09", "평가", "피평가자는 해당 프로젝트 참여자 (일부 기간 투입자 포함)", "trg_evaluation_bi", "거부"),
    ("BR-10", "평가", "서브타입(고객/PM/동료) 평가는 슈퍼타입의 eval_type 과 일치", "trg_customer_eval_bi, trg_pm_eval_bi, trg_peer_eval_bi", "거부"),
    ("BR-11", "평가", "고객 평가자는 해당 프로젝트 발주처의 담당자", "trg_customer_eval_bi", "거부"),
    ("BR-12", "평가", "고객 평가 의뢰는 프로젝트 PM 만, 피평가자당 1건", "trg_customer_eval_bi", "거부"),
    ("BR-13", "평가", "PM 평가의 평가자는 프로젝트 PM, 자기 자신 불가, 피평가자당 1건", "trg_pm_eval_bi", "거부"),
    ("BR-14", "평가", "동료 평가의 평가자는 참여자, 자기 자신 불가, (평가자, 피평가자)당 1건", "trg_peer_eval_bi", "거부"),
    ("BR-15", "경력", "기술등급 변경 시 변경 전후·처리자·사유를 이력으로 자동 기록", "trg_developer_bu/au → grade_history", "이력 행 확인"),
    ("BR-30", "직원", "직원 서브타입은 판별자(emp_type)와 일치·배타, 서브타입이 있으면 판별자 변경 금지, 모든 직원은 서브타입 보유(전체 참여)",
     "trg_developer_bi, trg_staff_bi, trg_employee_bu, sp_register_employee + 앱 계정 권한 회수(04_privileges.sql)", "거부 3건, pms 직접 INSERT → 권한 오류"),
    ("BR-16", "시나리오 A", "변경요청은 예정·진행 중 프로젝트에만, 요청번호 자동 채번", "trg_change_request_bi", "거부"),
    ("BR-17", "시나리오 A", "요청한 담당자는 해당 프로젝트 발주처 소속", "trg_change_request_bi", "거부"),
    ("BR-18", "시나리오 A", "변경요청 접수와 검토안 작성은 해당 프로젝트 PM 만", "trg_change_request_bi, sp_validate_change_review", "거부"),
    ("BR-19", "시나리오 A", "결정·동의·반영은 최신 차수 검토안에만 (승인 후 변경은 새 차수로 재검토)", "sp_validate_change_review, trg_change_history_bi, sp_apply_change", "거부"),
    ("BR-20", "시나리오 A", "결정이 난 검토안의 제안 내용(종료예정일·금액·의견)은 수정 불가", "trg_change_review_bu", "거부"),
    ("BR-21", "시나리오 A", "내부 승인·반려는 경영진만", "sp_validate_change_review", "거부"),
    ("BR-22", "시나리오 A", "고객 동의는 내부 승인 후에만, 동의 담당자는 해당 발주처 소속", "sp_validate_change_review", "거부"),
    ("BR-23", "시나리오 A", "승인 + 동의된 검토안만 반영, 중복 반영 금지, 변경 전후 값 이력 보존, 새 종료예정일보다 늦게 끝나는 투입이 있으면 거부",
     "trg_change_history_bi, sp_apply_change, uk_history_review", "거부"),
    ("BR-24", "시나리오 B", "역량개선계획 대상은 근거 프로젝트(종료)에 참여한 개발자", "trg_development_plan_bi", "거부"),
    ("BR-25", "시나리오 B", "계획은 교육 담당자로 지정된 경영관리 직원만 수립", "trg_development_plan_bi, chk_staff_trainer", "거부"),
    ("BR-26", "시나리오 B", "신청 일정은 계획에서 추천한 교육과정의 일정", "trg_enrollment_bi", "거부"),
    ("BR-27", "시나리오 B", "같은 직원은 같은 일정에 중복 신청 불가 (취소 건 제외)", "trg_enrollment_bi", "거부"),
    ("BR-28", "시나리오 B", "일정별 정원 초과 신청 불가 (일정 행 잠금으로 동시 신청에도 정확)", "trg_enrollment_bi", "거부"),
    ("BR-29", "시나리오 B", "신청은 교육 시작 전에만, 수료·미수료 기록은 교육 종료 후 신청 건에만", "trg_enrollment_bi/bu", "거부"),
]
for b in BRS:
    row(ws, r, list(b), center_cols=(0, 1), height=13 * max(lines_of(b[2], 56), lines_of(b[3], 42)) + 4); r += 1
r += 1

section("3. 문제 설명에 없어 팀이 정한 가정 (설계에 반영)")
header(ws, r, ["번호", "확인할 내용", "결정 내용", "관련 요구사항", "반영 위치"]); r += 1
qa = openpyxl.load_workbook(ROOT / "docs" / "01-2_팀확인사항_추적표.xlsx")["팀 확인 필요 사항"]
WHERE = {1: "trg_employee_bi, sp_next_seq", 2: "BR-01, sp_register_employee", 3: "user_account.auth_role", 4: "v_employee 마스킹",
         5: "project.client_id (FK 1개)", 6: "BR-05 participation_rate", 7: "BR-04 (기간 분할 재투입)", 8: "developer.career_start_date",
         9: "developer.skill_grade ENUM", 10: "eval_detail.score CHECK 1~5", 11: "BR-09", 12: "customer_eval.access_token", 13: "v_project_eval_summary 가중 환산",
         14: "trg_project_bi", 15: "job_role.min_grade, BR-07", 16: "BR-06", 17: "BR-15 grade_history", 18: "client, client_contact",
         19: "eval_item (is_active)", 20: "eval_type_weight", 21: "앱 권한 (executive_required)", 22: "project.end_date / actual_end_date / status",
         23: "평가 할 일 화면 (PM 에 두 목록)", 24: "BR-13 (PM 경력자 누구나, 1건)"}
n = 0
for rr in range(5, qa.max_row + 1):
    if not qa[f"A{rr}"].value:
        continue
    no = int(qa[f"A{rr}"].value)
    vals = [no, qa[f"B{rr}"].value, qa[f"D{rr}"].value, qa[f"C{rr}"].value, WHERE.get(no, "")]
    row(ws, r, vals, center_cols=(0, 3), height=13 * max(lines_of(vals[1], 24), lines_of(vals[2], 56)) + 4); r += 1; n += 1
assert n == 24, n
ws.freeze_panes = "B5"

wb.save(OUT)
print(f"saved {OUT} | 테이블 {len(TABLES)} 컬럼 {len(COLS)} FK {len(FKS)} 객체 {len(VIEWS) + len(TRIGGERS) + len(ROUTINES)} BR {len(BRS)} 가정 {n}")
