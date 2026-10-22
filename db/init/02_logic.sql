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
--   BR-30 직원 서브타입은 판별자(emp_type)와 일치하고 배타적 (개발자이면서 지원직일 수 없음),
--         서브타입 행이 있는 직원의 판별자는 바꿀 수 없음
--         ※ '모든 직원은 서브타입을 반드시 가진다'(전체 참여)는 직원·서브타입을 한 트랜잭션으로 등록해 보장
--           (MySQL 은 지연 제약을 지원하지 않아 행 단위 트리거로는 검사 불가 — 회원가입·시드가 같은 트랜잭션에서 등록)
--   ── 조별 특화 시나리오 A: 고객사 변경요청 및 승인 관리 ──
--   BR-16 변경요청은 예정·진행 중 프로젝트에만, 요청번호 자동 채번
--   BR-17 요청한 담당자는 해당 프로젝트 발주처 소속
--   BR-18 변경요청 접수와 검토안 작성은 해당 프로젝트 PM 만
--   BR-19 결정·동의·반영은 최신 차수 검토안에만 (승인 후 내용 변경은 새 차수로 재검토)
--   BR-20 결정이 난 검토안의 제안 내용(종료예정일·금액·의견)은 수정 불가
--   BR-21 내부 승인·반려는 경영진만
--   BR-22 고객 동의는 내부 승인 후에만, 동의 담당자는 해당 발주처 소속
--   BR-23 내부 승인 + 고객 동의가 모두 끝난 검토안만 반영, 같은 검토안 중복 반영 금지,
--         반영 시 변경 전후 값 이력 보존, 새 종료예정일보다 늦게 끝나는 투입이 있으면 거부
--   ── 조별 특화 시나리오 B: 평가 기반 역량 개선 및 교육 이수 관리 ──
--   BR-24 역량개선계획의 대상은 근거 프로젝트(종료)에 참여한 개발자
--   BR-25 계획은 교육 담당자로 지정된 경영관리 직원만 수립
--   BR-26 신청한 일정은 계획에서 추천한 교육과정의 일정이어야 함
--   BR-27 같은 직원은 같은 일정에 중복 신청 불가 (취소 건 제외)
--   BR-28 일정별 정원 초과 신청 불가
--   BR-29 신청은 교육 시작 전에만, 수료·미수료 기록은 교육 종료 후 신청 건에만
--   (수료가 기술등급을 자동으로 바꾸지 않음: 두 데이터 사이에 트리거를 두지 않음)
-- =====================================================================
USE si_pms;

DROP PROCEDURE IF EXISTS sp_next_seq;
DROP PROCEDURE IF EXISTS sp_validate_assignment;
DROP TRIGGER   IF EXISTS trg_employee_bi;
DROP TRIGGER   IF EXISTS trg_employee_bu;
DROP TRIGGER   IF EXISTS trg_developer_bi;
DROP TRIGGER   IF EXISTS trg_staff_bi;
DROP TRIGGER   IF EXISTS trg_project_bi;
DROP TRIGGER   IF EXISTS trg_assignment_bi;
DROP TRIGGER   IF EXISTS trg_assignment_bu;
DROP TRIGGER   IF EXISTS trg_evaluation_bi;
DROP TRIGGER   IF EXISTS trg_customer_eval_bi;
DROP TRIGGER   IF EXISTS trg_pm_eval_bi;
DROP TRIGGER   IF EXISTS trg_peer_eval_bi;
DROP TRIGGER   IF EXISTS trg_developer_bu;
DROP TRIGGER   IF EXISTS trg_developer_au;
DROP PROCEDURE IF EXISTS sp_validate_change_review;
DROP PROCEDURE IF EXISTS sp_sync_change_status;
DROP PROCEDURE IF EXISTS sp_apply_change;
DROP TRIGGER   IF EXISTS trg_change_request_bi;
DROP TRIGGER   IF EXISTS trg_change_review_bi;
DROP TRIGGER   IF EXISTS trg_change_review_bu;
DROP TRIGGER   IF EXISTS trg_change_review_ai;
DROP TRIGGER   IF EXISTS trg_change_review_au;
DROP TRIGGER   IF EXISTS trg_change_history_bi;
DROP TRIGGER   IF EXISTS trg_change_history_ai;
DROP TRIGGER   IF EXISTS trg_development_plan_bi;
DROP TRIGGER   IF EXISTS trg_enrollment_bi;
DROP TRIGGER   IF EXISTS trg_enrollment_bu;
DROP VIEW      IF EXISTS v_training_plan;
DROP VIEW      IF EXISTS v_change_request;
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

