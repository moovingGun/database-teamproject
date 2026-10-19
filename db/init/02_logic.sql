SET NAMES utf8mb4;
-- =====================================================================
--  SI-PMS  -  비즈니스 규칙 계층 (프로시저 · 트리거 · 뷰)
--  실행 순서 : 01_schema.sql → 02_logic.sql → 03_seed.sql
-- ---------------------------------------------------------------------
--  비즈니스 규칙(BR) 목록  (docs/01_요구사항정의서.md 와 번호 일치)
--   BR-01 프로젝트에는 개발자(developer 서브타입)만 투입 가능
--   BR-02 사번/프로젝트번호는 규칙에 따라 자동 채번 (E+YY+NNNN / P+YYYY-NNN)
--   BR-03 투입 기간은 프로젝트 기간 내여야 함
--   BR-04 동일 직원의 동일 프로젝트 투입 기간은 겹칠 수 없음
--   BR-05 동일 기간 개인 투입률 합계는 100% 이하
--   BR-06 같은 기간에 프로젝트 PM 은 1명
--   BR-07 직무별 최소 기술등급 충족
--   BR-08 평가는 종료(COMPLETED)된 프로젝트에 대해서만 등록
--   BR-09 피평가자는 해당 프로젝트 참여자
--   BR-10 서브타입 평가는 슈퍼타입의 eval_type 과 일치
--   BR-11 고객 평가자는 해당 프로젝트 발주처의 담당자
--   BR-12 고객 평가 의뢰는 프로젝트 PM 만 가능
--   BR-13 PM 평가의 평가자는 프로젝트 PM, 자기 자신은 평가 불가, 피평가자당 1건
--   BR-14 동료 평가의 평가자는 참여자, 자기 자신은 평가 불가, (평가자,피평가자)당 1건
--   BR-15 기술등급 변경 시 이력 자동 기록
-- =====================================================================
USE si_pms;

DROP PROCEDURE IF EXISTS sp_next_seq;
DROP PROCEDURE IF EXISTS sp_validate_assignment;
DROP TRIGGER   IF EXISTS trg_employee_bi;
DROP TRIGGER   IF EXISTS trg_project_bi;
DROP TRIGGER   IF EXISTS trg_assignment_bi;
DROP TRIGGER   IF EXISTS trg_assignment_bu;
DROP TRIGGER   IF EXISTS trg_evaluation_bi;
DROP TRIGGER   IF EXISTS trg_customer_eval_bi;
DROP TRIGGER   IF EXISTS trg_pm_eval_bi;
DROP TRIGGER   IF EXISTS trg_peer_eval_bi;
DROP TRIGGER   IF EXISTS trg_developer_bu;
DROP TRIGGER   IF EXISTS trg_developer_au;
DROP VIEW      IF EXISTS v_project_eval_summary;
DROP VIEW      IF EXISTS v_eval_score;
DROP VIEW      IF EXISTS v_assignment_detail;
DROP VIEW      IF EXISTS v_employee;

DELIMITER $$

-- ---------------------------------------------------------------------
-- [BR-02] 연도별 일련번호 채번 (행 잠금으로 동시성 보장)
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_next_seq(IN p_name VARCHAR(20), IN p_year SMALLINT, OUT p_next INT)
BEGIN
  INSERT IGNORE INTO seq_counter (seq_name, seq_year, last_seq) VALUES (p_name, p_year, 0);
  SELECT last_seq + 1 INTO p_next
    FROM seq_counter WHERE seq_name = p_name AND seq_year = p_year FOR UPDATE;
  UPDATE seq_counter SET last_seq = p_next WHERE seq_name = p_name AND seq_year = p_year;
END$$

CREATE TRIGGER trg_employee_bi BEFORE INSERT ON employee FOR EACH ROW
BEGIN
  DECLARE v_seq INT;
  IF NEW.emp_no IS NULL OR NEW.emp_no = '' THEN
    CALL sp_next_seq('EMP_NO', YEAR(NEW.hire_date), v_seq);
    SET NEW.emp_no = CONCAT('E', DATE_FORMAT(NEW.hire_date, '%y'), LPAD(v_seq, 4, '0'));
  END IF;
END$$

CREATE TRIGGER trg_project_bi BEFORE INSERT ON project FOR EACH ROW
BEGIN
  DECLARE v_seq INT;
  IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
    CALL sp_next_seq('PROJECT_CODE', YEAR(NEW.start_date), v_seq);
    SET NEW.project_code = CONCAT('P', YEAR(NEW.start_date), '-', LPAD(v_seq, 3, '0'));
  END IF;
END$$

