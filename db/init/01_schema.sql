SET NAMES utf8mb4;
-- =====================================================================
--  SI 프로젝트 인력·평가 관리 시스템 (SI-PMS)  -  스키마 생성 스크립트
--  DBMS : MySQL 8.0 (InnoDB, utf8mb4)
--  ERD  : docs/02_ERD.md (Information Engineering 표기법) 와 1:1 대응
--  실행 : mysql -u root -p < db/init/01_schema.sql
-- ---------------------------------------------------------------------
--  설계 원칙
--   * 직원(employee) / 프로젝트 평가(evaluation) 는 슈퍼타입-서브타입으로 분리
--   * 발주처(client) 는 별도 엔티티 + 담당자(client_contact) 1:N
--   * M:N 관계는 모두 교차 엔티티로 해소
--       개발자-기술       -> employee_skill
--       프로젝트-기술     -> project_skill
--       개발자-프로젝트   -> assignment (투입 이력 보존)
--   * 1:N 관계에서 Total:Total 참여 지양 (1측은 항상 Partial 로 설계)
--   * 모든 컬럼에 COMMENT 를 부여 -> docs/03_테이블정의서.md 자동 생성
-- =====================================================================
CREATE DATABASE IF NOT EXISTS si_pms
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE si_pms;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS grade_history, eval_detail, eval_item, eval_type_weight,
  peer_eval, pm_eval, customer_eval, evaluation,
  assignment, job_role, project_skill, project,
  employee_skill, skill, user_account, staff, developer, employee,
  client_contact, client, seq_counter;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 0. 자동 채번 카운터 (사번 / 프로젝트번호 규칙 채번용)
-- ---------------------------------------------------------------------
CREATE TABLE seq_counter (
  seq_name  VARCHAR(20) NOT NULL COMMENT '채번 대상 (EMP_NO | PROJECT_CODE)',
  seq_year  SMALLINT    NOT NULL COMMENT '채번 기준 연도',
  last_seq  INT         NOT NULL DEFAULT 0 COMMENT '마지막으로 발급한 일련번호',
  PRIMARY KEY (seq_name, seq_year)
) COMMENT='자동 채번 카운터';

-- ---------------------------------------------------------------------
-- 1. 발주처 / 발주처 담당자
-- ---------------------------------------------------------------------
CREATE TABLE client (
  client_id       INT          NOT NULL AUTO_INCREMENT COMMENT '발주처 ID (PK)',
  client_name     VARCHAR(100) NOT NULL COMMENT '발주처명',
  business_reg_no CHAR(12)     NOT NULL COMMENT '사업자등록번호 (000-00-00000)',
  industry        VARCHAR(50)  NULL     COMMENT '업종',
  address         VARCHAR(200) NULL     COMMENT '주소',
  phone           VARCHAR(20)  NULL     COMMENT '대표 전화',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  PRIMARY KEY (client_id),
  UNIQUE KEY uk_client_breg (business_reg_no)
) COMMENT='발주처(고객사)';

CREATE TABLE client_contact (
  contact_id   INT          NOT NULL AUTO_INCREMENT COMMENT '담당자 ID (PK)',
  client_id    INT          NOT NULL COMMENT '소속 발주처 (FK)',
  contact_name VARCHAR(50)  NOT NULL COMMENT '담당자명',
  position     VARCHAR(50)  NULL     COMMENT '직위',
  email        VARCHAR(100) NULL     COMMENT '이메일',
  phone        VARCHAR(20)  NULL     COMMENT '연락처',
  is_active    TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '재직 여부 (1=재직)',
  PRIMARY KEY (contact_id),
  CONSTRAINT fk_contact_client FOREIGN KEY (client_id) REFERENCES client (client_id)
) COMMENT='발주처 담당자 (고객 평가의 평가자)';

