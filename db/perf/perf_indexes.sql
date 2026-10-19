-- =====================================================================
--  성능 향상 기법 (대표 시나리오 S2: 특정 시점 투입 현황 - 기간 범위 검색)
--  실험 스크립트: scripts/perf_benchmark.py  /  결과·분석: docs/06_성능향상기법_실험.md
-- ---------------------------------------------------------------------
--  문제   WHERE a.start_date <= :d AND a.end_date >= :d  →  보조 인덱스가 없으면 assignment 풀스캔(type=ALL)
--  기법 B 복합 인덱스 (end_date, start_date)
--         end_date >= :d 범위 스캔으로 이미 종료된 투입을 배제, start_date 는 인덱스 조건(ICP)으로 필터
--         → 최근 시점(선택도 높음)에서는 3.7배 개선, 과거 시점(절반 이상 매칭)에서는 옵티마이저가 풀스캔 선택
--  기법 C 커버링 인덱스 (end_date, start_date, project_id, emp_id, role_id, participation_rate)   ★ 채택
--         조인 키·출력 컬럼까지 포함 → 테이블 접근 없이 인덱스만 스캔(Using index)
--         → 최근 4.0배, 중간 2.3배, 과거 1.4배 개선 (모든 기준일에서 인덱스 사용)
--  적용   01_schema.sql 의 assignment 테이블에 idx_assignment_period 로 포함되어 있음 (아래는 비교 재현용)
-- =====================================================================
USE si_pms;

-- (비교) 인덱스 제거 → 풀스캔 실행계획
-- ALTER TABLE assignment DROP INDEX idx_assignment_period;
-- (적용) 커버링 인덱스
-- ALTER TABLE assignment ADD INDEX idx_assignment_period (end_date, start_date, project_id, emp_id, role_id, participation_rate);

EXPLAIN
SELECT p.project_code, p.project_name, c.client_name, e.emp_no, e.emp_name, d.skill_grade, r.role_name,
       a.start_date, a.end_date, a.participation_rate
  FROM assignment a
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id  = p.client_id
  JOIN employee  e ON e.emp_id     = a.emp_id
  JOIN developer d ON d.emp_id     = a.emp_id
  JOIN job_role  r ON r.role_id    = a.role_id
 WHERE a.start_date <= '2025-06-01' AND a.end_date >= '2025-06-01';