-- ---------------------------------------------------------------------
-- [BR-01,03~07] 투입 검증 (INSERT / UPDATE 공통)
-- ---------------------------------------------------------------------
CREATE PROCEDURE sp_validate_assignment(
  IN p_assignment_id INT, IN p_project_id INT, IN p_emp_id INT, IN p_role_id INT,
  IN p_start DATE, IN p_end DATE, IN p_rate TINYINT)
BEGIN
  DECLARE v_pstart    DATE;
  DECLARE v_pend      DATE;
  DECLARE v_cnt       INT DEFAULT 0;
  DECLARE v_max_rate  INT DEFAULT 0;
  DECLARE v_role_code VARCHAR(10);
  DECLARE v_min_grade TINYINT;
  DECLARE v_grade     TINYINT;
  DECLARE v_self      INT;
  DECLARE v_msg       VARCHAR(128);
  SET v_self = IFNULL(p_assignment_id, 0);

  -- BR-01 / BR-07 : 개발자 여부, 직무별 최소 등급 (ENUM+0 = 등급 서열)
  SELECT skill_grade + 0 INTO v_grade FROM developer WHERE emp_id = p_emp_id;
  IF v_grade IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-01] 개발자만 프로젝트에 투입할 수 있습니다.';
  END IF;
  SELECT role_code, min_grade + 0 INTO v_role_code, v_min_grade FROM job_role WHERE role_id = p_role_id;
  IF v_grade < v_min_grade THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-07] 해당 직무의 최소 기술등급을 충족하지 않습니다.';
  END IF;

  -- BR-03 : 프로젝트 기간 내
  SELECT start_date, end_date INTO v_pstart, v_pend FROM project WHERE project_id = p_project_id;
  IF p_start < v_pstart OR p_end > v_pend THEN
    SET v_msg = CONCAT('[BR-03] 투입 기간은 프로젝트 기간(', v_pstart, ' ~ ', v_pend, ') 내여야 합니다.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  -- BR-04 : 동일 프로젝트 기간 중복
  SELECT COUNT(*) INTO v_cnt FROM assignment
   WHERE emp_id = p_emp_id AND project_id = p_project_id AND assignment_id <> v_self
     AND start_date <= p_end AND end_date >= p_start;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-04] 동일 프로젝트에 기간이 겹치는 투입이 이미 존재합니다.';
  END IF;

  -- BR-05 : 투입률 합계 (겹치는 구간의 모든 시작 시점에서 합계 검사)
  SELECT IFNULL(MAX(t.rate_sum), 0) INTO v_max_rate
    FROM (
      SELECT (SELECT IFNULL(SUM(a2.participation_rate), 0)
                FROM assignment a2
               WHERE a2.emp_id = p_emp_id AND a2.assignment_id <> v_self
                 AND a2.start_date <= d.chk_date AND a2.end_date >= d.chk_date) AS rate_sum
        FROM (SELECT p_start AS chk_date
              UNION
              SELECT a1.start_date FROM assignment a1
               WHERE a1.emp_id = p_emp_id AND a1.assignment_id <> v_self
                 AND a1.start_date BETWEEN p_start AND p_end) d
    ) t;
  IF v_max_rate + p_rate > 100 THEN
    SET v_msg = CONCAT('[BR-05] 해당 기간 투입률 합계가 100%를 초과합니다. (기존 ', v_max_rate, '% + 신규 ', p_rate, '%)');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  -- BR-06 : 동일 기간 PM 1명
  IF v_role_code = 'PM' THEN
    SELECT COUNT(*) INTO v_cnt
      FROM assignment a JOIN job_role r ON r.role_id = a.role_id
     WHERE a.project_id = p_project_id AND r.role_code = 'PM' AND a.assignment_id <> v_self
       AND a.start_date <= p_end AND a.end_date >= p_start;
    IF v_cnt > 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-06] 같은 기간에 PM은 1명만 지정할 수 있습니다.';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_assignment_bi BEFORE INSERT ON assignment FOR EACH ROW
  CALL sp_validate_assignment(NULL, NEW.project_id, NEW.emp_id, NEW.role_id,
                              NEW.start_date, NEW.end_date, NEW.participation_rate)$$

CREATE TRIGGER trg_assignment_bu BEFORE UPDATE ON assignment FOR EACH ROW
  CALL sp_validate_assignment(OLD.assignment_id, NEW.project_id, NEW.emp_id, NEW.role_id,
                              NEW.start_date, NEW.end_date, NEW.participation_rate)$$