-- ---------------------------------------------------------------------
-- [BR-30] 직원 슈퍼타입-서브타입: 판별자 일치 + 배타성
-- ---------------------------------------------------------------------
CREATE TRIGGER trg_developer_bi BEFORE INSERT ON developer FOR EACH ROW
BEGIN
  DECLARE v_type VARCHAR(10);
  DECLARE v_cnt INT DEFAULT 0;
  SELECT emp_type INTO v_type FROM employee WHERE emp_id = NEW.emp_id;
  IF v_type <> 'DEV' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-30] 직원 구분(emp_type)이 DEV 인 직원만 개발자 서브타입을 가질 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM staff WHERE emp_id = NEW.emp_id;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-30] 이미 지원직인 직원은 개발자가 될 수 없습니다. (서브타입 배타)';
  END IF;
END$$

CREATE TRIGGER trg_staff_bi BEFORE INSERT ON staff FOR EACH ROW
BEGIN
  DECLARE v_type VARCHAR(10);
  DECLARE v_cnt INT DEFAULT 0;
  SELECT emp_type INTO v_type FROM employee WHERE emp_id = NEW.emp_id;
  IF v_type <> 'STAFF' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-30] 직원 구분(emp_type)이 STAFF 인 직원만 지원직 서브타입을 가질 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM developer WHERE emp_id = NEW.emp_id;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-30] 이미 개발자인 직원은 지원직이 될 수 없습니다. (서브타입 배타)';
  END IF;
END$$

CREATE TRIGGER trg_employee_bu BEFORE UPDATE ON employee FOR EACH ROW
BEGIN
  DECLARE v_cnt INT DEFAULT 0;
  IF NEW.emp_type <> OLD.emp_type THEN
    SELECT (SELECT COUNT(*) FROM developer WHERE emp_id = OLD.emp_id) + (SELECT COUNT(*) FROM staff WHERE emp_id = OLD.emp_id) INTO v_cnt;
    IF v_cnt > 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-30] 서브타입이 등록된 직원의 구분(emp_type)은 바꿀 수 없습니다.';
    END IF;
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

-- =====================================================================
-- [조별 특화 시나리오 A] 고객사 변경요청 및 승인 관리 (BR-16 ~ BR-23)
-- =====================================================================
CREATE TRIGGER trg_change_request_bi BEFORE INSERT ON change_request FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_client INT;
  DECLARE v_cnt INT DEFAULT 0;
  DECLARE v_seq INT;
  SELECT status, client_id INTO v_status, v_client FROM project WHERE project_id = NEW.project_id;
  IF v_status NOT IN ('PLANNED', 'IN_PROGRESS') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-16] 변경요청은 예정 또는 진행 중인 프로젝트에만 접수할 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM client_contact WHERE contact_id = NEW.contact_id AND client_id = v_client;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-17] 요청한 담당자는 해당 프로젝트 발주처 소속이어야 합니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM assignment a JOIN job_role r ON r.role_id = a.role_id
   WHERE a.project_id = NEW.project_id AND a.emp_id = NEW.received_by_emp_id AND r.role_code = 'PM';
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-18] 변경요청은 해당 프로젝트 PM 만 접수할 수 있습니다.';
  END IF;
  IF NEW.cr_no IS NULL OR NEW.cr_no = '' THEN
    CALL sp_next_seq('CR_NO', YEAR(NEW.request_date), v_seq);
    SET NEW.cr_no = CONCAT('CR', YEAR(NEW.request_date), '-', LPAD(v_seq, 3, '0'));
  END IF;
  SET NEW.status = 'RECEIVED';
