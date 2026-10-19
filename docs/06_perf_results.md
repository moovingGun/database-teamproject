# 성능 실험 원시 결과 (자동 생성)

* 데이터: assignment 1,000,000건 (si_pms_perf, 트리거 제외 동일 스키마)
* 실행: 각 조건·기준일별 warm-up 1회 후 5회 측정, 중앙값(ms)
* 환경: MySQL 8.0 (Docker), PyMySQL, 기준일 3종(최근/중간/과거)

| 조건 | 기준일 | 결과 건수 | 중앙값(ms) | 최소(ms) | EXPLAIN (assignment) |
|---|---|---:|---:|---:|---|
| A. 인덱스 없음 | 2026-06-01 | 9,720 | 160.8 | 160.6 | type=ALL, key=None, rows=997,194, extra=Using where |
| A. 인덱스 없음 | 2020-06-01 | 18,483 | 178.0 | 176.3 | type=ALL, key=None, rows=997,194, extra=Using where |
| A. 인덱스 없음 | 2012-06-01 | 18,776 | 184.7 | 180.4 | type=ALL, key=None, rows=997,194, extra=Using where |
| B. 복합 인덱스 (end_date, start_date) | 2026-06-01 | 9,720 | 42.9 | 41.8 | type=range, key=idx_assignment_period, rows=18,636, extra=Using index condition |
| B. 복합 인덱스 (end_date, start_date) | 2020-06-01 | 18,483 | 174.6 | 174.4 | type=ALL, key=None, rows=997,194, extra=Using where |
| B. 복합 인덱스 (end_date, start_date) | 2012-06-01 | 18,776 | 184.8 | 180.9 | type=ALL, key=None, rows=997,194, extra=Using where |
| C. 커버링 인덱스 (+project_id, emp_id, role_id, participation_rate) | 2026-06-01 | 9,720 | 40.3 | 40.1 | type=range, key=idx_assignment_period_cover, rows=19,698, extra=Using where; Using index |
| C. 커버링 인덱스 (+project_id, emp_id, role_id, participation_rate) | 2020-06-01 | 18,483 | 78.7 | 78.3 | type=range, key=idx_assignment_period_cover, rows=498,597, extra=Using where; Using index |
| C. 커버링 인덱스 (+project_id, emp_id, role_id, participation_rate) | 2012-06-01 | 18,776 | 129.6 | 128.5 | type=range, key=idx_assignment_period_cover, rows=498,597, extra=Using where; Using index |
