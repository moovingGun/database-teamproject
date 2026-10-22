"""
ERD 이미지 생성 (Information Engineering 표기) — 실제 DB(information_schema)에서 자동 생성
  .venv/bin/python scripts/gen_erd.py     →  docs/erd/*.png, *.svg   (graphviz 의 dot 필요: brew install graphviz)

표기 규칙 (관계선 양 끝)
  부모 쪽:  ┼┼ 정확히 1 (FK NOT NULL)   ┼○ 0 또는 1 (FK NULL 허용)
  자식 쪽:  ○< 0 이상 (일반 1:N)          ┼○ 0 또는 1 (FK 가 PK/UK = 서브타입·1:1)
  → 모든 1:N 의 1측이 '0 이상'(Partial) 이므로 Total:Total 관계가 없음을 그림으로 확인할 수 있다.
슈퍼타입-서브타입 (IE 서브타입 기호)
  슈퍼타입 ── ⊗‖ ──< 서브타입들     ⊗ 배타적(Exclusive)  ‖ 완전(Complete, 전체 참여)  옆 글자 = 판별자
"""
import os
import subprocess
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "erd"
DB = os.environ.get("DB_NAME", "si_pms")
FONT = "Apple SD Gothic Neo"

AREAS = [  # (키, 제목, 색, 테이블)
    ("hr", "직원 · 계정 · 기술", "#e8eefc", ["employee", "developer", "staff", "user_account", "skill", "employee_skill", "grade_history"]),
    ("prj", "발주처 · 프로젝트 · 투입", "#e7f6ec", ["client", "client_contact", "project", "project_skill", "job_role", "assignment"]),
    ("eval", "프로젝트 평가", "#fdf1e3", ["evaluation", "customer_eval", "pm_eval", "peer_eval", "eval_item", "eval_detail", "eval_type_weight"]),
    ("chg", "시나리오 A · 변경요청 승인", "#f3e8fd", ["change_request", "change_review", "change_history"]),
    ("edu", "시나리오 B · 역량개선 · 교육", "#fde8ee", ["training_course", "training_session", "development_plan", "training_enrollment"]),
]
SYSTEM = ["seq_counter"]
SUBTYPES = {  # 슈퍼타입: (판별자, 서브타입) — 서브타입 PK=FK 관계선 대신 IE 서브타입 기호로 그린다
    "employee": ("emp_type", ["developer", "staff"]),
    "evaluation": ("eval_type", ["customer_eval", "pm_eval", "peer_eval"]),
}

conn = pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
                       user=os.environ.get("DB_USER", "pms"), password=os.environ.get("DB_PASSWORD", "pms1234"),
                       database="information_schema", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT table_name t, table_comment c FROM tables WHERE table_schema=%s AND table_type='BASE TABLE'", (DB,))
TCOM = {r["t"]: r["c"].split(" (")[0] for r in cur.fetchall()}
cur.execute("""SELECT table_name t, column_name c, column_type ty, is_nullable n, column_key k FROM columns
               WHERE table_schema=%s ORDER BY table_name, ordinal_position""", (DB,))
COLS = {}
for r in cur.fetchall():
    COLS.setdefault(r["t"], []).append(r)
cur.execute("""SELECT k.table_name t, k.column_name c, k.referenced_table_name rt, k.constraint_name cn
               FROM key_column_usage k WHERE k.table_schema=%s AND k.referenced_table_name IS NOT NULL""", (DB,))
FKS = cur.fetchall()
cur.execute("""SELECT table_name t, GROUP_CONCAT(column_name) cols, index_name i, non_unique nu FROM statistics
               WHERE table_schema=%s GROUP BY table_name, index_name, non_unique""", (DB,))
UNIQ = {(r["t"], r["cols"]) for r in cur.fetchall() if not r["nu"]}
assert set(TCOM) == {t for _, _, _, ts in AREAS for t in ts} | set(SYSTEM), set(TCOM) ^ ({t for *_, ts in AREAS for t in ts} | set(SYSTEM))
AREA_OF = {t: a for a, _, _, ts in AREAS for t in ts}
FK_COLS = {(f["t"], f["c"]) for f in FKS}
SUB_FKS = [f for f in FKS if f["t"] in SUBTYPES.get(f["rt"], ("", []))[1]
           and any(c["c"] == f["c"] and c["k"] == "PRI" for c in COLS[f["t"]])]