END$$

-- 검토안 INSERT/UPDATE 공통 검증 (p_old_* 는 INSERT 시 NULL)
CREATE PROCEDURE sp_validate_change_review(
  IN p_is_insert TINYINT, IN p_cr_id INT, IN p_version TINYINT, IN p_reviewer INT,
  IN p_decision VARCHAR(10), IN p_old_decision VARCHAR(10), IN p_decided_by INT,
  IN p_consent VARCHAR(10), IN p_old_consent VARCHAR(10), IN p_consent_contact INT)
BEGIN
  DECLARE v_project INT;
  DECLARE v_client INT;
  DECLARE v_cr_status VARCHAR(10);
  DECLARE v_max TINYINT;
  DECLARE v_cnt INT DEFAULT 0;
  SELECT cr.project_id, cr.status, p.client_id INTO v_project, v_cr_status, v_client
    FROM change_request cr JOIN project p ON p.project_id = cr.project_id WHERE cr.cr_id = p_cr_id;
  IF v_cr_status = 'APPLIED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 이미 프로젝트에 반영된 변경요청입니다.';
  END IF;
  SELECT IFNULL(MAX(version_no), 0) INTO v_max FROM change_review WHERE cr_id = p_cr_id;
  IF p_is_insert = 1 THEN
    IF p_version <> v_max + 1 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-19] 검토 차수는 기존 최신 차수 + 1 이어야 합니다.';
    END IF;
    SELECT COUNT(*) INTO v_cnt FROM assignment a JOIN job_role r ON r.role_id = a.role_id
     WHERE a.project_id = v_project AND a.emp_id = p_reviewer AND r.role_code = 'PM';
    IF v_cnt = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-18] 검토안(영향 분석)은 해당 프로젝트 PM 만 작성할 수 있습니다.';
    END IF;
  ELSEIF p_version <> v_max AND (p_decision <> p_old_decision OR p_consent <> p_old_consent) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-19] 최신 차수의 검토안만 결정하거나 고객 동의를 기록할 수 있습니다.';
  END IF;
  -- BR-21 : 결정은 경영진만, PENDING 에서 한 번만
  IF p_decision <> 'PENDING' AND (p_is_insert = 1 OR p_decision <> p_old_decision) THEN
    IF p_old_decision IS NOT NULL AND p_old_decision <> 'PENDING' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-21] 이미 결정된 검토안입니다. 내용이 바뀌면 새 차수로 재검토하세요.';
    END IF;
    SELECT COUNT(*) INTO v_cnt FROM user_account WHERE emp_id = p_decided_by AND auth_role = 'EXECUTIVE';
    IF v_cnt = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-21] 변경 검토안의 승인·반려는 경영진만 할 수 있습니다.';
    END IF;
  END IF;
  -- BR-22 : 고객 동의는 내부 승인 후에만, 해당 발주처 담당자만
  IF p_consent <> 'PENDING' AND (p_is_insert = 1 OR p_consent <> p_old_consent) THEN
    IF p_decision <> 'APPROVED' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-22] 고객 동의는 내부 승인된 검토안에만 기록할 수 있습니다.';
    END IF;
    IF p_old_consent IS NOT NULL AND p_old_consent <> 'PENDING' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-22] 고객 동의 결과가 이미 기록되어 있습니다.';
    END IF;
    SELECT COUNT(*) INTO v_cnt FROM client_contact WHERE contact_id = p_consent_contact AND client_id = v_client;
    IF v_cnt = 0 THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-22] 동의한 담당자는 해당 프로젝트 발주처 소속이어야 합니다.';
    END IF;
  END IF;
END$$

