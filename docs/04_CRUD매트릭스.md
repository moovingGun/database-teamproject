# CRUD Matrix (상관 모델링)

> 2차 산출물. 행 = 업무 기능(프로세스, 구현 모듈), 열 = 엔티티. C 생성 · R 조회 · U 수정 · D 삭제.
> 모든 엔티티가 최소 1개 기능에서 C 되고 1개 이상에서 R 되는지(고아 엔티티 없음), 모든 기능이 1개 이상 엔티티를 사용하는지 검증하였다.

| 기능 \ 엔티티 | CLIENT | CLIENT_CONTACT | EMPLOYEE | DEVELOPER | STAFF | USER_ACCOUNT | SKILL | EMPLOYEE_SKILL | PROJECT | PROJECT_SKILL | JOB_ROLE | ASSIGNMENT | EVALUATION | CUSTOMER_EVAL | PM_EVAL | PEER_EVAL | EVAL_ITEM | EVAL_DETAIL | EVAL_TYPE_WEIGHT | GRADE_HISTORY | SEQ_COUNTER |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| F01 회원가입 (`auth.signup`) | | | **C** | **C** | **C** | **C** R | | | | | | | | | | | | | | | C U |
| F02 로그인 ID 중복확인 (`auth.check_id`) | | | | | | R | | | | | | | | | | | | | | | |
| F03 로그인/로그아웃 (`auth.login`) | | | R | | | R U | | | | | | | | | | | | | | | |
| F04 내 정보 조회 (`employees.detail`) | | | R | R | R | R | R | R | R | | R | R | R | | | | | R | R | R | |
| F05 내 정보 수정 (`employees.edit_me`) | | | R U | U | U | U | | | | | | | | | | | | | | | |
| F06 보유 기술 관리 (`employees.my_skills`) | | | | | | | R | C R U D | | | | | | | | | | | | | |
| F07 직원 검색 ★경영진 (`employees.search`) | | | R | R | R | R | R | R | R | | | R | | | | | | | | | |
| F08 직원 상세·경력 조회 ★ (`employees.detail`) | R | | R | R | R | R | R | R | R | | R | R | R | | | | | R | R | R | |
| F09 기술등급 변경 ★ (`employees.change_grade`) | | | | U | | | | | | | | | | | | | | | | C(트리거) | |
| F10 프로젝트 목록/상세 (`projects.index/detail`) | R | R | R | R | | | R | | R | R | R | R | R | R | | | | | | | |
| F11 프로젝트 등록 ★ (`projects.new`) | R | | | | | | R | | **C** | **C** | | | | | | | | | | | C U |
| F12 프로젝트 상태 변경 ★ (`projects.change_status`) | | | | | | | | | U | | | U D | | | | | | | | | |
| F13 투입 등록 ★ (`projects.add_assignment`) | | | R | R | | | | | R | | R | **C** | | | | | | | | | |
| F14 투입 조기 철수 ★ (`projects.end_assignment`) | | | | | | | | | R | | | U | | | | | | | | | |
| F15 평가 할 일 조회 (`evaluations.tasks`) | | R | R | | | | | | R | | R | R | R | R | R | R | | R | R | | |
| F16 PM 평가 입력 (`evaluations.new`, PM) | | | R | R | | | | | R | | R | R | **C** | | **C** | | R | **C** | | | |
| F17 동료 평가 입력 (`evaluations.new`, PEER) | | | R | R | | | | | R | | R | R | **C** | | | **C** | R | **C** | | | |
| F18 고객 평가 의뢰 (`evaluations.request_customer`) | | R | | | | | | | R | | R | R | **C** | **C** | | | | | | | |
| F19 고객 평가서 작성·제출 (외부, `customer_form`) | R | R | R | | | | | | R | | R | R | R U | R | | | R | **C** | | | |
| F20 고객 평가 결과 보고 (`report_customer`) | | | | | | | | | | | | | U | U | | | | | | | |
| F21 대시보드 — 현재 투입 현황 ★ S1 (`reports.index`) | R | | R | R | | | | | R | | R | R | R | | | | | | | | |
| F22 시점별 투입 현황 ★ S2 (`reports.staffing`) | R | | R | R | | | | | R | | R | R | | | | | | | | | |
| F23 평가 결과 리포트 ★ S4 (`reports.evaluations`) | | R | R | R | | | | | R | | | | R | R | R | R | R | R | R | | |
| F24 인센티브 기초자료 ★ S5 (`reports.incentive`) | | | R | R | | | | | R | | | | R | | R | | R | R | R | | |
| F25 기준 데이터 적재 (SQL, UI 생략) | **C** | **C** | | | | | **C** | | | | **C** | | | | | | **C** | | **C** | | |