FKS = [f for f in FKS if f not in SUB_FKS]
assert len(SUB_FKS) == sum(len(s) for _, s in SUBTYPES.values()), SUB_FKS


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def node(t, detail, color, ghost=False):
    head = f'<TR><TD BGCOLOR="{color}" ALIGN="LEFT"><B>{esc(t)}</B>  <FONT POINT-SIZE="10" COLOR="#555555">{esc(TCOM[t])}</FONT></TD></TR>'
    rows = ""
    if detail:
        for c in COLS[t]:
            mark = ("PK" if c["k"] == "PRI" else "") + (" FK" if (t, c["c"]) in FK_COLS else "")
            if c["k"] == "UNI" and "PK" not in mark:
                mark = (mark + " UK").strip()
            ty = "enum" if c["ty"].startswith("enum(") else c["ty"]
            ty = ty if len(ty) < 22 else ty[:20] + "…)"
            name = f'<B>{esc(c["c"])}</B>' if c["k"] == "PRI" else esc(c["c"])
            nn = "" if c["n"] == "YES" else " ●"
            rows += (f'<TR><TD ALIGN="LEFT"><FONT POINT-SIZE="9" COLOR="#2b4fd6">{mark.strip():<6}</FONT> {name}'
                     f'<FONT POINT-SIZE="9" COLOR="#777777">  {esc(ty)}{nn}</FONT></TD></TR>')
    style = ' STYLE="dashed"' if ghost else ""
    return (f'"{t}" [label=<<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="4" COLOR="#8a94a6"{style}>'
            f'{head}{rows}</TABLE>>];')


def edge(f):
    child_nullable = next(c["n"] for c in COLS[f["t"]] if c["c"] == f["c"]) == "YES"
    child_unique = (f["t"], f["c"]) in UNIQ or any(c["c"] == f["c"] and c["k"] == "PRI" and
                    sum(1 for x in COLS[f["t"]] if x["k"] == "PRI") == 1 for c in COLS[f["t"]])
    parent_end = "teeodot" if child_nullable else "teetee"
    child_end = "teeodot" if child_unique else "crowodot"
    return (f'"{f["rt"]}" -> "{f["t"]}" [dir=both, arrowtail={parent_end}, arrowhead={child_end}, '
            f'color="#6b7280", penwidth=1.1, arrowsize=0.9];')


def cat_symbol(lr):
    """IE 서브타입 기호 (⊗ 배타 + 이중선 완전) HTML 라벨과 선 연결 포트"""
    circle = '<TD PORT="in"><FONT POINT-SIZE="20">⊗</FONT></TD>'
    if lr:  # 이중선은 서브타입 쪽(오른쪽)에 세로로
        bar = '<TD BORDER="1" SIDES="R" WIDTH="3" HEIGHT="26" FIXEDSIZE="TRUE"{}></TD>'.format
        sym = "<TR>" + circle + bar("") + bar(' PORT="out"') + "</TR>"
        tail, head = "out:e", "in:w"
    else:   # 이중선은 서브타입 쪽(아래)에 가로로
        bar = '<TD BORDER="1" SIDES="B" WIDTH="26" HEIGHT="3" FIXEDSIZE="TRUE"{}></TD>'.format
        sym = "<TR>" + circle + "</TR><TR>" + bar("") + "</TR><TR>" + bar(' PORT="out"') + "</TR>"
        tail, head = "out:s", "in:n"
    return f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0" COLOR="#6b7280">{sym}</TABLE>>', tail, head


def category(sup, lr):
    """IE 서브타입 기호: 슈퍼타입 ─ ⊗(배타) + 이중선(완전) ─ 각 서브타입, 기호 옆에 판별자"""
    disc, subs = SUBTYPES[sup]
    label, tail, head = cat_symbol(lr)
    cat = f"cat_{sup}"
    out = [f'"{cat}" [margin=0, width=0, height=0, label={label}, '
           f'xlabel=<<FONT POINT-SIZE="9" COLOR="#b45309">{disc}</FONT>>];',
           f'"{sup}" -> "{cat}" [dir=none, headport="{head}", color="#6b7280", penwidth=1.1];']
    out += [f'"{cat}" -> "{s}" [dir=none, tailport="{tail}", color="#6b7280", penwidth=1.1];' for s in subs]
    return out