-- ---------------------------------------------------------------------
-- 2. 직원 (슈퍼타입) / 개발자, 지원직 (서브타입) / 로그인 계정
-- ---------------------------------------------------------------------
CREATE TABLE employee (
  emp_id          INT          NOT NULL AUTO_INCREMENT COMMENT '직원 ID (PK, 내부 식별자)',
  emp_no          CHAR(7)      NULL     COMMENT '사번 = E + 입사연도(2) + 연도별 일련번호(4). BEFORE INSERT 트리거가 자동 채번',
  emp_name        VARCHAR(50)  NOT NULL COMMENT '직원명',
  resident_reg_no CHAR(14)     NOT NULL COMMENT '주민등록번호 (000000-0000000). 화면에는 뒷자리 마스킹',
  education_level ENUM('고졸','전문학사','학사','석사','박사') NOT NULL COMMENT '최종학력',
  hire_date       DATE         NOT NULL COMMENT '입사일',
  emp_type        ENUM('DEV','STAFF') NOT NULL COMMENT '서브타입 판별자 (DEV=개발자, STAFF=지원직)',
  email           VARCHAR(100) NULL     COMMENT '이메일',
  phone           VARCHAR(20)  NULL     COMMENT '연락처',
  status          ENUM('ACTIVE','LEAVE','RESIGNED') NOT NULL DEFAULT 'ACTIVE' COMMENT '재직 상태',
  created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
  PRIMARY KEY (emp_id),
  UNIQUE KEY uk_employee_no  (emp_no),
  UNIQUE KEY uk_employee_rrn (resident_reg_no)
) COMMENT='직원 (슈퍼타입)';

CREATE TABLE developer (
  emp_id            INT  NOT NULL COMMENT '직원 ID (PK, FK → employee)',
  skill_grade       ENUM('초급','중급','고급','특급') NOT NULL COMMENT '기술등급',
  career_start_date DATE NOT NULL COMMENT '개발 경력 기산일 (입사 전 경력 포함). 총 경력은 이 날짜로부터 산출',
  grade_updated_at  DATE NULL     COMMENT '최근 기술등급 변경일',
  PRIMARY KEY (emp_id),
  CONSTRAINT fk_developer_employee FOREIGN KEY (emp_id) REFERENCES employee (emp_id) ON DELETE CASCADE
) COMMENT='개발자 (직원 서브타입: 프로젝트 투입 대상)';

CREATE TABLE staff (
  emp_id     INT         NOT NULL COMMENT '직원 ID (PK, FK → employee)',
  department ENUM('MARKETING','MANAGEMENT','RND') NOT NULL COMMENT '부서 (마케팅 / 경영관리 / 연구개발)',
  job_title  VARCHAR(50) NULL     COMMENT '직책',
  PRIMARY KEY (emp_id),
  CONSTRAINT fk_staff_employee FOREIGN KEY (emp_id) REFERENCES employee (emp_id) ON DELETE CASCADE
) COMMENT='지원직 (직원 서브타입: 마케팅·경영관리·연구개발)';

CREATE TABLE user_account (
  emp_id        INT          NOT NULL COMMENT '직원 ID (PK, FK → employee)',
  login_id      VARCHAR(30)  NOT NULL COMMENT '로그인 ID (회원가입 시 중복 체크)',
  password_hash VARCHAR(255) NOT NULL COMMENT '비밀번호 해시 (PBKDF2-SHA256)',
  auth_role     ENUM('EMPLOYEE','EXECUTIVE') NOT NULL DEFAULT 'EMPLOYEE' COMMENT '권한 (EMPLOYEE=일반직원, EXECUTIVE=경영진: 타 직원 조회 가능)',
  is_active     TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '계정 활성 여부',
  last_login_at DATETIME     NULL     COMMENT '최근 로그인 일시',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '가입일시',
  PRIMARY KEY (emp_id),
  UNIQUE KEY uk_account_login (login_id),
  CONSTRAINT fk_account_employee FOREIGN KEY (emp_id) REFERENCES employee (emp_id) ON DELETE CASCADE
) COMMENT='로그인 계정 (직원과 1:1)';

-- ---------------------------------------------------------------------
-- 3. 기술 사전 / 개발자 보유 기술
-- ---------------------------------------------------------------------
CREATE TABLE skill (
  skill_id   INT         NOT NULL AUTO_INCREMENT COMMENT '기술 ID (PK)',
  skill_name VARCHAR(50) NOT NULL COMMENT '기술명',
  category   ENUM('LANGUAGE','FRAMEWORK','DATABASE','CLOUD','OS','TOOL','METHOD') NOT NULL COMMENT '기술 분류',
  PRIMARY KEY (skill_id),
  UNIQUE KEY uk_skill_name (skill_name)
) COMMENT='기술 (Skill Set 사전)';