★ = 경영진(EXECUTIVE) 전용 기능 · S1~S5 = 데모 시나리오 번호

## 검증 결과

| 검증 항목 | 결과 |
|---|---|
| 모든 엔티티에 C 가 존재하는가 | 예 — 마스터/정책 테이블(CLIENT, CLIENT_CONTACT, SKILL, JOB_ROLE, EVAL_ITEM, EVAL_TYPE_WEIGHT)은 F25(SQL 적재)에서 C, GRADE_HISTORY·SEQ_COUNTER 는 트리거가 C |
| 모든 엔티티에 R 이 존재하는가 | 예 |
| D 가 없는 엔티티 | 이력·평가·투입 데이터는 업무상 삭제하지 않고 상태/종료일로 관리(감사 추적). EMPLOYEE 는 status=RESIGNED 로 논리 삭제 |
| UI 없이 SQL 로만 관리되는 엔티티 | CLIENT, CLIENT_CONTACT, SKILL, JOB_ROLE, EVAL_ITEM, EVAL_TYPE_WEIGHT → 요구사항 2-4) 에 따라 `db/init/03_seed.sql` 로 적재하여 데모 |

## 조별 특화 시나리오 기능 × 엔티티

| 기능 \ 엔티티 | PROJECT | CLIENT_CONTACT | ASSIGNMENT | EMPLOYEE/DEVELOPER | STAFF | EVALUATION·EVAL_DETAIL | SKILL | CHANGE_REQUEST | CHANGE_REVIEW | CHANGE_HISTORY | TRAINING_COURSE | TRAINING_SESSION | DEVELOPMENT_PLAN | TRAINING_ENROLLMENT |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| A1 변경요청 접수 (PM) | R | R | R | R | | | | **C** | | | | | | |
| A2 검토안 작성 (PM) | R | | R | R | | | | R U(트리거) | **C** | | | | | |
| A3 내부 승인·반려 ★ | | | | R | | | | U(트리거) | **U** | | | | | |
| A4 고객 동의 기록 (PM) | R | R | | | | | | U(트리거) | **U** | | | | | |
| A5 계획 반영 (PM·경영진) | **U** | | R | R | | | | U(트리거) | R | **C** | | | | |
| A6 변경요청 현황 ★ S7 | R | R | | R | | | | R | R | R | | | | |
| B1 검토 대상 조회 (담당자) | R | | R | R | | R | R | | | | | | R | |
| B2 역량개선계획 수립 (담당자) | R | | R | R | R | R | R | | | | R | | **C** | |
| B3 교육 신청·취소 (직원) | | | | R | | | | | | | R | R | R | **C U** |
| B4 수료·미수료 기록 (담당자) | | | | R | | | | | | | R | R | R | **U** |
| B5 교육 이수 현황 ★ S8 | R | | | R | R | R | R | | | | R | R | R | R |
| 기준 데이터 적재 (SQL) | | | | | U | | | | | | **C** | **C** | | |

검증: 신규 엔티티 7개 모두 C·R 이 있고, 이력성 데이터(CHANGE_HISTORY, TRAINING_ENROLLMENT)는 삭제하지 않는다(취소·미수료도 상태로 보존).
