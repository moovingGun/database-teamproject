-- =====================================================================
--  데모 시나리오 질의 (모두 2개 이상 테이블 조인)  -  docs/05_데모시나리오.md 와 동일
--  실행: docker exec -i si_pms_db mysql -uroot -proot1234 --default-character-set=utf8mb4 si_pms < db/demo/demo_scenarios.sql
--  * 시나리오 2 가 대표 시나리오이며 성능 향상 기법(인덱스) 실험 대상 (scripts/perf_benchmark.py)
-- =====================================================================
SET NAMES utf8mb4;
USE si_pms;

-- ---------------------------------------------------------------------
-- [S1] 경영진 대시보드: 현재 진행 중인 프로젝트 수와 프로젝트별 투입 인원·PM·직무 구성
--      project ⋈ client ⋈ assignment ⋈ employee ⋈ job_role   (5개 테이블)
-- ---------------------------------------------------------------------
SELECT '[S1] 진행 중 프로젝트별 현재 투입 현황' AS scenario;
SELECT p.project_code, p.project_name, c.client_name,
       COUNT(a.assignment_id)                                   AS headcount,
       ROUND(IFNULL(SUM(a.participation_rate), 0) / 100, 1)     AS fte,
       MAX(CASE WHEN r.role_code = 'PM' THEN e.emp_name END)    AS pm_name,
       GROUP_CONCAT(CONCAT(r.role_name, ' ', e.emp_name) ORDER BY r.sort_order SEPARATOR ', ') AS members
  FROM project p
  JOIN client c ON c.client_id = p.client_id
  LEFT JOIN assignment a ON a.project_id = p.project_id AND CURDATE() BETWEEN a.start_date AND a.end_date
  LEFT JOIN employee e ON e.emp_id = a.emp_id
  LEFT JOIN job_role r ON r.role_id = a.role_id
 WHERE p.status = 'IN_PROGRESS'
 GROUP BY p.project_id, p.project_code, p.project_name, c.client_name
 ORDER BY p.start_date;

-- ---------------------------------------------------------------------
-- [S2] ★ 대표 시나리오 ★ 과거 특정 시점(예: 2025-06-01)에 누가 어느 프로젝트에 어떤 직무로 투입되어 있었는가
--      assignment ⋈ project ⋈ client ⋈ employee ⋈ developer ⋈ job_role   (6개 테이블)
--      → 투입 기간 범위 검색: idx_assignment_period(end_date, start_date) 인덱스 효과 실험
-- ---------------------------------------------------------------------
SET @as_of := '2025-06-01';
SELECT CONCAT('[S2] ', @as_of, ' 시점 투입 현황') AS scenario;
SELECT p.project_code, p.project_name, c.client_name,
       e.emp_no, e.emp_name, d.skill_grade, r.role_name,
       a.start_date, a.end_date, a.participation_rate
  FROM assignment a
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id  = p.client_id
  JOIN employee  e ON e.emp_id     = a.emp_id
  JOIN developer d ON d.emp_id     = a.emp_id
  JOIN job_role  r ON r.role_id    = a.role_id
 WHERE a.start_date <= @as_of AND a.end_date >= @as_of
 ORDER BY p.project_code, r.sort_order, e.emp_name;

-- ---------------------------------------------------------------------
-- [S3] 개인별 경력관리: 특정 개발자(pm01)의 프로젝트 참여 이력 + 보유 기술 + 총 경력
--      employee ⋈ developer ⋈ assignment ⋈ project ⋈ client ⋈ job_role / employee_skill ⋈ skill
-- ---------------------------------------------------------------------
SELECT '[S3] pm01 의 프로젝트 참여 이력' AS scenario;
SELECT e.emp_no, e.emp_name, d.skill_grade,
       TIMESTAMPDIFF(MONTH, d.career_start_date, CURDATE()) AS career_months,
       p.project_code, p.project_name, c.client_name, r.role_name,
       a.start_date, a.end_date, a.participation_rate, p.status
  FROM user_account ua
  JOIN employee  e ON e.emp_id = ua.emp_id
  JOIN developer d ON d.emp_id = e.emp_id
  JOIN assignment a ON a.emp_id = e.emp_id
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id = p.client_id
  JOIN job_role  r ON r.role_id = a.role_id
 WHERE ua.login_id = 'pm01'
 ORDER BY a.start_date DESC;

SELECT '[S3-b] pm01 의 보유 기술' AS scenario;
SELECT s.category, s.skill_name, es.proficiency, es.years_used, es.last_used_date
  FROM user_account ua
  JOIN employee_skill es ON es.emp_id = ua.emp_id
  JOIN skill s ON s.skill_id = es.skill_id
 WHERE ua.login_id = 'pm01'
 ORDER BY es.proficiency DESC, s.skill_name;

-- ---------------------------------------------------------------------
-- [S4] 프로젝트 종료 후 평가 종합: 피평가자별 고객/PM/동료 평가 평균과 가중 종합점수, 인센티브 등급
--      evaluation ⋈ eval_detail ⋈ eval_item ⋈ eval_type_weight ⋈ employee ⋈ project  (뷰 v_project_eval_summary 활용)
-- ---------------------------------------------------------------------
SELECT '[S4] 가장 최근 종료 프로젝트의 평가 종합' AS scenario;
SELECT p.project_code, p.project_name, e.emp_no, e.emp_name,
       s.customer_score, s.pm_score, s.peer_score, s.eval_count, s.weighted_score, s.incentive_grade
  FROM v_project_eval_summary s
  JOIN project  p ON p.project_id = s.project_id
  JOIN employee e ON e.emp_id = s.evaluatee_emp_id
 WHERE p.project_id = (SELECT project_id FROM project WHERE status = 'COMPLETED'
                         AND EXISTS (SELECT 1 FROM evaluation ev WHERE ev.project_id = project.project_id AND ev.status <> 'REQUESTED')
                        ORDER BY end_date DESC LIMIT 1)
 ORDER BY s.weighted_score DESC;