CREATE TABLE employee_skill (
  emp_id         INT          NOT NULL COMMENT '개발자 (FK → developer)',
  skill_id       INT          NOT NULL COMMENT '기술 (FK → skill)',
  proficiency    TINYINT      NOT NULL COMMENT '숙련도 (1~5)',
  years_used     DECIMAL(3,1) NOT NULL DEFAULT 0 COMMENT '사용 경력 (년)',
  last_used_date DATE         NULL     COMMENT '최근 사용일',
  PRIMARY KEY (emp_id, skill_id),
  CONSTRAINT fk_empskill_developer FOREIGN KEY (emp_id)   REFERENCES developer (emp_id) ON DELETE CASCADE,
  CONSTRAINT fk_empskill_skill     FOREIGN KEY (skill_id) REFERENCES skill (skill_id),
  CONSTRAINT chk_empskill_prof CHECK (proficiency BETWEEN 1 AND 5)
) COMMENT='개발자 보유 기술 (개발자:기술 M:N 해소)';

-- ---------------------------------------------------------------------
-- 4. 프로젝트 / 프로젝트 요구 기술 / 직무 / 투입
-- ---------------------------------------------------------------------
CREATE TABLE project (
  project_id      INT           NOT NULL AUTO_INCREMENT COMMENT '프로젝트 ID (PK)',
  project_code    VARCHAR(12)   NULL     COMMENT '프로젝트번호 = P + 착수연도(4) + - + 일련번호(3). BEFORE INSERT 트리거가 자동 채번',
  project_name    VARCHAR(100)  NOT NULL COMMENT '프로젝트명',
  client_id       INT           NOT NULL COMMENT '발주처 (FK)',
  start_date      DATE          NOT NULL COMMENT '착수일자',
  end_date        DATE          NOT NULL COMMENT '종료일자 (진행 중: 예정일, 종료: 실제 종료일)',
  status          ENUM('PLANNED','IN_PROGRESS','COMPLETED','CANCELLED') NOT NULL DEFAULT 'PLANNED' COMMENT '진행 상태',
  contract_amount DECIMAL(15,0) NULL     COMMENT '계약금액 (원)',
  description     VARCHAR(500)  NULL     COMMENT '프로젝트 개요',
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
  PRIMARY KEY (project_id),
  UNIQUE KEY uk_project_code (project_code),
  CONSTRAINT fk_project_client FOREIGN KEY (client_id) REFERENCES client (client_id),
  CONSTRAINT chk_project_period CHECK (start_date <= end_date)
) COMMENT='프로젝트';

CREATE TABLE project_skill (
  project_id     INT     NOT NULL COMMENT '프로젝트 (FK)',
  skill_id       INT     NOT NULL COMMENT '요구 기술 (FK)',
  required_level TINYINT NOT NULL DEFAULT 3 COMMENT '요구 숙련도 (1~5)',
  PRIMARY KEY (project_id, skill_id),
  CONSTRAINT fk_prjskill_project FOREIGN KEY (project_id) REFERENCES project (project_id) ON DELETE CASCADE,
  CONSTRAINT fk_prjskill_skill   FOREIGN KEY (skill_id)   REFERENCES skill (skill_id),
  CONSTRAINT chk_prjskill_level CHECK (required_level BETWEEN 1 AND 5)
) COMMENT='프로젝트 요구 기술 (프로젝트:기술 M:N 해소)';

CREATE TABLE job_role (
  role_id    INT         NOT NULL AUTO_INCREMENT COMMENT '직무 ID (PK)',
  role_code  VARCHAR(10) NOT NULL COMMENT '직무 코드 (PM, PL, ANALYST, DESIGNER, PROGRAMMER, TESTER)',
  role_name  VARCHAR(30) NOT NULL COMMENT '직무명',
  min_grade  ENUM('초급','중급','고급','특급') NOT NULL DEFAULT '초급' COMMENT '투입 가능 최소 기술등급 (비즈니스 규칙)',
  sort_order TINYINT     NOT NULL DEFAULT 0 COMMENT '표시 순서',
  PRIMARY KEY (role_id),
  UNIQUE KEY uk_role_code (role_code)
) COMMENT='직무 (프로젝트 투입 역할)';

