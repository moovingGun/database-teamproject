"""
성능 향상 기법 실험: 대표 시나리오 S2 (특정 시점 투입 현황 - 기간 범위 검색)

  .venv/bin/python scripts/perf_benchmark.py [--rows 1000000] [--skip-load] [--keep]

* 운영 DB(si_pms)와 동일한 스키마를 si_pms_perf 에 생성(01_schema.sql 재사용, 트리거는 제외)하고
  대량 합성 데이터(기본 100만 건 투입)를 적재한 뒤, 동일 질의를
    A) 인덱스 없음  B) 복합 인덱스(end_date, start_date)  C) 커버링 인덱스
  세 조건에서 각각 N회 실행해 중앙값 응답시간과 EXPLAIN 결과를 비교한다.
* 결과는 표준출력 + docs/06_perf_results.md 에 Markdown 표로 기록
"""
import argparse
import os
import random
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
PERF_DB = "si_pms_perf"
CFG = dict(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
           user=os.environ.get("DB_USER", "pms"), password=os.environ.get("DB_PASSWORD", "pms1234"),
           charset="utf8mb4", autocommit=False)

QUERY = """
SELECT p.project_code, p.project_name, c.client_name, e.emp_no, e.emp_name, d.skill_grade, r.role_name,
       a.start_date, a.end_date, a.participation_rate
  FROM assignment a
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id  = p.client_id
  JOIN employee  e ON e.emp_id     = a.emp_id
  JOIN developer d ON d.emp_id     = a.emp_id
  JOIN job_role  r ON r.role_id    = a.role_id
 WHERE a.start_date <= %s AND a.end_date >= %s"""
COUNT_QUERY = "SELECT COUNT(*) FROM assignment a WHERE a.start_date <= %s AND a.end_date >= %s"

CASES = [
    ("A. 인덱스 없음", []),
    ("B. 복합 인덱스 (end_date, start_date)", ["CREATE INDEX idx_assignment_period ON assignment (end_date, start_date)"]),
    ("C. 커버링 인덱스 (+project_id, emp_id, role_id, participation_rate)",
     ["CREATE INDEX idx_assignment_period_cover ON assignment (end_date, start_date, project_id, emp_id, role_id, participation_rate)"]),
]
DROPS = ["DROP INDEX idx_assignment_period ON assignment", "DROP INDEX idx_assignment_period_cover ON assignment"]


def connect(db=None):
    return pymysql.connect(database=db, **CFG)