-- ---------------------------------------------------------------------
-- [BR-08, 09] 평가 슈퍼타입 검증
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_evaluation_bi BEFORE INSERT ON evaluation FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_cnt INT DEFAULT 0;
  SELECT status INTO v_status FROM project WHERE project_id = NEW.project_id;
  IF v_status <> 'COMPLETED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-08] 평가는 종료(COMPLETED)된 프로젝트에 대해서만 등록할 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM assignment
   WHERE project_id = NEW.project_id AND emp_id = NEW.evaluatee_emp_id;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-09] 피평가자는 해당 프로젝트 참여자여야 합니다.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- [BR-10, 11, 12] 고객 평가 서브타입 검증
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_customer_eval_bi BEFORE INSERT ON customer_eval FOR EACH ROW
BEGIN
  DECLARE v_type VARCHAR(10);
  DECLARE v_project INT;
  DECLARE v_client INT;
  DECLARE v_cnt INT DEFAULT 0;
  SELECT eval_type, project_id INTO v_type, v_project FROM evaluation WHERE eval_id = NEW.eval_id;
  IF v_type <> 'CUSTOMER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-10] 평가 유형이 CUSTOMER 인 평가에만 등록할 수 있습니다.';
  END IF;
  SELECT client_id INTO v_client FROM project WHERE project_id = v_project;
  SELECT COUNT(*) INTO v_cnt FROM client_contact WHERE contact_id = NEW.contact_id AND client_id = v_client;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-11] 고객 평가자는 해당 프로젝트 발주처의 담당자여야 합니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt
    FROM assignment a JOIN job_role r ON r.role_id = a.role_id
   WHERE a.project_id = v_project AND a.emp_id = NEW.requested_by_emp_id AND r.role_code = 'PM';
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-12] 고객 평가 의뢰는 해당 프로젝트 PM만 할 수 있습니다.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- [BR-10, 13] PM 평가 서브타입 검증
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_pm_eval_bi BEFORE INSERT ON pm_eval FOR EACH ROW
BEGIN
  DECLARE v_type VARCHAR(10);
  DECLARE v_project INT;
  DECLARE v_evaluatee INT;
  DECLARE v_cnt INT DEFAULT 0;
  SELECT eval_type, project_id, evaluatee_emp_id INTO v_type, v_project, v_evaluatee
    FROM evaluation WHERE eval_id = NEW.eval_id;
  IF v_type <> 'PM' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-10] 평가 유형이 PM 인 평가에만 등록할 수 있습니다.';
  END IF;
  IF NEW.evaluator_emp_id = v_evaluatee THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-13] 자기 자신은 평가할 수 없습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt
    FROM assignment a JOIN job_role r ON r.role_id = a.role_id
   WHERE a.project_id = v_project AND a.emp_id = NEW.evaluator_emp_id AND r.role_code = 'PM';
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-13] PM 평가의 평가자는 해당 프로젝트 PM이어야 합니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt
    FROM pm_eval pe JOIN evaluation e ON e.eval_id = pe.eval_id
   WHERE e.project_id = v_project AND e.evaluatee_emp_id = v_evaluatee;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-13] 해당 팀원에 대한 PM 평가가 이미 존재합니다.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- [BR-10, 14] 동료 평가 서브타입 검증
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_peer_eval_bi BEFORE INSERT ON peer_eval FOR EACH ROW
BEGIN
  DECLARE v_type VARCHAR(10);
  DECLARE v_project INT;
  DECLARE v_evaluatee INT;
  DECLARE v_cnt INT DEFAULT 0;
  SELECT eval_type, project_id, evaluatee_emp_id INTO v_type, v_project, v_evaluatee
    FROM evaluation WHERE eval_id = NEW.eval_id;
  IF v_type <> 'PEER' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-10] 평가 유형이 PEER 인 평가에만 등록할 수 있습니다.';
  END IF;
  IF NEW.evaluator_emp_id = v_evaluatee THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-14] 자기 자신은 평가할 수 없습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM assignment
   WHERE project_id = v_project AND emp_id = NEW.evaluator_emp_id;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-14] 동료 평가의 평가자는 해당 프로젝트 참여자여야 합니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt
    FROM peer_eval pe JOIN evaluation e ON e.eval_id = pe.eval_id
   WHERE e.project_id = v_project AND e.evaluatee_emp_id = v_evaluatee
     AND pe.evaluator_emp_id = NEW.evaluator_emp_id;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-14] 동일 동료에 대한 평가가 이미 존재합니다.';
  END IF;
END$$

-- ---------------------------------------------------------------------
-- [BR-15] 기술등급 변경 이력 (세션 변수 @app_user_id / @grade_change_reason 활용)
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_developer_bu BEFORE UPDATE ON developer FOR EACH ROW
BEGIN
  IF OLD.skill_grade <> NEW.skill_grade THEN
    SET NEW.grade_updated_at = CURDATE();
  END IF;
END$$

CREATE TRIGGER trg_developer_au AFTER UPDATE ON developer FOR EACH ROW
BEGIN
  IF OLD.skill_grade <> NEW.skill_grade THEN
    INSERT INTO grade_history (emp_id, old_grade, new_grade, changed_by_emp_id, reason)
    VALUES (NEW.emp_id, OLD.skill_grade, NEW.skill_grade, @app_user_id, @grade_change_reason);
  END IF;