def render(name, body, rankdir="LR", extra=""):
    dot = f'''digraph "{name}" {{
  graph [rankdir={rankdir}, fontname="{FONT}", fontsize=13, bgcolor="white", nodesep=0.35, pad=0.3, splines=true, newrank=true{extra or ", ranksep=0.9"}];
  node  [shape=plaintext, fontname="{FONT}", fontsize=11];
  edge  [fontname="{FONT}", fontsize=9];
{body}
}}'''
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.dot").write_text(dot, encoding="utf-8")
    for fmt in ("svg", "png"):
        args = ["dot", f"-T{fmt}", "-o", str(OUT / f"{name}.{fmt}")]
        if fmt == "png":
            args.insert(1, "-Gdpi=144")
        subprocess.run(args, input=dot.encode(), check=True)
    print("wrote", OUT / f"{name}.png")


legend = f'''  subgraph cluster_legend {{ label="IE 표기"; fontsize=11; color="#d1d5db"; style=rounded;
    lg_a [shape=plaintext, label=""]; lg_b [shape=plaintext, label="1 : 0..N  (FK NOT NULL)"];
    lg_c [shape=plaintext, label=""]; lg_d [shape=plaintext, label="1 : 0..1  (1:1)"];
    lg_e [shape=plaintext, label=""]; lg_f [shape=plaintext, label="0..1 : 0..N  (FK NULL 허용)"];
    lg_g [shape=plaintext, label={cat_symbol(lr=False)[0]}]; lg_h [shape=plaintext, label="서브타입: ⊗ 배타적 · 이중선 완전(전체) · 주황 글자 판별자"];
    lg_a -> lg_b [dir=both, arrowtail=teetee, arrowhead=crowodot, color="#6b7280"];
    lg_c -> lg_d [dir=both, arrowtail=teetee, arrowhead=teeodot, color="#6b7280"];
    lg_e -> lg_f [dir=both, arrowtail=teeodot, arrowhead=crowodot, color="#6b7280"];
    lg_g -> lg_h [style=invis];
  }}'''
SUB_NOTE = "  ·  ⊗ = 배타적 서브타입, 이중선 = 완전(전체), 주황 글자 = 판별자"

# 1) 전체 개요: 영역별 묶음, 속성 없이
body = []
for key, title, color, ts in AREAS:
    body.append(f'  subgraph cluster_{key} {{ label="{title}"; style="rounded,filled"; fillcolor="{color}55"; color="{color}"; fontsize=14;')
    body += ["    " + node(t, False, color) for t in ts]
    body += ["    " + x for sup in SUBTYPES if sup in ts for x in category(sup, lr=False)]
    body.append("  }")
body += ["  " + edge(f) for f in FKS]
# 배치용 보이지 않는 연결: 시나리오 A·B 영역을 기본 영역 아래 줄에 놓아 가로 길이를 줄인다 (관계 아님)
body += ['  "grade_history" -> "change_request" [style=invis, weight=4];',
         '  "employee_skill" -> "training_course" [style=invis, weight=4];',
         '  "assignment" -> "evaluation" [style=invis, weight=4];',
         '  "assignment" -> "eval_type_weight" [style=invis];',
         '  "assignment" -> "eval_item" [style=invis];',
         '  "client_contact" -> "lg_a" [style=invis];']
body.append(legend)
render("00_overview", "\n".join(body), rankdir="TB", extra=", ranksep=0.65")

# 2) 영역별 상세: 해당 영역 테이블은 속성 포함, 다른 영역 참조 테이블은 점선 상자
for key, title, color, ts in AREAS:
    related = [f for f in FKS if f["t"] in ts or f["rt"] in ts]
    ghosts = sorted({x for f in related for x in (f["t"], f["rt"]) if x not in ts})
    sups = [s for s in SUBTYPES if s in ts]
    note = SUB_NOTE if sups else ""
    body = [f'  label="{title}  (실선: 이 영역 · 점선: 다른 영역){note}"; labelloc=t; fontsize=15;']
    body += ["  " + node(t, True, color) for t in ts]
    body += ["  " + node(t, False, dict((a, c) for a, _, c, _ in AREAS)[AREA_OF[t]], ghost=True) for t in ghosts]
    body += ["  " + edge(f) for f in related]
    body += ["  " + x for sup in sups for x in category(sup, lr=True)]
    idx = [a for a, *_ in AREAS].index(key) + 1
    render(f"{idx:02d}_{key}", "\n".join(body))