CREATE TRIGGER trg_change_review_bi BEFORE INSERT ON change_review FOR EACH ROW
  CALL sp_validate_change_review(1, NEW.cr_id, NEW.version_no, NEW.reviewer_emp_id,
       NEW.decision, NULL, NEW.decided_by_emp_id, NEW.consent, NULL, NEW.consent_contact_id)$$

CREATE TRIGGER trg_change_review_bu BEFORE UPDATE ON change_review FOR EACH ROW
BEGIN
  -- BR-20 : 결정이 난 검토안의 제안 내용은 고칠 수 없음
  IF OLD.decision <> 'PENDING' AND (NEW.proposed_end_date <> OLD.proposed_end_date
       OR NEW.additional_amount <> OLD.additional_amount
       OR NOT (NEW.review_comment <=> OLD.review_comment)) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-20] 결정이 난 검토안은 수정할 수 없습니다. 새 차수로 재검토하세요.';
  END IF;
  CALL sp_validate_change_review(0, NEW.cr_id, NEW.version_no, NEW.reviewer_emp_id,
       NEW.decision, OLD.decision, NEW.decided_by_emp_id, NEW.consent, OLD.consent, NEW.consent_contact_id);
END$$

-- 변경요청 상태 = 최신 차수 검토안의 결정·동의 상태
CREATE PROCEDURE sp_sync_change_status(IN p_cr_id INT)
BEGIN
  UPDATE change_request cr
    JOIN change_review rv ON rv.cr_id = cr.cr_id
     AND rv.version_no = (SELECT MAX(version_no) FROM change_review WHERE cr_id = p_cr_id)
     SET cr.status = CASE
           WHEN rv.decision = 'PENDING'  THEN 'REVIEWING'
           WHEN rv.decision = 'REJECTED' THEN 'REJECTED'
           WHEN rv.consent  = 'AGREED'   THEN 'AGREED'
           WHEN rv.consent  = 'DECLINED' THEN 'DECLINED'
           ELSE 'APPROVED' END
   WHERE cr.cr_id = p_cr_id AND cr.status <> 'APPLIED';
END$$

CREATE TRIGGER trg_change_review_ai AFTER INSERT ON change_review FOR EACH ROW
  CALL sp_sync_change_status(NEW.cr_id)$$

CREATE TRIGGER trg_change_review_au AFTER UPDATE ON change_review FOR EACH ROW
  CALL sp_sync_change_status(NEW.cr_id)$$

-- BR-23 : 적용이력은 승인 + 동의된 최신 검토안만
CREATE TRIGGER trg_change_history_bi BEFORE INSERT ON change_history FOR EACH ROW
BEGIN
  DECLARE v_cr INT;
  DECLARE v_ver TINYINT;
  DECLARE v_dec VARCHAR(10);
  DECLARE v_con VARCHAR(10);
  SELECT cr_id, version_no, decision, consent INTO v_cr, v_ver, v_dec, v_con
    FROM change_review WHERE review_id = NEW.review_id;
  IF v_dec <> 'APPROVED' OR v_con <> 'AGREED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 내부 승인과 고객 동의가 모두 끝난 검토안만 반영할 수 있습니다.';
  END IF;
  IF v_ver <> (SELECT MAX(version_no) FROM change_review WHERE cr_id = v_cr) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-19] 최신 차수의 검토안만 반영할 수 있습니다.';
  END IF;
END$$

CREATE TRIGGER trg_change_history_ai AFTER INSERT ON change_history FOR EACH ROW
  UPDATE change_request SET status = 'APPLIED'
   WHERE cr_id = (SELECT cr_id FROM change_review WHERE review_id = NEW.review_id)$$