SELECT '[S4-b] 같은 프로젝트의 평가 상세 (슈퍼타입 ⋈ 3개 서브타입 ⋈ 상세)' AS scenario;
SELECT ev.eval_type, te.emp_name AS evaluatee,
       COALESCE(cc.contact_name, pe1.emp_name, pe2.emp_name) AS evaluator,
       it.item_name, dt.score, dt.comment
  FROM evaluation ev
  JOIN employee te ON te.emp_id = ev.evaluatee_emp_id
  LEFT JOIN customer_eval ce ON ce.eval_id = ev.eval_id
  LEFT JOIN client_contact cc ON cc.contact_id = ce.contact_id
  LEFT JOIN pm_eval  pm ON pm.eval_id = ev.eval_id
  LEFT JOIN employee pe1 ON pe1.emp_id = pm.evaluator_emp_id
  LEFT JOIN peer_eval pr ON pr.eval_id = ev.eval_id
  LEFT JOIN employee pe2 ON pe2.emp_id = pr.evaluator_emp_id
  JOIN eval_detail dt ON dt.eval_id = ev.eval_id
  JOIN eval_item   it ON it.item_id = dt.item_id
 WHERE ev.project_id = (SELECT project_id FROM project WHERE status = 'COMPLETED'
                          AND EXISTS (SELECT 1 FROM evaluation ev2 WHERE ev2.project_id = project.project_id AND ev2.status <> 'REQUESTED')
                        ORDER BY end_date DESC LIMIT 1)
 ORDER BY te.emp_name, FIELD(ev.eval_type, 'CUSTOMER', 'PM', 'PEER'), it.item_id
 LIMIT 20;

-- ---------------------------------------------------------------------
-- [S5] 인센티브 지급 기초자료: 2025년 종료 프로젝트 기준 개인별 평균 종합점수·등급·PM 추천 수·지급 권고액
--      v_project_eval_summary ⋈ project ⋈ employee ⋈ developer (+ pm_eval)
-- ---------------------------------------------------------------------
SELECT '[S5] 2025년 인센티브 산정 기초자료 (상위 10명)' AS scenario;
SELECT e.emp_no, e.emp_name, d.skill_grade,
       COUNT(*) AS project_cnt,
       ROUND(AVG(s.weighted_score), 2) AS avg_score,
       SUM(s.incentive_grade = 'S') AS s_cnt, SUM(s.incentive_grade = 'A') AS a_cnt,
       (SELECT COUNT(*) FROM pm_eval pm JOIN evaluation ev ON ev.eval_id = pm.eval_id JOIN project p2 ON p2.project_id = ev.project_id
         WHERE ev.evaluatee_emp_id = e.emp_id AND pm.recommend_incentive = 1 AND YEAR(p2.end_date) = 2025) AS pm_recommend_cnt,
       CASE WHEN AVG(s.weighted_score) >= 4.5 THEN 'S' WHEN AVG(s.weighted_score) >= 4.0 THEN 'A'
            WHEN AVG(s.weighted_score) >= 3.0 THEN 'B' ELSE 'C' END AS final_grade,
       CASE WHEN AVG(s.weighted_score) >= 4.5 THEN 1.5 WHEN AVG(s.weighted_score) >= 4.0 THEN 1.0
            WHEN AVG(s.weighted_score) >= 3.0 THEN 0.5 ELSE 0 END * 1000000 * COUNT(*) AS recommended_bonus
  FROM v_project_eval_summary s
  JOIN project   p ON p.project_id = s.project_id
  JOIN employee  e ON e.emp_id = s.evaluatee_emp_id
  JOIN developer d ON d.emp_id = s.evaluatee_emp_id
 WHERE p.status = 'COMPLETED' AND YEAR(p.end_date) = 2025
 GROUP BY e.emp_id, e.emp_no, e.emp_name, d.skill_grade
 ORDER BY avg_score DESC, project_cnt DESC
 LIMIT 10;

-- ---------------------------------------------------------------------
-- [S6] 투입 후보 검색: 2027-01-15 ~ 2027-06-30 기간에 가용(투입률 합계 < 100%)하고 'Spring Boot' 숙련도 3 이상인 중급 이상 개발자
--      employee ⋈ developer ⋈ employee_skill ⋈ skill (+ assignment 상관 부질의)
-- ---------------------------------------------------------------------
SELECT '[S6] 2027-01-15~06-30 가용 + Spring Boot ≥3 + 중급 이상 개발자' AS scenario;
SELECT e.emp_no, e.emp_name, d.skill_grade, es.proficiency, es.years_used,
       IFNULL((SELECT MAX(x.participation_rate) FROM assignment x
                WHERE x.emp_id = e.emp_id AND x.start_date <= '2027-06-30' AND x.end_date >= '2027-01-15'), 0) AS max_overlap_rate
  FROM employee e
  JOIN developer d ON d.emp_id = e.emp_id
  JOIN employee_skill es ON es.emp_id = e.emp_id
  JOIN skill s ON s.skill_id = es.skill_id
 WHERE s.skill_name = 'Spring Boot' AND es.proficiency >= 3
   AND d.skill_grade IN ('중급', '고급', '특급') AND e.status = 'ACTIVE'
   AND NOT EXISTS (SELECT 1 FROM assignment x
                    WHERE x.emp_id = e.emp_id AND x.participation_rate = 100
                      AND x.start_date <= '2027-06-30' AND x.end_date >= '2027-01-15')
 ORDER BY d.skill_grade DESC, es.proficiency DESC;
