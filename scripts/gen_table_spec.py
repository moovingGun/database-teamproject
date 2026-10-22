"""
테이블 정의서 자동 생성: information_schema 의 테이블/컬럼 COMMENT 를 읽어 docs/03_테이블정의서.md 작성
  .venv/bin/python scripts/gen_table_spec.py
"""
import os
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "03_테이블정의서.md"
DB = os.environ.get("DB_NAME", "si_pms")
# 트리거 목록(information_schema.TRIGGERS)은 TRIGGER 권한이 있어야 보이므로, 권한이 좁혀진 앱 계정(pms) 대신 root 로 읽는다
conn = pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
                       user=os.environ.get("DB_ADMIN_USER", "root"), password=os.environ.get("DB_ADMIN_PASSWORD", "root1234"),
                       database="information_schema", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

GROUPS = [
    ("발주처", ["client", "client_contact"]),
    ("직원 (슈퍼타입-서브타입)", ["employee", "developer", "staff", "user_account"]),
    ("기술", ["skill", "employee_skill"]),
    ("프로젝트 · 투입", ["project", "project_skill", "job_role", "assignment"]),
    ("프로젝트 평가 (슈퍼타입-서브타입)", ["evaluation", "customer_eval", "pm_eval", "peer_eval", "eval_item", "eval_detail", "eval_type_weight"]),
    ("이력 · 시스템", ["grade_history", "seq_counter"]),
    ("조별 특화 시나리오 A: 고객사 변경요청 및 승인", ["change_request", "change_review", "change_history"]),
    ("조별 특화 시나리오 B: 역량 개선 및 교육 이수", ["training_course", "training_session", "development_plan", "training_enrollment"]),
]

cur.execute("SELECT table_name, table_comment FROM tables WHERE table_schema=%s AND table_type='BASE TABLE'", (DB,))
tcomment = {r["TABLE_NAME"]: r["TABLE_COMMENT"] for r in cur.fetchall()}
cur.execute("""SELECT table_name, column_name, column_type, is_nullable, column_key, column_default, extra, column_comment
                 FROM columns WHERE table_schema=%s ORDER BY table_name, ordinal_position""", (DB,))
cols = {}
for r in cur.fetchall():
    cols.setdefault(r["TABLE_NAME"], []).append(r)
cur.execute("""SELECT table_name, column_name, referenced_table_name, referenced_column_name
                 FROM key_column_usage WHERE table_schema=%s AND referenced_table_name IS NOT NULL""", (DB,))
fks = {}
for r in cur.fetchall():
    fks[(r["TABLE_NAME"], r["COLUMN_NAME"])] = f"{r['REFERENCED_TABLE_NAME']}.{r['REFERENCED_COLUMN_NAME']}"
cur.execute("""SELECT table_name, index_name, non_unique, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS cols
                 FROM statistics WHERE table_schema=%s GROUP BY table_name, index_name, non_unique""", (DB,))
idx = {}
for r in cur.fetchall():
    idx.setdefault(r["TABLE_NAME"], []).append(r)
cur.execute("SELECT table_name, constraint_name FROM table_constraints WHERE table_schema=%s AND constraint_type='CHECK'", (DB,))
checks = {}
for r in cur.fetchall():
    checks.setdefault(r["TABLE_NAME"], []).append(r["CONSTRAINT_NAME"])
cur.execute("SELECT table_name, view_definition FROM views WHERE table_schema=%s ORDER BY table_name", (DB,))
views = cur.fetchall()
cur.execute("SELECT trigger_name, event_manipulation, event_object_table, action_timing FROM triggers WHERE trigger_schema=%s ORDER BY event_object_table, action_timing", (DB,))
triggers = cur.fetchall()
cur.execute("SELECT routine_name, routine_type FROM routines WHERE routine_schema=%s ORDER BY routine_name", (DB,))
routines = cur.fetchall()

lines = ["# 데이터베이스 정의서 (테이블 정의서)", "",
         "> `scripts/gen_table_spec.py` 가 실제 DB(information_schema) 에서 자동 생성. DDL 원본: `db/init/01_schema.sql`",
         "", f"총 {len(tcomment)}개 테이블 · {len(views)}개 뷰 · {len(triggers)}개 트리거 · {len(routines)}개 프로시저", ""]
lines += ["## 테이블 목록", "", "| # | 테이블 | 설명 | 컬럼 수 |", "|---|---|---|---:|"]
n = 0
for g, ts in GROUPS:
    for t in ts:
        n += 1
        lines.append(f"| {n} | `{t}` | {tcomment.get(t,'')} | {len(cols.get(t, []))} |")