-- 반영: 검증 → 이력 기록 → 프로젝트 종료예정일·계약금액 변경 (한 트랜잭션은 호출자가 관리)
CREATE PROCEDURE sp_apply_change(IN p_review_id INT, IN p_emp_id INT)
BEGIN
  DECLARE v_project INT;
  DECLARE v_start DATE;
  DECLARE v_end DATE;
  DECLARE v_amount DECIMAL(15,0);
  DECLARE v_new_end DATE;
  DECLARE v_add DECIMAL(15,0);
  DECLARE v_status VARCHAR(20);
  DECLARE v_late DATE;
  DECLARE v_cnt INT DEFAULT 0;
  DECLARE v_msg VARCHAR(160);
  SELECT p.project_id, p.start_date, p.end_date, p.contract_amount, p.status, rv.proposed_end_date, rv.additional_amount
    INTO v_project, v_start, v_end, v_amount, v_status, v_new_end, v_add
    FROM change_review rv JOIN change_request cr ON cr.cr_id = rv.cr_id
    JOIN project p ON p.project_id = cr.project_id
   WHERE rv.review_id = p_review_id FOR UPDATE;
  -- 검토안 상태를 먼저 확인 (이미 반영 → 최신 차수 → 승인·동의 순)
  SELECT COUNT(*) INTO v_cnt FROM change_history WHERE review_id = p_review_id;
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 이미 반영된 검토안입니다. 같은 요청을 두 번 반영할 수 없습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM change_review rv
   WHERE rv.review_id = p_review_id
     AND rv.version_no = (SELECT MAX(x.version_no) FROM change_review x WHERE x.cr_id = rv.cr_id);
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-19] 최신 차수의 검토안만 반영할 수 있습니다. 재검토된 요청은 새 차수로 진행하세요.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM change_review WHERE review_id = p_review_id AND decision = 'APPROVED' AND consent = 'AGREED';
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 내부 승인과 고객 동의가 모두 끝난 검토안만 반영할 수 있습니다.';
  END IF;
  IF v_status NOT IN ('PLANNED', 'IN_PROGRESS') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-16] 예정 또는 진행 중인 프로젝트에만 변경을 반영할 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM user_account ua WHERE ua.emp_id = p_emp_id AND ua.auth_role = 'EXECUTIVE';
  IF v_cnt = 0 THEN
    SELECT COUNT(*) INTO v_cnt FROM assignment a JOIN job_role r ON r.role_id = a.role_id
     WHERE a.project_id = v_project AND a.emp_id = p_emp_id AND r.role_code = 'PM';
  END IF;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 변경 반영은 해당 프로젝트 PM 또는 경영진만 할 수 있습니다.';
  END IF;
  IF v_new_end < v_start THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-23] 새 종료예정일이 착수일보다 빠릅니다.';
  END IF;
  SELECT MAX(end_date) INTO v_late FROM assignment WHERE project_id = v_project;
  IF v_late IS NOT NULL AND v_late > v_new_end THEN
    SET v_msg = CONCAT('[BR-23] ', v_late, ' 까지 투입된 인력이 있어 종료예정일을 ', v_new_end, ' 로 앞당길 수 없습니다. 투입을 먼저 조정하세요.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  INSERT INTO change_history (review_id, before_end_date, after_end_date, before_amount, after_amount, applied_by_emp_id)
  VALUES (p_review_id, v_end, v_new_end, v_amount, IFNULL(v_amount, 0) + v_add, p_emp_id);
  UPDATE project SET end_date = v_new_end, contract_amount = IFNULL(v_amount, 0) + v_add WHERE project_id = v_project;
END$$

-- =====================================================================
-- [조별 특화 시나리오 B] 역량 개선 및 교육 이수 관리 (BR-24 ~ BR-29)
-- =====================================================================
CREATE TRIGGER trg_development_plan_bi BEFORE INSERT ON development_plan FOR EACH ROW
BEGIN
  DECLARE v_status VARCHAR(20);
  DECLARE v_cnt INT DEFAULT 0;
  SELECT status INTO v_status FROM project WHERE project_id = NEW.project_id;
  IF v_status <> 'COMPLETED' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-24] 역량개선계획은 종료된 프로젝트의 평가를 근거로만 수립할 수 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM assignment WHERE project_id = NEW.project_id AND emp_id = NEW.emp_id;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-24] 계획 대상자는 근거 프로젝트에 참여한 개발자여야 합니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM staff WHERE emp_id = NEW.manager_emp_id AND is_training_manager = 1;
  IF v_cnt = 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-25] 역량개선계획은 교육 담당자로 지정된 직원만 수립할 수 있습니다.';
  END IF;