END$$

DELIMITER ;

-- ---------------------------------------------------------------------
-- 뷰 : 슈퍼타입-서브타입 통합 조회, 투입 상세, 평가 점수, 인센티브 산정
-- ---------------------------------------------------------------------
CREATE VIEW v_employee AS
SELECT e.emp_id, e.emp_no, e.emp_name, e.resident_reg_no,
       CONCAT(LEFT(e.resident_reg_no, 8), '******') AS rrn_masked,
       e.education_level, e.hire_date, e.emp_type, e.email, e.phone, e.status,
       d.skill_grade, d.career_start_date, d.grade_updated_at,
       TIMESTAMPDIFF(MONTH, d.career_start_date, CURDATE()) AS career_months,
       CASE WHEN d.emp_id IS NULL THEN NULL
            WHEN TIMESTAMPDIFF(MONTH, d.career_start_date, CURDATE()) <  36 THEN '초급'
            WHEN TIMESTAMPDIFF(MONTH, d.career_start_date, CURDATE()) <  72 THEN '중급'
            WHEN TIMESTAMPDIFF(MONTH, d.career_start_date, CURDATE()) < 120 THEN '고급'
            ELSE '특급' END AS recommended_grade,
       s.department, s.job_title,
       a.login_id, a.auth_role, a.is_active AS account_active
  FROM employee e
  LEFT JOIN developer    d ON d.emp_id = e.emp_id
  LEFT JOIN staff        s ON s.emp_id = e.emp_id
  LEFT JOIN user_account a ON a.emp_id = e.emp_id;

CREATE VIEW v_assignment_detail AS
SELECT a.assignment_id, a.project_id, p.project_code, p.project_name, p.status AS project_status,
       p.start_date AS project_start, p.end_date AS project_end,
       c.client_id, c.client_name,
       a.emp_id, e.emp_no, e.emp_name, d.skill_grade,
       r.role_id, r.role_code, r.role_name,
       a.start_date, a.end_date, a.participation_rate, a.note
  FROM assignment a
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id  = p.client_id
  JOIN employee  e ON e.emp_id     = a.emp_id
  JOIN developer d ON d.emp_id     = a.emp_id
  JOIN job_role  r ON r.role_id    = a.role_id;

CREATE VIEW v_eval_score AS
SELECT ev.eval_id, ev.project_id, ev.evaluatee_emp_id, ev.eval_type, ev.status, ev.eval_date,
       ROUND(SUM(dt.score * it.weight) / SUM(it.weight), 2) AS avg_score,
       MAX(CASE WHEN it.item_code = 'WORK' THEN dt.score END) AS work_score,
       MAX(CASE WHEN it.item_code = 'COMM' THEN dt.score END) AS comm_score
  FROM evaluation  ev
  JOIN eval_detail dt ON dt.eval_id = ev.eval_id
  JOIN eval_item   it ON it.item_id = dt.item_id
 GROUP BY ev.eval_id, ev.project_id, ev.evaluatee_emp_id, ev.eval_type, ev.status, ev.eval_date;

CREATE VIEW v_project_eval_summary AS
SELECT t.project_id, t.evaluatee_emp_id,
       ROUND(MAX(CASE WHEN t.eval_type = 'CUSTOMER' THEN t.type_avg END), 2) AS customer_score,
       ROUND(MAX(CASE WHEN t.eval_type = 'PM'       THEN t.type_avg END), 2) AS pm_score,
       ROUND(MAX(CASE WHEN t.eval_type = 'PEER'     THEN t.type_avg END), 2) AS peer_score,
       SUM(t.eval_cnt) AS eval_count,
       ROUND(SUM(t.type_avg * w.weight) / SUM(w.weight), 2) AS weighted_score,
       CASE WHEN ROUND(SUM(t.type_avg * w.weight) / SUM(w.weight), 2) >= 4.5 THEN 'S'
            WHEN ROUND(SUM(t.type_avg * w.weight) / SUM(w.weight), 2) >= 4.0 THEN 'A'
            WHEN ROUND(SUM(t.type_avg * w.weight) / SUM(w.weight), 2) >= 3.0 THEN 'B'
            ELSE 'C' END AS incentive_grade
  FROM (SELECT project_id, evaluatee_emp_id, eval_type,
               AVG(avg_score) AS type_avg, COUNT(*) AS eval_cnt
          FROM v_eval_score
         WHERE status IN ('SUBMITTED', 'REPORTED')
         GROUP BY project_id, evaluatee_emp_id, eval_type) t
  JOIN eval_type_weight w ON w.eval_type = t.eval_type
 GROUP BY t.project_id, t.evaluatee_emp_id;