def load(rows):
    random.seed(7)
    conn = connect()
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {PERF_DB}")
    cur.execute(f"CREATE DATABASE {PERF_DB} DEFAULT CHARACTER SET utf8mb4")
    conn.commit()
    conn.close()
    conn = connect(PERF_DB)
    cur = conn.cursor()
    ddl = (ROOT / "db/init/01_schema.sql").read_text(encoding="utf-8").replace("si_pms", PERF_DB)
    ddl = "\n".join(l for l in ddl.splitlines() if not l.strip().startswith("--"))   # 주석 제거 후 ; 분리
    for stmt in ddl.split(";"):
        if stmt.strip():
            cur.execute(stmt)
    conn.commit()
    t0 = time.time()
    n_client, n_dev, n_prj = 200, 5000, max(2000, rows // 20)
    cur.executemany("INSERT INTO client (client_id, client_name, business_reg_no) VALUES (%s,%s,%s)",
                    [(i, f"고객사{i}", f"{i:03d}-00-{i:05d}") for i in range(1, n_client + 1)])
    cur.executemany("INSERT INTO job_role (role_id, role_code, role_name, min_grade, sort_order) VALUES (%s,%s,%s,%s,%s)",
                    [(1, "PM", "PM", "고급", 1), (2, "PL", "PL", "중급", 2), (3, "ANALYST", "분석자", "중급", 3),
                     (4, "DESIGNER", "설계자", "중급", 4), (5, "PROGRAMMER", "프로그래머", "초급", 5), (6, "TESTER", "테스터", "초급", 6)])
    grades = ["초급", "중급", "고급", "특급"]
    for s in range(1, n_dev + 1, 1000):
        batch = range(s, min(s + 1000, n_dev + 1))
        cur.executemany("INSERT INTO employee (emp_id, emp_no, emp_name, resident_reg_no, education_level, hire_date, emp_type) VALUES (%s,%s,%s,%s,'학사','2010-01-01','DEV')",
                        [(i, f"E{i:06d}", f"직원{i}", f"{i:06d}-{i % 10}{i:06d}") for i in batch])
        cur.executemany("INSERT INTO developer (emp_id, skill_grade, career_start_date) VALUES (%s,%s,'2010-01-01')",
                        [(i, random.choice(grades)) for i in batch])
    conn.commit()
    base = date(2006, 1, 1)
    prj = []
    for i in range(1, n_prj + 1):
        s = base + timedelta(days=random.randint(0, 365 * 20))
        prj.append((i, f"P{i:06d}", f"프로젝트{i}", random.randint(1, n_client), s, s + timedelta(days=random.randint(90, 540)), "COMPLETED"))
    for s in range(0, n_prj, 5000):
        cur.executemany("INSERT INTO project (project_id, project_code, project_name, client_id, start_date, end_date, status) VALUES (%s,%s,%s,%s,%s,%s,%s)", prj[s:s + 5000])
    conn.commit()
    batch, done = [], 0
    for i in range(1, rows + 1):
        p = prj[random.randrange(n_prj)]
        ps, pe = p[4], p[5]
        s = ps + timedelta(days=random.randint(0, max(0, (pe - ps).days // 2)))
        e = s + timedelta(days=random.randint(30, max(30, (pe - s).days)))
        batch.append((i, p[0], random.randint(1, n_dev), random.randint(1, 6), s, min(e, pe), random.choice([50, 100, 100, 100])))
        if len(batch) == 10000:
            cur.executemany("INSERT INTO assignment (assignment_id, project_id, emp_id, role_id, start_date, end_date, participation_rate) VALUES (%s,%s,%s,%s,%s,%s,%s)", batch)
            conn.commit(); done += len(batch); batch = []
            print(f"\r  loading assignment {done:,}/{rows:,}", end="", flush=True)
    if batch:
        cur.executemany("INSERT INTO assignment (assignment_id, project_id, emp_id, role_id, start_date, end_date, participation_rate) VALUES (%s,%s,%s,%s,%s,%s,%s)", batch)
        conn.commit()
    cur.execute("ANALYZE TABLE assignment")
    cur.fetchall()
    print(f"\n  loaded in {time.time() - t0:.1f}s")
    conn.close()


def explain(cur, sql, params):
    cur.execute("EXPLAIN " + sql, params)
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        r = dict(zip(cols, row))
        if r["table"] == "a":
            return f"type={r['type']}, key={r['key']}, rows={r['rows']:,}, extra={r['Extra']}"
    return "-"


def bench(dates, runs):
    conn = connect(PERF_DB)
    cur = conn.cursor()
    for d in DROPS:
        try:
            cur.execute(d)
        except pymysql.MySQLError:
            pass
    cur.execute("SELECT COUNT(*) FROM assignment"); total = cur.fetchone()[0]
    results = []
    for name, ddls in CASES:
        for d in DROPS:
            try:
                cur.execute(d)
            except pymysql.MySQLError:
                pass
        t0 = time.time()
        for ddl in ddls:
            cur.execute(ddl)
        build = time.time() - t0
        conn.commit()
        print(f"\n== {name} (index build {build:.1f}s)")
        for d in dates:
            cur.execute(COUNT_QUERY, (d, d)); hit = cur.fetchone()[0]
            cur.execute(QUERY, (d, d)); cur.fetchall()           # warm-up
            times = []
            for _ in range(runs):
                t = time.perf_counter(); cur.execute(QUERY, (d, d)); cur.fetchall(); times.append((time.perf_counter() - t) * 1000)
            ex = explain(cur, QUERY, (d, d))
            med = statistics.median(times)
            results.append((name, d, hit, med, min(times), ex))
            print(f"  as_of={d}  hits={hit:>8,}  median={med:8.1f} ms  min={min(times):8.1f} ms  | {ex}")
    conn.close()
    return total, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=1_000_000)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--skip-load", action="store_true")
    ap.add_argument("--keep", action="store_true", help="실험 DB 유지")
    a = ap.parse_args()
    if not a.skip_load:
        print(f"[1/2] {PERF_DB} 생성 및 합성 데이터 적재 (assignment {a.rows:,}건)")
        load(a.rows)
    dates = ["2026-06-01", "2020-06-01", "2012-06-01"]   # 최근(선택도 높음) / 중간 / 과거(선택도 낮음)
    print("[2/2] 벤치마크")
    total, results = bench(dates, a.runs)
    out = ROOT / "docs" / "06_perf_results.md"
    lines = [f"# 성능 실험 원시 결과 (자동 생성)", "",
             f"* 데이터: assignment {total:,}건 (si_pms_perf, 트리거 제외 동일 스키마)", f"* 실행: 각 조건·기준일별 warm-up 1회 후 {a.runs}회 측정, 중앙값(ms)",
             f"* 환경: MySQL 8.0 (Docker), PyMySQL, 기준일 3종(최근/중간/과거)", "",
             "| 조건 | 기준일 | 결과 건수 | 중앙값(ms) | 최소(ms) | EXPLAIN (assignment) |", "|---|---|---:|---:|---:|---|"]
    for name, d, hit, med, mn, ex in results:
        lines.append(f"| {name} | {d} | {hit:,} | {med:.1f} | {mn:.1f} | {ex} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {out}")
    if not a.keep:
        conn = connect(); cur = conn.cursor(); cur.execute(f"DROP DATABASE IF EXISTS {PERF_DB}"); conn.commit(); conn.close()
        print(f"dropped {PERF_DB}")


if __name__ == "__main__":
    main()