CREATE TABLE assignment (
  assignment_id      INT          NOT NULL AUTO_INCREMENT COMMENT '투입 ID (PK)',
  project_id         INT          NOT NULL COMMENT '프로젝트 (FK)',
  emp_id             INT          NOT NULL COMMENT '투입 개발자 (FK → developer)',
  role_id            INT          NOT NULL COMMENT '수행 직무 (FK → job_role)',
  start_date         DATE         NOT NULL COMMENT '투입 시작일',
  end_date           DATE         NOT NULL COMMENT '투입 종료일 (미지정 시 프로젝트 종료일로 설정)',
  participation_rate TINYINT      NOT NULL DEFAULT 100 COMMENT '투입률 (%). 동일 기간 개인 합계 100% 이하',
  note               VARCHAR(200) NULL     COMMENT '비고',
  created_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  PRIMARY KEY (assignment_id),
  CONSTRAINT fk_assign_project   FOREIGN KEY (project_id) REFERENCES project (project_id),
  CONSTRAINT fk_assign_developer FOREIGN KEY (emp_id)     REFERENCES developer (emp_id),
  CONSTRAINT fk_assign_role      FOREIGN KEY (role_id)    REFERENCES job_role (role_id),
  -- [성능 향상 기법] 시점 질의(start_date <= :d AND end_date >= :d) 용 커버링 인덱스 (실험: docs/06_성능향상기법_실험.md)
  INDEX idx_assignment_period (end_date, start_date, project_id, emp_id, role_id, participation_rate),
  CONSTRAINT chk_assign_period CHECK (start_date <= end_date),
  CONSTRAINT chk_assign_rate   CHECK (participation_rate BETWEEN 10 AND 100)
) COMMENT='프로젝트 투입 (개발자:프로젝트 M:N 해소, 투입 이력 보존)';

-- ---------------------------------------------------------------------
-- 5. 프로젝트 평가 (슈퍼타입) / 고객·PM·동료 평가 (서브타입) / 항목·상세
-- ---------------------------------------------------------------------
CREATE TABLE evaluation (
  eval_id          INT          NOT NULL AUTO_INCREMENT COMMENT '평가 ID (PK)',
  project_id       INT          NOT NULL COMMENT '대상 프로젝트 (FK)',
  evaluatee_emp_id INT          NOT NULL COMMENT '피평가자 (FK → developer)',
  eval_type        ENUM('CUSTOMER','PM','PEER') NOT NULL COMMENT '서브타입 판별자 (고객 / PM / 동료 평가)',
  status           ENUM('REQUESTED','SUBMITTED','REPORTED') NOT NULL DEFAULT 'SUBMITTED' COMMENT '상태 (REQUESTED=의뢰됨, SUBMITTED=제출, REPORTED=회사 보고 완료)',
  eval_date        DATE         NULL     COMMENT '평가 제출일',
  overall_comment  VARCHAR(500) NULL     COMMENT '총평',
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
  PRIMARY KEY (eval_id),
  CONSTRAINT fk_eval_project   FOREIGN KEY (project_id)       REFERENCES project (project_id),
  CONSTRAINT fk_eval_evaluatee FOREIGN KEY (evaluatee_emp_id) REFERENCES developer (emp_id)
) COMMENT='프로젝트 평가 (슈퍼타입)';

CREATE TABLE customer_eval (
  eval_id             INT      NOT NULL COMMENT '평가 ID (PK, FK → evaluation)',
  contact_id          INT      NOT NULL COMMENT '평가자: 발주처 담당자 (FK → client_contact)',
  requested_by_emp_id INT      NOT NULL COMMENT '평가 의뢰 PM (FK → developer)',
  requested_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '의뢰일시',
  access_token        CHAR(32) NOT NULL COMMENT '고객 평가 입력용 외부 링크 토큰',
  reported_at         DATETIME NULL     COMMENT 'PM 의 회사 보고일시',
  PRIMARY KEY (eval_id),
  UNIQUE KEY uk_custeval_token (access_token),
  CONSTRAINT fk_custeval_eval    FOREIGN KEY (eval_id)             REFERENCES evaluation (eval_id) ON DELETE CASCADE,
  CONSTRAINT fk_custeval_contact FOREIGN KEY (contact_id)          REFERENCES client_contact (contact_id),
  CONSTRAINT fk_custeval_pm      FOREIGN KEY (requested_by_emp_id) REFERENCES developer (emp_id)
) COMMENT='고객 평가 (평가 서브타입: 발주처 담당자 → 참여 직원)';

CREATE TABLE pm_eval (
  eval_id             INT        NOT NULL COMMENT '평가 ID (PK, FK → evaluation)',
  evaluator_emp_id    INT        NOT NULL COMMENT '평가자: 해당 프로젝트 PM (FK → developer)',
  recommend_incentive TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'PM 의 인센티브 추천 여부',
  PRIMARY KEY (eval_id),
  CONSTRAINT fk_pmeval_eval      FOREIGN KEY (eval_id)          REFERENCES evaluation (eval_id) ON DELETE CASCADE,
  CONSTRAINT fk_pmeval_evaluator FOREIGN KEY (evaluator_emp_id) REFERENCES developer (emp_id)
) COMMENT='PM 평가 (평가 서브타입: PM → 팀원)';