END$$

CREATE TRIGGER trg_enrollment_bi BEFORE INSERT ON training_enrollment FOR EACH ROW
BEGIN
  DECLARE v_emp INT;
  DECLARE v_plan_course INT;
  DECLARE v_course INT;
  DECLARE v_start DATETIME;
  DECLARE v_cap SMALLINT;
  DECLARE v_cnt INT DEFAULT 0;
  DECLARE v_msg VARCHAR(128);
  SELECT emp_id, course_id INTO v_emp, v_plan_course FROM development_plan WHERE plan_id = NEW.plan_id;
  SELECT course_id, start_at, capacity INTO v_course, v_start, v_cap FROM training_session WHERE session_id = NEW.session_id FOR UPDATE;
  IF v_course <> v_plan_course THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-26] 계획에서 추천한 교육과정의 일정에만 신청할 수 있습니다.';
  END IF;
  IF NEW.applied_at >= v_start THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-29] 이미 시작한 교육일정에는 신청할 수 없습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM training_enrollment te JOIN development_plan dp ON dp.plan_id = te.plan_id
   WHERE te.session_id = NEW.session_id AND dp.emp_id = v_emp AND te.status <> 'CANCELLED';
  IF v_cnt > 0 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-27] 같은 교육일정에 이미 신청한 기록이 있습니다.';
  END IF;
  SELECT COUNT(*) INTO v_cnt FROM training_enrollment WHERE session_id = NEW.session_id AND status <> 'CANCELLED';
  IF v_cnt >= v_cap THEN
    SET v_msg = CONCAT('[BR-28] 정원이 찼습니다. (정원 ', v_cap, '명, 신청 ', v_cnt, '명)');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
END$$

CREATE TRIGGER trg_enrollment_bu BEFORE UPDATE ON training_enrollment FOR EACH ROW
BEGIN
  DECLARE v_start DATETIME;
  DECLARE v_end DATETIME;
  IF NEW.status <> OLD.status THEN
    SELECT start_at, end_at INTO v_start, v_end FROM training_session WHERE session_id = NEW.session_id;
    IF OLD.status <> 'APPLIED' THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-29] 이미 처리된 신청입니다. 재수강은 다른 일정에 새로 신청하세요.';
    END IF;
    IF NEW.status = 'CANCELLED' AND NOW() >= v_start THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-29] 이미 시작한 교육은 취소할 수 없습니다.';
    END IF;
    IF NEW.status IN ('COMPLETED', 'NOT_COMPLETED') AND NOW() < v_end THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '[BR-29] 수료 여부는 교육이 끝난 뒤에 기록할 수 있습니다.';
    END IF;
    SET NEW.processed_at = NOW();
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