lines.append("")
for g, ts in GROUPS:
    lines += [f"## {g}", ""]
    for t in ts:
        lines += [f"### `{t}` — {tcomment.get(t, '')}", "",
                  "| 컬럼 | 타입 | NULL | 키 | 기본값 | 설명 |", "|---|---|:---:|:---:|---|---|"]
        for c in cols.get(t, []):
            key = {"PRI": "PK", "UNI": "UK", "MUL": "FK/IDX"}.get(c["COLUMN_KEY"], "")
            fk = fks.get((t, c["COLUMN_NAME"]))
            if fk:
                key = (key + " FK→" + fk).strip() if "FK" not in key else "FK→" + fk
                if c["COLUMN_KEY"] == "PRI":
                    key = "PK, FK→" + fk
            default = c["COLUMN_DEFAULT"] if c["COLUMN_DEFAULT"] is not None else ""
            extra = (" " + c["EXTRA"]) if c["EXTRA"] and "DEFAULT_GENERATED" not in c["EXTRA"] else ""
            lines.append(f"| `{c['COLUMN_NAME']}` | {c['COLUMN_TYPE']} | {'Y' if c['IS_NULLABLE']=='YES' else 'N'} | {key} | {default}{extra} | {c['COLUMN_COMMENT']} |")
        extras = []
        for i in idx.get(t, []):
            if i["INDEX_NAME"] != "PRIMARY":
                extras.append(f"{'UNIQUE ' if not i['NON_UNIQUE'] else ''}INDEX `{i['INDEX_NAME']}` ({i['cols']})")
        for ck in checks.get(t, []):
            extras.append(f"CHECK `{ck}`")
        if extras:
            lines += ["", "제약/인덱스: " + " · ".join(extras)]
        lines.append("")
lines += ["## 뷰", "", "| 뷰 | 용도 |", "|---|---|",
          "| `v_employee` | 직원 슈퍼타입 + 개발자/지원직 서브타입 + 계정을 통합 조회, 주민번호 마스킹, 총 경력(개월)과 경력 기준 권고 등급 산출 |",
          "| `v_assignment_detail` | 투입 ⋈ 프로젝트 ⋈ 발주처 ⋈ 직원 ⋈ 직무 (경력 이력 / 투입 현황 공통 조회) |",
          "| `v_eval_score` | 평가별 항목 가중 평균 점수 (업무수행/커뮤니케이션 점수 포함) |",
          "| `v_project_eval_summary` | 프로젝트·피평가자별 고객/PM/동료 평균 → 유형 가중치(eval_type_weight) 적용 종합점수 → 인센티브 등급(S/A/B/C) |",
          "| `v_change_request` | [시나리오 A] 변경요청 ⋈ 최신 검토안 ⋈ 결정자 ⋈ 동의 담당자 ⋈ 적용이력 (데모 S7) |",
          "| `v_training_plan` | [시나리오 B] 역량개선계획 ⋈ 평가 종합 ⋈ 추천 과정 ⋈ 최근 신청, 이수 상태는 신청 이력에서 계산 (데모 S8) |", ""]
lines += ["## 트리거 · 프로시저", "", "| 객체 | 유형 | 대상 | 역할 |", "|---|---|---|---|"]
role = {"trg_employee_bi": "사번 자동 채번 (BR-02)", "trg_project_bi": "프로젝트번호 자동 채번 (BR-02)",
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
for t in triggers:
    lines.append(f"| `{t['TRIGGER_NAME']}` | {t['ACTION_TIMING']} {t['EVENT_MANIPULATION']} 트리거 | `{t['EVENT_OBJECT_TABLE']}` | {role.get(t['TRIGGER_NAME'], '')} |")
for r in routines:
    desc = {"sp_next_seq": "연도별 일련번호 채번 (행 잠금)", "sp_validate_assignment": "투입 규칙 검증 공통 로직",
            "sp_validate_change_review": "검토안 등록·결정·동의 공통 검증", "sp_sync_change_status": "최신 검토안 기준 요청 상태 계산",
            "sp_apply_change": "변경 반영: 검증 → 이력 기록 → 종료예정일·계약금액 변경",
            "sp_register_employee": "직원 + 서브타입 한 번에 등록, 실패 시 직원 행 제거 (BR-30 전체 참여)"}.get(r["ROUTINE_NAME"], "")
    lines.append(f"| `{r['ROUTINE_NAME']}` | {r['ROUTINE_TYPE']} | - | {desc} |")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {OUT} ({len(tcomment)} tables)")