CREATE TABLE peer_eval (
  eval_id          INT        NOT NULL COMMENT '평가 ID (PK, FK → evaluation)',
  evaluator_emp_id INT        NOT NULL COMMENT '평가자: 동일 프로젝트 참여 동료 (FK → developer)',
  is_anonymous     TINYINT(1) NOT NULL DEFAULT 1 COMMENT '피평가자에게 익명 처리 여부',
  PRIMARY KEY (eval_id),
  CONSTRAINT fk_peereval_eval      FOREIGN KEY (eval_id)          REFERENCES evaluation (eval_id) ON DELETE CASCADE,
  CONSTRAINT fk_peereval_evaluator FOREIGN KEY (evaluator_emp_id) REFERENCES developer (emp_id)
) COMMENT='동료 평가 (평가 서브타입: 참여자 → 자기 외 참여자)';

CREATE TABLE eval_item (
  item_id     INT          NOT NULL AUTO_INCREMENT COMMENT '평가 항목 ID (PK)',
  item_code   VARCHAR(20)  NOT NULL COMMENT '항목 코드 (WORK=업무수행, COMM=커뮤니케이션)',
  item_name   VARCHAR(50)  NOT NULL COMMENT '항목명',
  description VARCHAR(200) NULL     COMMENT '평가 기준 설명',
  weight      DECIMAL(3,2) NOT NULL DEFAULT 1.00 COMMENT '항목 가중치 (평점 평균 산출 시 사용)',
  is_active   TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '사용 여부',
  PRIMARY KEY (item_id),
  UNIQUE KEY uk_evalitem_code (item_code)
) COMMENT='평가 항목';

CREATE TABLE eval_detail (
  eval_id INT          NOT NULL COMMENT '평가 (FK → evaluation)',
  item_id INT          NOT NULL COMMENT '평가 항목 (FK → eval_item)',
  score   TINYINT      NOT NULL COMMENT '평점 (1~5)',
  comment VARCHAR(500) NULL     COMMENT '평가 내용',
  PRIMARY KEY (eval_id, item_id),
  CONSTRAINT fk_evaldetail_eval FOREIGN KEY (eval_id) REFERENCES evaluation (eval_id) ON DELETE CASCADE,
  CONSTRAINT fk_evaldetail_item FOREIGN KEY (item_id) REFERENCES eval_item (item_id),
  CONSTRAINT chk_evaldetail_score CHECK (score BETWEEN 1 AND 5)
) COMMENT='평가 상세 (항목별 평점·평가 내용)';

CREATE TABLE eval_type_weight (
  eval_type   ENUM('CUSTOMER','PM','PEER') NOT NULL COMMENT '평가 유형 (PK)',
  weight      DECIMAL(3,2) NOT NULL COMMENT '인센티브 종합점수 산정 가중치 (합계 1.00)',
  description VARCHAR(100) NULL     COMMENT '설명',
  PRIMARY KEY (eval_type)
) COMMENT='평가 유형별 가중치 (인센티브 정책 파라미터)';

-- ---------------------------------------------------------------------
-- 6. 기술등급 변경 이력 (경력관리)
-- ---------------------------------------------------------------------
CREATE TABLE grade_history (
  history_id        INT          NOT NULL AUTO_INCREMENT COMMENT '이력 ID (PK)',
  emp_id            INT          NOT NULL COMMENT '개발자 (FK → developer)',
  old_grade         ENUM('초급','중급','고급','특급') NULL     COMMENT '변경 전 등급',
  new_grade         ENUM('초급','중급','고급','특급') NOT NULL COMMENT '변경 후 등급',
  changed_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '변경일시',
  changed_by_emp_id INT          NULL     COMMENT '변경 처리자 (FK → employee, 경영진)',
  reason            VARCHAR(200) NULL     COMMENT '변경 사유',
  PRIMARY KEY (history_id),
  CONSTRAINT fk_gradehist_developer FOREIGN KEY (emp_id)            REFERENCES developer (emp_id) ON DELETE CASCADE,
  CONSTRAINT fk_gradehist_changer   FOREIGN KEY (changed_by_emp_id) REFERENCES employee (emp_id)
) COMMENT='기술등급 변경 이력 (AFTER UPDATE 트리거 자동 기록)';
