"""
11/09 설계 보고 산출물(엑셀) 생성 — 교수님 예시 양식 파일을 그대로 열어 표 안의 내용만 채운다
  .venv/bin/python scripts/build_design_xlsx.py <산출물 예시 폴더> docs/

  <예시 폴더>/03-2_표준용어-도메인-코드정의서(예시).xlsx → docs/03-2_표준용어-도메인-코드정의서.xlsx
  <예시 폴더>/03-1_CRUD_매트릭스(예시).xlsx             → docs/03-1_CRUD_매트릭스.xlsx

* 표준용어·도메인·코드: 실제 DB(information_schema) 의 28개 테이블 184개 컬럼에서 생성.
  논리명(한글)은 아래 TERM 표, 물리명(영문)은 DB 컬럼명. 코드는 ENUM 컬럼과 코드 테이블(직무·평가항목)에서.
* CRUD 매트릭스: 행 = 단위 프로세스(docs/04_CRUD매트릭스.md 와 동일), 열 = 엔터티 28개(한글 논리명).
* 예시의 서식(글꼴·테두리·채우기·병합)은 예시 셀에서 복사한다.
"""
import os
import sys
from copy import copy
from pathlib import Path

import openpyxl
import pymysql
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

sample_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
conn = pymysql.connect(host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
                       user=os.environ.get("DB_ADMIN_USER", "root"), password=os.environ.get("DB_ADMIN_PASSWORD", "root1234"),
                       database="information_schema", charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("""SELECT c.table_name t, c.column_name c, c.column_type ty, c.is_nullable n, c.column_key k, c.column_comment cm, t.table_comment tc
               FROM columns c JOIN tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
               WHERE c.table_schema = 'si_pms' AND t.table_type = 'BASE TABLE' ORDER BY c.table_name, c.ordinal_position""")
COLS = cur.fetchall()
cur.execute("SELECT role_code, role_name FROM si_pms.job_role ORDER BY sort_order")
ROLES = cur.fetchall()
cur.execute("SELECT item_code, item_name FROM si_pms.eval_item ORDER BY item_id")
ITEMS = cur.fetchall()


def clone(dst, src):
    dst.font, dst.border, dst.alignment, dst.fill, dst.number_format = copy(src.font), copy(src.border), copy(src.alignment), copy(src.fill), src.number_format


# =====================================================================================
#  엔터티 한글 논리명 (CRUD 열 · 표준용어의 엔터티 용어)
# =====================================================================================
ENTITY = {  # 물리명: (논리명, 업무 영역)
    "employee": ("직원", "인사"), "developer": ("개발자", "인사"), "staff": ("지원직", "인사"), "user_account": ("로그인계정", "인사"),
    "skill": ("기술", "인사"), "employee_skill": ("보유기술", "인사"), "grade_history": ("기술등급이력", "인사"),
    "client": ("발주처", "프로젝트"), "client_contact": ("발주처담당자", "프로젝트"), "project": ("프로젝트", "프로젝트"),
    "project_skill": ("프로젝트요구기술", "프로젝트"), "job_role": ("직무", "프로젝트"), "assignment": ("프로젝트투입", "프로젝트"),
    "evaluation": ("프로젝트평가", "평가"), "customer_eval": ("고객평가", "평가"), "pm_eval": ("PM평가", "평가"), "peer_eval": ("동료평가", "평가"),
    "eval_item": ("평가항목", "평가"), "eval_detail": ("평가상세", "평가"), "eval_type_weight": ("평가유형가중치", "평가"),
    "change_request": ("변경요청", "변경요청"), "change_review": ("변경검토안", "변경요청"), "change_history": ("변경적용이력", "변경요청"),
    "training_course": ("교육과정", "교육"), "training_session": ("교육일정", "교육"), "development_plan": ("역량개선계획", "교육"),
    "training_enrollment": ("교육신청", "교육"), "seq_counter": ("채번카운터", "시스템"),
}
AREAS = ["인사", "프로젝트", "평가", "변경요청", "교육", "시스템"]
assert set(ENTITY) == {r["t"] for r in COLS}, set(ENTITY) ^ {r["t"] for r in COLS}

# =====================================================================================
#  표준용어: 컬럼 → (한글 용어, 설명).  테이블마다 뜻이 다른 컬럼은 "table.column" 으로 따로 둔다
# =====================================================================================
TERM = {
    # 식별자
    "client_id": ("발주처일련번호", "발주처를 식별하는 일련번호"), "contact_id": ("발주처담당자일련번호", "발주처 담당자를 식별하는 일련번호"),
    "emp_id": ("직원일련번호", "직원을 식별하는 내부 일련번호 (사번과 별도)"), "skill_id": ("기술일련번호", "기술을 식별하는 일련번호"),
    "project_id": ("프로젝트일련번호", "프로젝트를 식별하는 내부 일련번호 (프로젝트번호와 별도)"), "role_id": ("직무일련번호", "직무를 식별하는 일련번호"),
    "assignment_id": ("투입일련번호", "프로젝트 투입 건을 식별하는 일련번호"), "eval_id": ("평가일련번호", "평가 건을 식별하는 일련번호"),
    "item_id": ("평가항목일련번호", "평가 항목을 식별하는 일련번호"), "history_id": ("이력일련번호", "이력 행을 식별하는 일련번호"),
    "cr_id": ("변경요청일련번호", "변경요청을 식별하는 내부 일련번호 (요청번호와 별도)"), "review_id": ("검토안일련번호", "변경 검토안을 식별하는 일련번호"),
    "course_id": ("교육과정일련번호", "교육과정을 식별하는 일련번호"), "session_id": ("교육일정일련번호", "교육일정을 식별하는 일련번호"),
    "plan_id": ("역량개선계획일련번호", "역량개선계획을 식별하는 일련번호"), "enroll_id": ("교육신청일련번호", "교육 신청 건을 식별하는 일련번호"),
    # 직원
    "emp_no": ("직원번호", "사번. E + 입사연도 2자리 + 연도별 순번 4자리, 시스템이 자동 부여"), "emp_name": ("직원명", "직원의 이름"),
    "resident_reg_no": ("주민등록번호", "직원의 주민등록번호 (화면에서는 뒷자리 마스킹)"), "education_level": ("최종학력코드", "직원의 최종 학력 구분"),
    "hire_date": ("입사일자", "직원의 입사일"), "emp_type": ("직원구분코드", "개발자 / 지원직 구분 (서브타입 판별자)"),
    "email": ("이메일", "이메일 주소"), "phone": ("전화번호", "연락처 전화번호"), "employee.status": ("재직상태코드", "재직 / 휴직 / 퇴직 구분"),
    "created_at": ("등록일시", "행이 등록된 일시"), "updated_at": ("수정일시", "행이 마지막으로 수정된 일시"),
    "skill_grade": ("기술등급코드", "개발자의 기술 등급 (초급 / 중급 / 고급 / 특급)"), "career_start_date": ("경력기산일자", "개발 경력을 세기 시작하는 날짜 (입사 전 경력 포함)"),
    "grade_updated_at": ("기술등급변경일자", "기술 등급이 마지막으로 바뀐 날짜"), "department": ("부서코드", "지원직의 부서 구분 (마케팅 / 경영관리 / 연구개발)"),
    "job_title": ("직책", "지원직의 직책"), "is_training_manager": ("교육담당자여부", "교육 담당자로 지정된 지원직인지 여부"),
    "login_id": ("로그인ID", "회원가입 시 정하는 로그인 아이디 (중복 불가)"), "password_hash": ("비밀번호해시", "비밀번호를 해시(PBKDF2-SHA256)한 값"),
    "auth_role": ("권한코드", "일반직원 / 경영진 권한 구분"), "user_account.is_active": ("계정활성여부", "로그인 계정의 활성 여부"),
    "last_login_at": ("최근로그인일시", "마지막으로 로그인한 일시"),
    # 기술
    "skill_name": ("기술명", "기술(Skill Set)의 이름"), "category": ("기술분류코드", "기술의 분류 (언어 / 프레임워크 / DB / 클라우드 등)"),
    "proficiency": ("숙련도", "보유 기술의 숙련도 (1~5)"), "years_used": ("사용경력연수", "해당 기술을 사용한 경력 (년)"), "last_used_date": ("최근사용일자", "해당 기술을 마지막으로 사용한 날짜"),
    "old_grade": ("변경전기술등급코드", "변경 전 기술 등급"), "new_grade": ("변경후기술등급코드", "변경 후 기술 등급"),
    "changed_at": ("변경일시", "기술 등급이 변경된 일시"), "changed_by_emp_id": ("변경처리자직원일련번호", "기술 등급을 변경한 경영진 직원"),
    "grade_history.reason": ("변경사유", "기술 등급 변경 사유"),
    # 발주처 · 프로젝트
    "client_name": ("발주처명", "발주처(고객사)의 이름"), "business_reg_no": ("사업자등록번호", "발주처의 사업자등록번호"), "industry": ("업종", "발주처의 업종"),
    "address": ("주소", "발주처의 주소"), "contact_name": ("담당자명", "발주처 담당자의 이름"), "position": ("직위", "발주처 담당자의 직위"),
    "client_contact.is_active": ("담당자재직여부", "발주처 담당자의 재직 여부"),
    "project_code": ("프로젝트번호", "P + 착수연도 4자리 + '-' + 순번 3자리, 시스템이 자동 부여"), "project_name": ("프로젝트명", "프로젝트의 이름"),
    "project.start_date": ("착수일자", "프로젝트 착수일"), "project.end_date": ("종료예정일자", "계약상 종료 예정일 (변경요청 반영 시에만 변경)"),
    "actual_end_date": ("실제종료일자", "프로젝트를 실제로 종료 처리한 날짜"), "project.status": ("프로젝트상태코드", "예정 / 진행중 / 종료 / 취소 구분"),
    "contract_amount": ("계약금액", "프로젝트 계약 금액 (원)"), "project.description": ("프로젝트개요", "프로젝트 개요 설명"),
    "required_level": ("요구숙련도", "프로젝트가 요구하는 기술 숙련도 (1~5)"),
    "role_code": ("직무코드", "직무를 나타내는 코드 (PM, PL, ANALYST …)"), "role_name": ("직무명", "직무의 이름"),
    "min_grade": ("최소기술등급코드", "해당 직무를 맡기 위한 최소 기술 등급"), "sort_order": ("표시순서", "화면 표시 순서"),
    "assignment.start_date": ("투입시작일자", "프로젝트 투입 시작일"), "assignment.end_date": ("투입종료일자", "프로젝트 투입 종료일"),
    "participation_rate": ("투입률", "투입 비율 (%). 같은 기간 개인 합계 100% 이하"), "note": ("비고", "비고"),
    # 평가
    "evaluatee_emp_id": ("피평가자직원일련번호", "평가를 받는 직원"), "eval_type": ("평가유형코드", "고객 / PM / 동료 평가 구분"),
    "evaluation.status": ("평가상태코드", "의뢰됨 / 제출 / 보고완료 구분"), "eval_date": ("평가일자", "평가를 제출한 날짜"), "overall_comment": ("총평", "평가 총평"),
    "requested_by_emp_id": ("의뢰PM직원일련번호", "고객 평가를 의뢰한 PM"), "requested_at": ("의뢰일시", "고객 평가를 의뢰한 일시"),
    "access_token": ("접속토큰", "고객 담당자가 로그인 없이 평가서에 접근하는 토큰"), "reported_at": ("보고일시", "PM 이 고객 평가 결과를 회사에 보고한 일시"),
    "evaluator_emp_id": ("평가자직원일련번호", "평가를 하는 직원 (PM 또는 동료)"), "recommend_incentive": ("인센티브추천여부", "PM 의 인센티브 추천 여부"),
    "is_anonymous": ("익명여부", "피평가자에게 평가자를 익명으로 처리할지 여부"),
    "item_code": ("평가항목코드", "평가 항목 코드 (WORK=업무수행, COMM=커뮤니케이션)"), "item_name": ("평가항목명", "평가 항목의 이름"),
    "eval_item.description": ("평가기준설명", "평가 항목의 평가 기준 설명"), "eval_item.weight": ("평가항목가중치", "항목 평점 평균 산출 시 가중치"),
    "eval_item.is_active": ("평가항목사용여부", "평가 항목의 사용 여부"), "score": ("평점", "평가 항목의 평점 (1~5)"), "comment": ("평가내용", "평가 항목에 대한 서술 평가"),
    "eval_type_weight.weight": ("평가유형가중치", "인센티브 종합점수 산정 시 평가 유형별 가중치 (합계 1)"), "eval_type_weight.description": ("가중치설명", "가중치 설명"),
    # 변경요청
    "cr_no": ("변경요청번호", "CR + 요청연도 4자리 + '-' + 순번 3자리, 시스템이 자동 부여"), "change_request.contact_id": ("요청담당자일련번호", "변경을 요청한 발주처 담당자"),
    "received_by_emp_id": ("접수PM직원일련번호", "변경요청을 접수한 PM"), "request_date": ("요청일자", "변경요청을 받은 날짜"),
    "title": ("요청제목", "변경요청 제목"), "content": ("요청내용", "변경요청 내용"), "change_request.reason": ("요청사유", "변경을 요청한 사유"),
    "change_request.status": ("변경요청상태코드", "접수 / 검토중 / 승인 / 동의 / 반영 / 반려 / 거절 구분"),
    "version_no": ("검토차수", "검토안 차수 (재검토 시 증가)"), "reviewer_emp_id": ("검토PM직원일련번호", "영향 분석을 작성한 PM"),
    "proposed_end_date": ("제안종료예정일자", "검토안이 제안하는 종료 예정일"), "additional_amount": ("추가계약금액", "추가 계약 금액 (원, 감액은 음수)"),
    "review_comment": ("검토의견", "영향 분석 의견"), "reviewed_at": ("검토일시", "검토안 작성 일시"), "decision": ("내부결정코드", "경영진 내부 결정 (대기 / 승인 / 반려)"),
    "decided_by_emp_id": ("결정자직원일련번호", "승인·반려를 결정한 경영진"), "decided_at": ("결정일자", "내부 결정 날짜"), "decision_reason": ("결정사유", "승인·반려 사유"),
    "consent": ("고객동의코드", "고객사 동의 (대기 / 동의 / 거절)"), "consent_contact_id": ("동의담당자일련번호", "동의한 발주처 담당자"),
    "consent_date": ("고객확인일자", "고객이 동의를 확인한 날짜"), "consent_evidence": ("확인근거", "동의 확인 근거 (이메일, 회의록 등)"),
    "consent_recorded_by": ("동의기록자직원일련번호", "고객 동의를 기록한 직원"),
    "before_end_date": ("변경전종료예정일자", "변경 반영 전 종료 예정일"), "after_end_date": ("변경후종료예정일자", "변경 반영 후 종료 예정일"),
    "before_amount": ("변경전계약금액", "변경 반영 전 계약 금액"), "after_amount": ("변경후계약금액", "변경 반영 후 계약 금액"),
    "applied_by_emp_id": ("반영자직원일련번호", "변경을 계획에 반영한 직원"), "change_history.applied_at": ("반영일시", "변경을 반영한 일시"),
    # 교육
    "course_name": ("교육과정명", "교육과정의 이름"), "field": ("교육분야코드", "기술 / 의사소통 / 관리 / 품질 구분"),
    "training_course.skill_id": ("관련기술일련번호", "교육과정과 관련된 기술 (없으면 비움)"), "training_course.description": ("교육내용", "교육과정 내용 설명"),
    "start_at": ("시작일시", "교육 시작 일시"), "end_at": ("종료일시", "교육 종료 일시"), "place": ("교육장소", "교육이 열리는 장소"), "capacity": ("정원", "교육일정의 정원"),
    "development_plan.project_id": ("근거프로젝트일련번호", "계획의 근거가 된 종료 프로젝트"), "development_plan.course_id": ("추천교육과정일련번호", "추천한 교육과정"),
    "manager_emp_id": ("교육담당자직원일련번호", "계획을 수립한 교육 담당자"), "improvement_goal": ("개선목표", "역량 개선 목표"),
    "development_plan.reason": ("추천사유", "교육과정을 추천한 사유 (평가 내용·보유 기술 검토 결과)"), "created_date": ("수립일자", "계획을 수립한 날짜"),
    "due_date": ("이수목표일자", "교육 이수 목표일"), "training_enrollment.applied_at": ("신청일시", "교육을 신청한 일시"),
    "training_enrollment.status": ("교육신청상태코드", "신청 / 취소 / 수료 / 미수료 구분"), "attended": ("출석여부", "교육 출석 여부"),
    "processed_at": ("처리일시", "취소 또는 수료를 처리한 일시"),
    # 시스템
    "seq_name": ("채번대상명", "자동 채번 대상 (사번 / 프로젝트번호 / 변경요청번호)"), "seq_year": ("채번기준연도", "채번 기준 연도"), "last_seq": ("최종발급순번", "마지막으로 발급한 순번"),
}


def term_of(r):
    return TERM.get(f"{r['t']}.{r['c']}") or TERM[r["c"]]


for r in COLS:
    term_of(r)   # 빠진 컬럼이 있으면 KeyError 로 바로 알 수 있게

# =====================================================================================
#  표준단어사전: 용어를 이루는 단어와 영문 약어 (물리 컬럼명과 일치)
# =====================================================================================
WORDS = [  # (단어, 영문약어, 영문명, 구분, 관련표준어)
    ("직원", "EMP", "employee", "표준용어", ""), ("개발자", "DEV", "developer", "표준용어", ""), ("지원직", "STAFF", "staff", "표준용어", ""),
    ("발주처", "CLIENT", "client", "표준용어", ""), ("고객사", "CLIENT", "client", "동의어", "발주처"), ("담당자", "CONTACT", "contact", "표준용어", ""),
    ("프로젝트", "PROJECT", "project", "표준용어", ""), ("기술", "SKILL", "skill", "표준용어", ""), ("직무", "ROLE", "role", "표준용어", ""),
    ("투입", "ASSIGN", "assignment", "표준용어", ""), ("배정", "ASSIGN", "assignment", "동의어", "투입"), ("평가", "EVAL", "evaluation", "표준용어", ""),
    ("고객", "CUSTOMER", "customer", "표준용어", ""), ("동료", "PEER", "peer", "표준용어", ""), ("항목", "ITEM", "item", "표준용어", ""),
    ("상세", "DETAIL", "detail", "표준용어", ""), ("변경요청", "CR", "change request", "표준용어", ""), ("검토안", "REVIEW", "review", "표준용어", ""),
    ("교육과정", "COURSE", "course", "표준용어", ""), ("교육일정", "SESSION", "session", "표준용어", ""), ("역량개선계획", "PLAN", "development plan", "표준용어", ""),
    ("교육신청", "ENROLL", "enrollment", "표준용어", ""), ("계정", "ACCOUNT", "account", "표준용어", ""), ("로그인", "LOGIN", "login", "표준용어", ""),
    ("일련번호", "ID", "identifier", "표준용어", ""), ("번호", "NO", "number", "표준용어", ""), ("명", "NAME", "name", "표준용어", ""),
    ("이름", "NAME", "name", "동의어", "명"), ("코드", "CODE", "code", "표준용어", ""), ("구분", "TYPE", "type", "표준용어", ""),
    ("상태", "STATUS", "status", "표준용어", ""), ("일자", "DATE", "date", "표준용어", ""), ("일시", "AT", "datetime", "표준용어", ""),
    ("여부", "IS", "is (true / false)", "표준용어", ""), ("주민등록번호", "RRN", "resident registration number", "표준용어", ""),
    ("사업자등록번호", "BREG_NO", "business registration number", "표준용어", ""), ("최종학력", "EDU_LEVEL", "education level", "표준용어", ""),
    ("입사", "HIRE", "hire", "표준용어", ""), ("이메일", "EMAIL", "email", "표준용어", ""), ("전화번호", "PHONE", "phone", "표준용어", ""),
    ("주소", "ADDR", "address", "표준용어", ""), ("업종", "INDUSTRY", "industry", "표준용어", ""), ("직위", "POSITION", "position", "표준용어", ""),
    ("직책", "JOB_TITLE", "job title", "표준용어", ""), ("부서", "DEPT", "department", "표준용어", ""), ("재직", "ACTIVE", "active", "표준용어", ""),
    ("등록", "CREATED", "created", "표준용어", ""), ("수정", "UPDATED", "updated", "표준용어", ""), ("변경", "CHANGE", "change", "표준용어", ""),
    ("이력", "HISTORY", "history", "표준용어", ""), ("등급", "GRADE", "grade", "표준용어", ""), ("경력", "CAREER", "career", "표준용어", ""),
    ("기산", "START", "start", "표준용어", ""), ("권한", "AUTH_ROLE", "authorization role", "표준용어", ""), ("비밀번호", "PASSWORD", "password", "표준용어", ""),
    ("해시", "HASH", "hash", "표준용어", ""), ("활성", "ACTIVE", "active", "표준용어", ""), ("최근", "LAST", "last", "표준용어", ""),
    ("분류", "CATEGORY", "category", "표준용어", ""), ("숙련도", "PROFICIENCY", "proficiency", "표준용어", ""), ("사용", "USED", "used", "표준용어", ""),
    ("연수", "YEARS", "years", "표준용어", ""), ("처리자", "BY", "processed by", "표준용어", ""), ("사유", "REASON", "reason", "표준용어", ""),
    ("착수", "START", "start", "표준용어", ""), ("종료", "END", "end", "표준용어", ""), ("예정", "PLANNED", "planned", "표준용어", ""),
    ("실제", "ACTUAL", "actual", "표준용어", ""), ("계약", "CONTRACT", "contract", "표준용어", ""), ("금액", "AMOUNT", "amount", "표준용어", ""),
    ("개요", "DESCRIPTION", "description", "표준용어", ""), ("설명", "DESCRIPTION", "description", "동의어", "개요"), ("요구", "REQUIRED", "required", "표준용어", ""),
    ("최소", "MIN", "minimum", "표준용어", ""), ("표시", "SORT", "sort", "표준용어", ""), ("순서", "ORDER", "order", "표준용어", ""),
    ("시작", "START", "start", "표준용어", ""), ("투입률", "PARTICIPATION_RATE", "participation rate", "표준용어", ""), ("비고", "NOTE", "note", "표준용어", ""),
    ("피평가자", "EVALUATEE", "evaluatee", "표준용어", ""), ("평가자", "EVALUATOR", "evaluator", "표준용어", ""), ("유형", "TYPE", "type", "동의어", "구분"),
    ("제출", "SUBMITTED", "submitted", "표준용어", ""), ("총평", "OVERALL_COMMENT", "overall comment", "표준용어", ""), ("의뢰", "REQUESTED", "requested", "표준용어", ""),
    ("접속토큰", "ACCESS_TOKEN", "access token", "표준용어", ""), ("보고", "REPORTED", "reported", "표준용어", ""), ("인센티브", "INCENTIVE", "incentive", "표준용어", ""),
    ("추천", "RECOMMEND", "recommend", "표준용어", ""), ("익명", "ANONYMOUS", "anonymous", "표준용어", ""), ("가중치", "WEIGHT", "weight", "표준용어", ""),
    ("기준", "CRITERIA", "criteria", "표준용어", ""), ("평점", "SCORE", "score", "표준용어", ""), ("내용", "CONTENT", "content", "표준용어", ""),
    ("요청", "REQUEST", "request", "표준용어", ""), ("접수", "RECEIVED", "received", "표준용어", ""), ("제목", "TITLE", "title", "표준용어", ""),
    ("차수", "VERSION_NO", "version number", "표준용어", ""), ("검토", "REVIEW", "review", "표준용어", ""), ("제안", "PROPOSED", "proposed", "표준용어", ""),
    ("추가", "ADDITIONAL", "additional", "표준용어", ""), ("의견", "COMMENT", "comment", "표준용어", ""), ("결정", "DECISION", "decision", "표준용어", ""),
    ("내부", "INTERNAL", "internal", "표준용어", ""), ("동의", "CONSENT", "consent", "표준용어", ""), ("확인", "CONFIRM", "confirm", "표준용어", ""),
    ("근거", "EVIDENCE", "evidence", "표준용어", ""), ("기록자", "RECORDED_BY", "recorded by", "표준용어", ""), ("반영", "APPLIED", "applied", "표준용어", ""),
    ("전", "BEFORE", "before", "표준용어", ""), ("후", "AFTER", "after", "표준용어", ""), ("교육", "TRAINING", "training", "표준용어", ""),
    ("분야", "FIELD", "field", "표준용어", ""), ("관련", "RELATED", "related", "표준용어", ""), ("장소", "PLACE", "place", "표준용어", ""),
    ("정원", "CAPACITY", "capacity", "표준용어", ""), ("개선", "IMPROVEMENT", "improvement", "표준용어", ""), ("목표", "GOAL", "goal", "표준용어", ""),
    ("수립", "CREATED", "created", "표준용어", ""), ("이수", "COMPLETED", "completed", "표준용어", ""), ("신청", "APPLIED", "applied", "표준용어", ""),
    ("출석", "ATTENDED", "attended", "표준용어", ""), ("처리", "PROCESSED", "processed", "표준용어", ""), ("취소", "CANCELLED", "cancelled", "표준용어", ""),
    ("채번", "SEQ", "sequence", "표준용어", ""), ("대상", "TARGET", "target", "표준용어", ""), ("연도", "YEAR", "year", "표준용어", ""),
    ("최종", "LAST", "last", "표준용어", ""), ("발급", "ISSUED", "issued", "표준용어", ""), ("순번", "SEQ", "sequence", "동의어", "일련번호"),
    ("PM", "PM", "project manager", "표준용어", ""), ("ID", "ID", "identifier", "표준용어", ""),
]

# =====================================================================================
#  표준코드: ENUM 컬럼과 코드 테이블
# =====================================================================================
CODES = [  # (코드 구분, [(한글명, 코드값), ...])
    ("직원 구분", [("개발자", "DEV"), ("지원직", "STAFF")]),
    ("재직상태 구분", [("재직", "ACTIVE"), ("휴직", "LEAVE"), ("퇴직", "RESIGNED")]),
    ("최종학력 구분", [("고졸", "고졸"), ("전문학사", "전문학사"), ("학사", "학사"), ("석사", "석사"), ("박사", "박사")]),
    ("권한 구분", [("일반직원", "EMPLOYEE"), ("경영진", "EXECUTIVE")]),
    ("기술등급 구분", [("초급", "초급"), ("중급", "중급"), ("고급", "고급"), ("특급", "특급")]),
    ("부서 구분", [("마케팅", "MARKETING"), ("경영관리", "MANAGEMENT"), ("연구개발", "RND")]),
    ("기술분류 구분", [("언어", "LANGUAGE"), ("프레임워크", "FRAMEWORK"), ("데이터베이스", "DATABASE"), ("클라우드", "CLOUD"), ("운영체제", "OS"), ("도구", "TOOL"), ("방법론", "METHOD")]),
    ("직무 코드", [(r["role_name"], r["role_code"]) for r in ROLES]),
    ("프로젝트상태 구분", [("예정", "PLANNED"), ("진행중", "IN_PROGRESS"), ("종료", "COMPLETED"), ("취소", "CANCELLED")]),
    ("평가유형 구분", [("고객 평가", "CUSTOMER"), ("PM 평가", "PM"), ("동료 평가", "PEER")]),
    ("평가상태 구분", [("의뢰됨", "REQUESTED"), ("제출", "SUBMITTED"), ("보고완료", "REPORTED")]),
    ("평가항목 코드", [(r["item_name"], r["item_code"]) for r in ITEMS]),
    ("변경요청상태 구분", [("접수", "RECEIVED"), ("검토중", "REVIEWING"), ("내부승인", "APPROVED"), ("고객동의", "AGREED"), ("반영", "APPLIED"), ("반려", "REJECTED"), ("고객거절", "DECLINED")]),
    ("내부결정 구분", [("대기", "PENDING"), ("승인", "APPROVED"), ("반려", "REJECTED")]),
    ("고객동의 구분", [("대기", "PENDING"), ("동의", "AGREED"), ("거절", "DECLINED")]),
    ("교육분야 구분", [("기술", "TECH"), ("의사소통", "COMM"), ("관리", "MGMT"), ("품질", "QUALITY")]),
    ("교육신청상태 구분", [("신청", "APPLIED"), ("취소", "CANCELLED"), ("수료", "COMPLETED"), ("미수료", "NOT_COMPLETED")]),
    ("채번대상 구분", [("사번", "EMP_NO"), ("프로젝트번호", "PROJECT_CODE"), ("변경요청번호", "CR_NO")]),
    ("여부 구분", [("예", "1"), ("아니오", "0")]),
]

# =====================================================================================
#  표준도메인: 대표 속성 → 물리 타입
# =====================================================================================
DOMAINS = [  # (구분, [(대표 속성, 물리 타입), ...])
    ("문자", [("직원번호", "CHAR(7)"), ("주민등록번호", "CHAR(14)"), ("사업자등록번호", "CHAR(12)"), ("접속토큰", "CHAR(32)"),
            ("프로젝트번호·변경요청번호", "VARCHAR(12)"), ("코드", "VARCHAR(10)~VARCHAR(20)"), ("로그인ID", "VARCHAR(30)"),
            ("명 (직원명·담당자명·기술명·직무명·항목명)", "VARCHAR(50)"), ("명 (발주처명·프로젝트명·교육과정명·제목·장소)", "VARCHAR(100)"),
            ("이메일", "VARCHAR(100)"), ("전화번호", "VARCHAR(20)"), ("주소", "VARCHAR(200)"), ("비밀번호해시", "VARCHAR(255)"),
            ("비고·목표·설명", "VARCHAR(200)"), ("내용·사유·총평·의견", "VARCHAR(500)~VARCHAR(1000)")]),
    ("구분코드", [("구분·상태·유형 (ENUM)", "ENUM('값1','값2',…)"), ("여부", "TINYINT(1)  (0 / 1)")]),
    ("번호", [("일련번호 (PK·FK)", "INT AUTO_INCREMENT"), ("평점·숙련도·투입률·차수·순서", "TINYINT"), ("정원·연도", "SMALLINT"), ("순번", "INT")]),
    ("금액·비율", [("계약금액·추가계약금액", "DECIMAL(15,0)"), ("사용경력연수", "DECIMAL(3,1)"), ("가중치", "DECIMAL(3,2)")]),
    ("일자", [("일자 (입사·착수·종료·요청·결정 …)", "DATE"), ("일시 (등록·수정·의뢰·보고·처리 …)", "DATETIME")]),
]

# =====================================================================================
#  CRUD 매트릭스: 단위 프로세스 × 엔터티 (docs/04_CRUD매트릭스.md 와 동일)
# =====================================================================================
PROCESSES = [  # (프로세스명, {물리 테이블명: "CRUD"})
    ("회원가입", {"employee": "C", "developer": "C", "staff": "C", "user_account": "CR", "seq_counter": "CRU"}),
    ("로그인 ID 중복확인", {"user_account": "R"}),
    ("로그인 / 로그아웃", {"employee": "R", "user_account": "RU"}),
    ("내 정보 조회", {"employee": "R", "developer": "R", "staff": "R", "user_account": "R", "skill": "R", "employee_skill": "R", "project": "R",
                 "job_role": "R", "assignment": "R", "evaluation": "R", "eval_detail": "R", "eval_type_weight": "R", "grade_history": "R"}),
    ("내 정보 수정", {"employee": "RU", "developer": "U", "staff": "U", "user_account": "U"}),
    ("보유 기술 등록·수정·삭제", {"skill": "R", "employee_skill": "CRUD"}),
    ("직원 검색 (경영진)", {"employee": "R", "developer": "R", "staff": "R", "user_account": "R", "skill": "R", "employee_skill": "R", "project": "R", "assignment": "R"}),
    ("직원 상세·경력 조회 (경영진)", {"client": "R", "employee": "R", "developer": "R", "staff": "R", "user_account": "R", "skill": "R", "employee_skill": "R",
                           "project": "R", "job_role": "R", "assignment": "R", "evaluation": "R", "eval_detail": "R", "eval_type_weight": "R", "grade_history": "R"}),
    ("기술등급 변경 (경영진)", {"developer": "U", "grade_history": "C"}),
    ("프로젝트 목록·상세 조회", {"client": "R", "client_contact": "R", "employee": "R", "developer": "R", "skill": "R", "project": "R", "project_skill": "R",
                       "job_role": "R", "assignment": "R", "evaluation": "R", "customer_eval": "R"}),
    ("프로젝트 등록 (경영진)", {"client": "R", "skill": "R", "project": "C", "project_skill": "C", "seq_counter": "CRU"}),
    ("프로젝트 상태 변경 (경영진)", {"project": "U", "assignment": "UD"}),
    ("투입 등록 (경영진)", {"employee": "R", "developer": "R", "project": "R", "job_role": "R", "assignment": "C"}),
    ("투입 조기 철수 (경영진)", {"project": "R", "assignment": "U"}),
    ("평가 할 일 조회", {"client_contact": "R", "employee": "R", "project": "R", "job_role": "R", "assignment": "R", "evaluation": "R",
                   "customer_eval": "R", "pm_eval": "R", "peer_eval": "R", "eval_detail": "R", "eval_type_weight": "R"}),
    ("PM 평가 입력", {"employee": "R", "developer": "R", "project": "R", "job_role": "R", "assignment": "R", "evaluation": "C", "pm_eval": "C", "eval_item": "R", "eval_detail": "C"}),
    ("동료 평가 입력", {"employee": "R", "developer": "R", "project": "R", "job_role": "R", "assignment": "R", "evaluation": "C", "peer_eval": "C", "eval_item": "R", "eval_detail": "C"}),
    ("고객 평가 의뢰 (PM)", {"client_contact": "R", "project": "R", "job_role": "R", "assignment": "R", "evaluation": "C", "customer_eval": "C"}),
    ("고객 평가서 작성·제출 (발주처 담당자)", {"client": "R", "client_contact": "R", "employee": "R", "project": "R", "job_role": "R", "assignment": "R",
                                  "evaluation": "RU", "customer_eval": "R", "eval_item": "R", "eval_detail": "C"}),
    ("고객 평가 결과 보고 (PM)", {"evaluation": "U", "customer_eval": "U"}),
    ("대시보드 · 현재 투입 현황 (S1)", {"client": "R", "employee": "R", "developer": "R", "project": "R", "job_role": "R", "assignment": "R", "evaluation": "R"}),
    ("시점별 투입 현황 (S2)", {"client": "R", "employee": "R", "developer": "R", "project": "R", "job_role": "R", "assignment": "R"}),
    ("평가 결과 리포트 (S4)", {"client_contact": "R", "employee": "R", "developer": "R", "project": "R", "evaluation": "R", "customer_eval": "R",
                       "pm_eval": "R", "peer_eval": "R", "eval_item": "R", "eval_detail": "R", "eval_type_weight": "R"}),
    ("인센티브 기초자료 (S5)", {"employee": "R", "developer": "R", "project": "R", "evaluation": "R", "pm_eval": "R", "eval_item": "R", "eval_detail": "R", "eval_type_weight": "R"}),
    ("변경요청 접수 (PM)", {"project": "R", "client_contact": "R", "assignment": "R", "employee": "R", "change_request": "C", "seq_counter": "CRU"}),
    ("변경 검토안 작성 (PM)", {"project": "R", "assignment": "R", "employee": "R", "change_request": "RU", "change_review": "C"}),
    ("변경 내부 승인·반려 (경영진)", {"employee": "R", "change_request": "U", "change_review": "U"}),
    ("변경 고객 동의 기록 (PM)", {"project": "R", "client_contact": "R", "change_request": "U", "change_review": "U"}),
    ("변경 계획 반영 (PM·경영진)", {"project": "U", "assignment": "R", "employee": "R", "change_request": "U", "change_review": "R", "change_history": "C"}),
    ("변경요청 처리 현황 (S7)", {"project": "R", "client_contact": "R", "employee": "R", "change_request": "R", "change_review": "R", "change_history": "R"}),
    ("역량개선 검토 대상 조회 (교육담당자)", {"project": "R", "assignment": "R", "employee": "R", "evaluation": "R", "eval_detail": "R", "skill": "R", "development_plan": "R"}),
    ("역량개선계획 수립 (교육담당자)", {"project": "R", "assignment": "R", "employee": "R", "staff": "R", "evaluation": "R", "eval_detail": "R", "skill": "R",
                           "training_course": "R", "development_plan": "C"}),
    ("교육 신청·취소 (직원)", {"employee": "R", "training_course": "R", "training_session": "R", "development_plan": "R", "training_enrollment": "CU"}),
    ("수료·미수료 기록 (교육담당자)", {"employee": "R", "training_course": "R", "training_session": "R", "development_plan": "R", "training_enrollment": "U"}),
    ("교육 이수 현황 (S8)", {"project": "R", "employee": "R", "staff": "R", "evaluation": "R", "skill": "R", "training_course": "R", "training_session": "R",
                      "development_plan": "R", "training_enrollment": "R"}),
    ("기준 데이터 적재 (SQL)", {"client": "C", "client_contact": "C", "skill": "C", "job_role": "C", "eval_item": "C", "eval_type_weight": "C",
                       "training_course": "C", "training_session": "C", "staff": "U"}),
]
for _, m in PROCESSES:
    assert set(m) <= set(ENTITY), set(m) - set(ENTITY)


# =====================================================================================
#  03-2 표준용어-도메인-코드정의서
# =====================================================================================
def build_standards():
    wb = openpyxl.load_workbook(sample_dir / "03-2_표준용어-도메인-코드정의서(예시).xlsx")
    assert wb.sheetnames == ["데이터 표준화 기본원칙", "표준용어", "표준단어사전", "표준코드", "표준도메인"], wb.sheetnames

    def reset(ws, first_row):
        """first_row 부터 아래 내용·병합을 모두 지우고, 데이터 행 서식 견본을 돌려준다"""
        for rng in list(ws.merged_cells.ranges):
            if rng.min_row >= first_row:
                ws.unmerge_cells(str(rng))
        styles = {c: copy(ws[f"{c}{first_row}"]._style) for c in "BCDEFG"}
        for row in ws.iter_rows(min_row=first_row, max_row=ws.max_row):
            for c in row:
                c.value = None
        return styles

    def put(ws, r, styles, values):
        for col, v in values.items():
            cell = ws[f"{col}{r}"]
            cell.value = v
            cell._style = copy(styles[col])

    # ---- 표준용어: 용어 하나에 한 행 (여러 테이블에 쓰이면 한 번만), 가나다순
    ws = wb["표준용어"]
    st = reset(ws, 4)
    seen, rows = {}, []
    for r in COLS:
        term, desc = term_of(r)
        if term not in seen:
            seen[term] = (desc, r["c"].upper())
    for e, (ko, _) in ENTITY.items():
        if ko not in seen:
            seen[ko] = (f"{COLS and next(x['tc'] for x in COLS if x['t'] == e)}", e.upper())
    ws["E3"], ws["F3"] = "물리명 (영문)", "비고"
    clone(ws["E3"], ws["D3"]); clone(ws["F3"], ws["D3"])
    for i, term in enumerate(sorted(seen, key=lambda t: (t[0].isascii(), t))):   # 한글 먼저, 영문(PM…) 뒤
        r = 4 + i
        desc, phys = seen[term]
        put(ws, r, st, {"B": "표준용어" if i == 0 else None, "C": term, "D": desc, "E": phys,
                        "F": "엔터티" if term in {ko for ko, _ in ENTITY.values()} else ""})
    last = 4 + len(seen) - 1
    ws.merge_cells(f"B4:B{last}")
    ws["B4"].alignment = Alignment(horizontal="center", vertical="center")
    ws.column_dimensions["E"].width = 26.9

    # ---- 표준단어사전
    ws = wb["표준단어사전"]
    st = reset(ws, 3)
    for i, (w, abbr, en, kind, rel) in enumerate(sorted(WORDS, key=lambda x: (x[0][0].isascii(), x[0]))):
        put(ws, 3 + i, st, {"B": "표준단어사전" if i == 0 else None, "C": w, "D": abbr, "E": en, "F": kind, "G": rel or None})
    ws.merge_cells(f"B3:B{3 + len(WORDS) - 1}")
    ws["B3"].alignment = Alignment(horizontal="center", vertical="center")

    # ---- 표준코드: 구분별로 C 열 병합, D=한글명, F=코드값
    ws = wb["표준코드"]
    st = reset(ws, 3)
    r = 3
    for group, items in CODES:
        start = r
        for name, code in items:
            put(ws, r, st, {"B": "표준코드" if r == 3 else None, "C": group if r == start else None, "D": name, "E": None, "F": code})
            r += 1
        if r - 1 > start:
            ws.merge_cells(f"C{start}:C{r - 1}")
        ws[f"C{start}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(f"B3:B{r - 1}")
    ws["B3"].alignment = Alignment(horizontal="center", vertical="center")

    # ---- 표준도메인
    ws = wb["표준도메인"]
    st = reset(ws, 3)
    r = 3
    for group, items in DOMAINS:
        start = r
        for attr, ty in items:
            put(ws, r, st, {"B": "표준도메인" if r == 3 else None, "C": group if r == start else None, "D": attr, "E": None, "F": ty})
            ws.merge_cells(f"D{r}:E{r}")
            r += 1
        if r - 1 > start:
            ws.merge_cells(f"C{start}:C{r - 1}")
        ws[f"C{start}"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells(f"B3:B{r - 1}")
    ws["B3"].alignment = Alignment(horizontal="center", vertical="center")
    ws.column_dimensions["F"].width = 30

    out = out_dir / "03-2_표준용어-도메인-코드정의서.xlsx"
    wb.save(out)
    print("saved", out, "| 용어", len(seen), "단어", len(WORDS), "코드", sum(len(i) for _, i in CODES), "도메인", sum(len(i) for _, i in DOMAINS))


# =====================================================================================
#  03-1 CRUD 매트릭스
# =====================================================================================
def build_crud():
    wb = openpyxl.load_workbook(sample_dir / "03-1_CRUD_매트릭스(예시).xlsx")
    ws = wb["Sheet1"]
    FIRST_COL, HDR_GROUP, HDR_ENT, FIRST_ROW = 4, 4, 5, 6           # D 열부터 엔터티, 4행 영역, 5행 엔터티, 6행부터 프로세스
    ents = [e for a in AREAS for e in ENTITY if ENTITY[e][1] == a]
    assert len(ents) == 28 and FIRST_COL + len(ents) - 1 == 31       # 예시와 같은 28개 열 (D~AE)
    last_col = get_column_letter(FIRST_COL + len(ents) - 1)
    sample_last_row = max(r for r in range(FIRST_ROW, ws.max_row + 1) if ws[f"B{r}"].value)

    # 서식 견본: (첫 행, 중간 행, 마지막 행) × (B, C, D(첫 엔터티), 중간, 마지막 엔터티)
    def row_styles(r):
        return {"B": copy(ws[f"B{r}"]._style), "C": copy(ws[f"C{r}"]._style), "D": copy(ws[f"D{r}"]._style),
                "M": copy(ws[f"E{r}"]._style), "L": copy(ws[f"AE{r}"]._style)}
    S_FIRST, S_MID, S_LAST = row_styles(FIRST_ROW), row_styles(FIRST_ROW + 1), row_styles(sample_last_row)
    hdr_group = {"D": copy(ws["D4"]._style), "M": copy(ws["E4"]._style), "L": copy(ws["AE4"]._style)}
    hdr_ent = {"D": copy(ws["D5"]._style), "M": copy(ws["E5"]._style), "L": copy(ws["AE5"]._style)}

    # 기존 내용·병합 제거 (제목 2행, B4:C5 유지)
    for rng in list(ws.merged_cells.ranges):
        if rng.min_row >= HDR_GROUP and str(rng) != "B4:C5":
            ws.unmerge_cells(str(rng))
    for row in ws.iter_rows(min_row=HDR_GROUP, max_row=ws.max_row, min_col=FIRST_COL):
        for c in row:
            c.value = None
    for row in ws.iter_rows(min_row=FIRST_ROW, max_row=ws.max_row, min_col=2, max_col=3):
        for c in row:
            c.value = None

    # 헤더: 영역(병합) / 엔터티 (세로 글자)
    col = FIRST_COL
    for area in AREAS:
        n = sum(1 for e in ents if ENTITY[e][1] == area)
        c1, c2 = get_column_letter(col), get_column_letter(col + n - 1)
        ws[f"{c1}{HDR_GROUP}"] = area
        for k in range(col, col + n):
            cl = get_column_letter(k)
            ws[f"{cl}{HDR_GROUP}"]._style = copy(hdr_group["L" if cl == last_col else ("D" if k == FIRST_COL else "M")])
        if n > 1:
            ws.merge_cells(f"{c1}{HDR_GROUP}:{c2}{HDR_GROUP}")
        col += n
    for i, e in enumerate(ents):
        cl = get_column_letter(FIRST_COL + i)
        ws[f"{cl}{HDR_ENT}"] = "\n".join(ENTITY[e][0])
        ws[f"{cl}{HDR_ENT}"]._style = copy(hdr_ent["L" if cl == last_col else ("D" if i == 0 else "M")])
        ws.column_dimensions[cl].width = 4.6
    ws.row_dimensions[HDR_ENT].height = 182.25

    # 프로세스 행
    for i, (name, m) in enumerate(PROCESSES):
        r = FIRST_ROW + i
        st = S_FIRST if i == 0 else (S_LAST if i == len(PROCESSES) - 1 else S_MID)
        ws[f"B{r}"], ws[f"C{r}"] = i + 1, name
        ws[f"B{r}"]._style, ws[f"C{r}"]._style = copy(st["B"]), copy(st["C"])
        for j, e in enumerate(ents):
            cl = get_column_letter(FIRST_COL + j)
            cell = ws[f"{cl}{r}"]
            cell.value = m.get(e)
            cell._style = copy(st["L" if cl == last_col else ("D" if j == 0 else "M")])
        ws.row_dimensions[r].height = 17.25
    for r in range(FIRST_ROW + len(PROCESSES), ws.max_row + 1):      # 예시보다 행이 많으면 남는 행 없음, 적으면 서식 제거
        for c in ws[r]:
            c._style = copy(ws["A1"]._style)
    ws.column_dimensions["C"].width = 34

    out = out_dir / "03-1_CRUD_매트릭스.xlsx"
    wb.save(out)
    print("saved", out, "| 프로세스", len(PROCESSES), "엔터티", len(ents))


build_standards()
build_crud()