-- [시나리오 A 데모 S7] 변경요청 ⋈ 프로젝트 ⋈ 발주처 ⋈ 담당자 ⋈ PM ⋈ 최신 검토안 ⋈ 결정자 ⋈ 동의 담당자 ⋈ 적용이력
CREATE VIEW v_change_request AS
SELECT cr.cr_id, cr.cr_no, cr.status, cr.request_date, cr.title, cr.content, cr.reason,
       p.project_id, p.project_code, p.project_name, p.status AS project_status,
       c.client_name, cc.contact_name AS requested_by, pm.emp_name AS received_pm,
       rv.review_id, rv.version_no, rv.proposed_end_date, rv.additional_amount, rv.review_comment,
       rv.decision, ex.emp_name AS decided_by, rv.decided_at, rv.decision_reason,
       rv.consent, ccs.contact_name AS consent_by, rv.consent_date, rv.consent_evidence,
       h.before_end_date, h.after_end_date, h.before_amount, h.after_amount, h.applied_at, ap.emp_name AS applied_by
  FROM change_request cr
  JOIN project  p  ON p.project_id  = cr.project_id
  JOIN client   c  ON c.client_id   = p.client_id
  JOIN client_contact cc ON cc.contact_id = cr.contact_id
  JOIN employee pm ON pm.emp_id     = cr.received_by_emp_id
  LEFT JOIN change_review rv ON rv.cr_id = cr.cr_id
        AND rv.version_no = (SELECT MAX(x.version_no) FROM change_review x WHERE x.cr_id = cr.cr_id)
  LEFT JOIN employee ex ON ex.emp_id = rv.decided_by_emp_id
  LEFT JOIN client_contact ccs ON ccs.contact_id = rv.consent_contact_id
  LEFT JOIN change_history h ON h.review_id = rv.review_id
  LEFT JOIN employee ap ON ap.emp_id = h.applied_by_emp_id;

-- [시나리오 B 데모 S8] 계획 ⋈ 직원 ⋈ 프로젝트 ⋈ 평가 종합 ⋈ 추천 과정 ⋈ 담당자 ⋈ (최근 신청 ⋈ 일정)
--   이수 상태는 저장하지 않고 신청 이력에서 계산 (수료 > 신청 > 미수료 > 미신청)
CREATE VIEW v_training_plan AS
SELECT dp.plan_id, dp.emp_id, e.emp_no, e.emp_name, d.skill_grade,
       dp.project_id, p.project_code, p.project_name,
       es.weighted_score, es.incentive_grade,
       (SELECT ROUND(AVG(vs.comm_score), 2) FROM v_eval_score vs WHERE vs.project_id = dp.project_id AND vs.evaluatee_emp_id = dp.emp_id) AS comm_avg,
       (SELECT ROUND(AVG(vs.work_score), 2) FROM v_eval_score vs WHERE vs.project_id = dp.project_id AND vs.evaluatee_emp_id = dp.emp_id) AS work_avg,
       dp.course_id, tc.course_name, tc.field, sk.skill_name,
       dp.manager_emp_id, m.emp_name AS manager_name,
       dp.improvement_goal, dp.reason, dp.created_date, dp.due_date,
       CASE WHEN EXISTS (SELECT 1 FROM training_enrollment x WHERE x.plan_id = dp.plan_id AND x.status = 'COMPLETED') THEN 'COMPLETED'
            WHEN EXISTS (SELECT 1 FROM training_enrollment x WHERE x.plan_id = dp.plan_id AND x.status = 'APPLIED') THEN 'APPLIED'
            WHEN EXISTS (SELECT 1 FROM training_enrollment x WHERE x.plan_id = dp.plan_id AND x.status = 'NOT_COMPLETED') THEN 'NOT_COMPLETED'
            ELSE 'NOT_APPLIED' END AS plan_status,
       le.enroll_id, le.status AS last_enroll_status, ts.start_at AS last_session_start, ts.place AS last_session_place
  FROM development_plan dp
  JOIN employee  e  ON e.emp_id = dp.emp_id
  JOIN developer d  ON d.emp_id = dp.emp_id
  JOIN project   p  ON p.project_id = dp.project_id
  JOIN training_course tc ON tc.course_id = dp.course_id
  LEFT JOIN skill sk ON sk.skill_id = tc.skill_id
  JOIN employee  m  ON m.emp_id = dp.manager_emp_id
  LEFT JOIN v_project_eval_summary es ON es.project_id = dp.project_id AND es.evaluatee_emp_id = dp.emp_id
  LEFT JOIN training_enrollment le ON le.enroll_id = (SELECT MAX(y.enroll_id) FROM training_enrollment y WHERE y.plan_id = dp.plan_id)
  LEFT JOIN training_session ts ON ts.session_id = le.session_id;
