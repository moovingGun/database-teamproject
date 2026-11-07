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

sys.path.insert(0, str(Path(__file__).resolve().parent))
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


from si_pms_terms import AREAS, ENTITY, TERM, term_of  # noqa: E402  (논리명 공용 정의)

assert set(ENTITY) == {r["t"] for r in COLS}, set(ENTITY) ^ {r["t"] for r in COLS}
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
