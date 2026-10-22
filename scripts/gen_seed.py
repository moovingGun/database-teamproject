"""
SI-PMS 시드 데이터 생성기
  .venv/bin/python scripts/gen_seed.py  ->  db/init/03_seed.sql 생성

* random.seed 고정 -> 항상 동일한 데이터가 생성됨 (팀원 간 동일 환경 보장)
* 02_logic.sql 의 트리거(투입 검증, 평가 검증)를 모두 통과하도록 생성 단계에서 규칙을 지킴
* 사번(emp_no)·프로젝트번호(project_code)는 비워 두어 트리거 자동 채번을 그대로 검증
"""
import random
from datetime import date, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

random.seed(20261019)
TODAY = date(2026, 10, 19)
OUT = Path(__file__).resolve().parent.parent / "db" / "init" / "03_seed.sql"
DEMO_PASSWORD = "pass1234"

# --------------------------------------------------------------------- helpers
def q(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, date):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"

def rows(table, cols, data, chunk=200):
    out = []
    for i in range(0, len(data), chunk):
        vals = ",\n".join("  (" + ", ".join(q(v) for v in r) + ")" for r in data[i:i + chunk])
        out.append(f"INSERT INTO {table} ({', '.join(cols)}) VALUES\n{vals};")
    return "\n".join(out)

def rdate(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))

def add_months(d, m):
    y, mo = divmod(d.month - 1 + m, 12)
    return date(d.year + y, mo + 1, min(d.day, 28))

# --------------------------------------------------------------------- 기준 데이터
SURNAMES = [("김", "kim"), ("이", "lee"), ("박", "park"), ("최", "choi"), ("정", "jung"), ("강", "kang"),
            ("조", "cho"), ("윤", "yoon"), ("장", "jang"), ("임", "lim"), ("한", "han"), ("오", "oh"),
            ("서", "seo"), ("신", "shin"), ("권", "kwon"), ("황", "hwang"), ("안", "ahn"), ("송", "song"),
            ("류", "ryu"), ("홍", "hong"), ("전", "jeon"), ("고", "ko"), ("문", "moon"), ("배", "bae")]
GIVEN = ["민준", "서준", "도윤", "예준", "시우", "하준", "지호", "지유", "서연", "하은", "수아", "지민", "지우",
         "하윤", "채원", "다은", "은우", "현우", "준서", "유진", "민서", "서현", "지훈", "승현", "태양", "정우",
         "동현", "수빈", "예린", "가은", "민재", "성민", "영호", "미영", "은지", "상훈", "재현", "혜진", "보람",
         "나영", "준혁", "세진", "우진", "예은", "지원", "성호", "다현", "경민", "소율", "현준"]

SKILLS = [
    ("Java", "LANGUAGE"), ("Python", "LANGUAGE"), ("JavaScript", "LANGUAGE"), ("TypeScript", "LANGUAGE"),
    ("Kotlin", "LANGUAGE"), ("C#", "LANGUAGE"), ("C++", "LANGUAGE"), ("Go", "LANGUAGE"), ("SQL/PL-SQL", "LANGUAGE"),
    ("Spring Boot", "FRAMEWORK"), ("Spring Batch", "FRAMEWORK"), ("React", "FRAMEWORK"), ("Vue.js", "FRAMEWORK"),
    ("Next.js", "FRAMEWORK"), ("Node.js", "FRAMEWORK"), ("Django", "FRAMEWORK"), (".NET Core", "FRAMEWORK"),
    ("Android", "FRAMEWORK"), ("Flutter", "FRAMEWORK"), ("JPA/Hibernate", "FRAMEWORK"), ("MyBatis", "FRAMEWORK"),
    ("Oracle", "DATABASE"), ("MySQL", "DATABASE"), ("PostgreSQL", "DATABASE"), ("MS-SQL", "DATABASE"),
    ("MongoDB", "DATABASE"), ("Redis", "DATABASE"), ("Tibero", "DATABASE"),
    ("AWS", "CLOUD"), ("Azure", "CLOUD"), ("GCP", "CLOUD"), ("Docker", "CLOUD"), ("Kubernetes", "CLOUD"),
    ("Naver Cloud", "CLOUD"),
    ("Linux", "OS"), ("Windows Server", "OS"), ("Unix(AIX)", "OS"),
    ("Jenkins", "TOOL"), ("Git", "TOOL"), ("JIRA", "TOOL"), ("Figma", "TOOL"), ("Kafka", "TOOL"),
    ("Elasticsearch", "TOOL"),
    ("Agile/Scrum", "METHOD"), ("정보공학방법론", "METHOD"), ("TDD", "METHOD"), ("DevOps", "METHOD"),
    ("ISMS-P 보안", "METHOD"),
]
SKILL_ID = {name: i + 1 for i, (name, _) in enumerate(SKILLS)}

ROLES = [  # role_id, code, name, min_grade, sort
    (1, "PM", "PM(프로젝트관리자)", "고급", 1),
    (2, "PL", "PL(프로젝트리더)", "중급", 2),
    (3, "ANALYST", "분석자", "중급", 3),
    (4, "DESIGNER", "설계자", "중급", 4),
    (5, "PROGRAMMER", "프로그래머", "초급", 5),
    (6, "TESTER", "테스터", "초급", 6),
]
GRADE_LEVEL = {"초급": 1, "중급": 2, "고급": 3, "특급": 4}
ROLE_MIN = {r[0]: GRADE_LEVEL[r[3]] for r in ROLES}

CLIENTS = [  # 가상의 발주처
    ("대한전력공사", "공공/에너지", "전라남도 나주시 전력로 55"),
    ("한빛은행", "금융", "서울특별시 중구 을지로 35"),
    ("미래카드", "금융", "서울특별시 중구 세종대로 9"),
    ("태양생명보험", "보험", "서울특별시 영등포구 국제금융로 10"),
    ("한성자동차", "제조", "경기도 화성시 현대연구소로 150"),
    ("스카이텔레콤", "통신", "서울특별시 용산구 한강대로 32"),
    ("온누리마트", "유통", "서울특별시 송파구 올림픽로 300"),
    ("세종특별시청", "공공/행정", "세종특별자치시 한누리대로 2130"),
    ("국민건강보험공단", "공공/보건", "강원도 원주시 건강로 32"),
    ("퀵커머스", "유통/IT", "서울특별시 송파구 송파대로 570"),
    ("한국물류", "물류", "서울특별시 중구 소월로 2"),
    ("북앤라이프", "유통/문화", "서울특별시 종로구 종로 1"),
]
POSITIONS = ["부장", "차장", "과장", "팀장", "실장"]

PROJECT_NAMES = [
    "차세대 계정계 시스템 구축", "모바일 뱅킹 앱 고도화", "ERP 시스템 전환", "전사 데이터 플랫폼 구축",
    "고객관리(CRM) 시스템 재구축", "스마트팩토리 MES 구축", "온라인몰 리뉴얼", "민원 포털 고도화",
    "빅데이터 분석 플랫폼 구축", "클라우드 전환(마이그레이션)", "통합 보안관제 시스템 구축", "물류 WMS 구축",
    "AI 챗봇 상담 시스템 개발", "전자결재 시스템 고도화", "카드 승인 시스템 성능개선", "보험 청약 시스템 구축",
    "통신 요금 정산 시스템 재구축", "HR 통합 시스템 구축", "데이터 거버넌스 체계 구축", "배송 추적 시스템 개발",
    "스마트그리드 운영 시스템 구축", "건강검진 예약 플랫폼 구축", "도서 추천 서비스 개발", "자금 관리 시스템 고도화",
    "커넥티드카 백엔드 플랫폼 구축", "통합 콜센터 시스템 구축", "마이데이터 연계 시스템 구축", "전자도서관 시스템 재구축",
]

COMMENTS = {
    5: ["기한 내 높은 품질로 산출물을 완수함", "핵심 이슈를 주도적으로 해결함", "명확한 보고와 협업으로 팀 신뢰도가 높음",
        "고객 요구사항을 정확히 파악하고 선제적으로 대응함"],
    4: ["맡은 업무를 안정적으로 수행함", "의사소통이 원활하고 협조적임", "일정 준수율이 높고 문서화가 충실함",
        "요구사항 변경에 유연하게 대응함"],
    3: ["기본 업무는 수행하나 품질 편차가 있음", "보고 주기가 다소 불규칙함", "일정 지연이 간혹 발생함",
        "회의 참여도는 보통 수준임"],
    2: ["산출물 재작업이 잦았음", "이슈 공유가 늦어 일정에 영향을 줌", "커뮤니케이션 개선이 필요함",
        "요구사항 이해도가 부족하여 재설명이 필요했음"],
    1: ["업무 수행에 지속적인 지원이 필요했음", "협업 과정에서 갈등이 발생함"],
}

# --------------------------------------------------------------------- 직원 100명
employees = []   # dict
used_names = set()
def new_name():
    while True:
        s, rom = random.choice(SURNAMES)
        n = s + random.choice(GIVEN)
        if n not in used_names:
            used_names.add(n)
            return n, rom

def rrn(birth, male):
    g = (1 if birth.year < 2000 else 3) + (0 if male else 1)
    return f"{birth:%y%m%d}-{g}{random.randint(0, 999999):06d}"

login_counter = {}
def new_login(rom):
    login_counter[rom] = login_counter.get(rom, 0) + 1
    return f"{rom}{login_counter[rom]:02d}"

def grade_for(career_months):
    if career_months < 36: return "초급"
    if career_months < 72: return "중급"
    if career_months < 120: return "고급"
    return "특급"

def make_emp(emp_id, emp_type, *, login=None, role="EMPLOYEE", dept=None, title=None, grade=None):
    name, rom = new_name()
    birth = rdate(date(1970, 1, 1), date(2002, 12, 31))
    hire = rdate(date(2012, 1, 1), date(2026, 9, 30))
    if grade:  # 원하는 등급에 맞춰 경력 기산일 역산
        lo, hi = {"초급": (6, 35), "중급": (36, 71), "고급": (72, 119), "특급": (120, 240)}[grade]
        career_months = random.randint(lo, hi)
    else:
        career_months = random.randint(6, 200)
    career_start = add_months(TODAY, -career_months)
    if emp_type == "DEV" and career_start > hire:
        career_start = hire
        career_months = (TODAY.year - hire.year) * 12 + TODAY.month - hire.month
    if hire < career_start:          # 입사가 경력 기산일보다 빠를 수 없음(지원직 포함)
        hire = career_start if emp_type == "DEV" else hire
    e = dict(emp_id=emp_id, name=name, rrn=rrn(birth, random.random() < 0.6),
             edu=random.choices(["고졸", "전문학사", "학사", "석사", "박사"], [3, 12, 65, 17, 3])[0],
             hire=hire, type=emp_type, email=f"{login or new_login(rom)}@sipms.co.kr",
             phone=f"010-{random.randint(2000, 9999)}-{random.randint(1000, 9999)}",
             login=None, role=role, dept=dept, title=title,
             grade=grade_for(career_months) if emp_type == "DEV" else None,
             career_start=career_start if emp_type == "DEV" else None)
    e["login"] = login or e["email"].split("@")[0]
    return e

# 고정 데모 계정 4명
employees.append(make_emp(1, "STAFF", login="ceo",    role="EXECUTIVE", dept="MANAGEMENT", title="대표이사"))
employees.append(make_emp(2, "STAFF", login="exec01", role="EXECUTIVE", dept="MANAGEMENT", title="경영관리본부장"))
employees.append(make_emp(3, "DEV",   login="pm01",   grade="특급"))
employees.append(make_emp(4, "DEV",   login="dev01",  grade="중급"))
# 개발자 68명 추가 (고정 계정 2명 포함 총 70명. 등급 분포: 초급 25, 중급 23, 고급 14, 특급 6)
dev_grades = ["초급"] * 25 + ["중급"] * 23 + ["고급"] * 14 + ["특급"] * 6
random.shuffle(dev_grades)
eid = 5
for g in dev_grades:
    employees.append(make_emp(eid, "DEV", grade=g)); eid += 1
# 지원직 28명 (마케팅 10, 경영관리 10(그 중 1명 경영진), 연구개발 8)
staff_plan = [("MARKETING", None)] * 10 + [("MANAGEMENT", None)] * 10 + [("RND", None)] * 8
titles = {"MARKETING": ["마케팅팀장", "마케팅 매니저", "영업대표", "제안 컨설턴트"],
          "MANAGEMENT": ["인사팀장", "재무 담당", "총무 담당", "구매 담당", "PMO 담당"],
          "RND": ["연구소장", "선임연구원", "연구원", "데이터 사이언티스트"]}
for i, (dept, _) in enumerate(staff_plan):
    role = "EXECUTIVE" if (dept == "MANAGEMENT" and i == 10) else "EMPLOYEE"
    title = titles[dept][0] if role == "EXECUTIVE" else random.choice(titles[dept][1:])
    employees.append(make_emp(eid, "STAFF", role=role, dept=dept, title=title)); eid += 1
assert len(employees) == 100
EMP = {e["emp_id"]: e for e in employees}
DEVS = [e for e in employees if e["type"] == "DEV"]
pw_hash = generate_password_hash(DEMO_PASSWORD, method="pbkdf2:sha256")

# 데모용 '현재 가용 인력' 확보: 등급별 소수 인원은 2026-09-01 이후 종료되는 투입에서 제외 (경영진 투입 데모에 사용)
BENCH_FROM = date(2026, 9, 1)
RESERVED = set()
for g, n in (("특급", 1), ("고급", 2), ("중급", 2), ("초급", 2)):
    RESERVED |= {d["emp_id"] for d in [x for x in DEVS if x["grade"] == g and x["emp_id"] not in (3, 4)][:n]}

# 개발자 보유 기술 3~8개
emp_skills = []
for e in DEVS:
    n = random.randint(3, 8)
    for name, _ in random.sample(SKILLS, n):
        years = round(min(random.uniform(0.5, 12), max(0.5, (TODAY - e["career_start"]).days / 365)), 1)
        emp_skills.append((e["emp_id"], SKILL_ID[name], random.randint(2, 5), years,
                           rdate(date(2023, 1, 1), TODAY)))

# --------------------------------------------------------------------- 발주처 / 담당자
clients, contacts = [], []
cid = 1
for i, (name, ind, addr) in enumerate(CLIENTS):
    breg = f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10000,99999)}"
    clients.append((i + 1, name, breg, ind, addr, f"02-{random.randint(200,999)}-{random.randint(1000,9999)}"))
    for _ in range(random.randint(1, 3)):
        cn, rom = new_name()
        contacts.append((cid, i + 1, cn, random.choice(POSITIONS), f"{rom}{cid}@{['kepco','hanbit','mirae','taeyang','hansung','skytel','onnuri','sejong','nhis','quick','krlogis','booknlife'][i]}.co.kr",
                         f"010-{random.randint(2000,9999)}-{random.randint(1000,9999)}", 1))
        cid += 1
CONTACTS_BY_CLIENT = {}
for c in contacts:
    CONTACTS_BY_CLIENT.setdefault(c[1], []).append(c[0])

# --------------------------------------------------------------------- 프로젝트 28개
projects = []  # dict(project_id, name, client, start, end, status, amount, desc)
names = PROJECT_NAMES[:]
random.shuffle(names)
pid = 1
def add_project(status, start, end):
    global pid
    projects.append(dict(project_id=pid, name=names.pop(), client=random.randint(1, len(CLIENTS)),
                         start=start, end=end, status=status,
                         amount=random.randint(3, 60) * 50_000_000,
                         desc="발주처 요구에 따른 " + ("신규 구축" if random.random() < 0.6 else "고도화") + " 프로젝트"))
    pid += 1
for _ in range(12):                       # 종료
    s = rdate(date(2024, 1, 1), date(2025, 11, 1)); add_project("COMPLETED", s, min(add_months(s, random.randint(4, 10)), date(2026, 8, 31)))
for _ in range(2):                        # 취소
    s = rdate(date(2025, 1, 1), date(2025, 9, 1)); add_project("CANCELLED", s, add_months(s, random.randint(2, 4)))
for _ in range(10):                       # 진행 중 (현재 시점 포함)
    s = rdate(date(2026, 3, 1), date(2026, 10, 1)); add_project("IN_PROGRESS", s, add_months(s, random.randint(6, 12)))
for _ in range(4):                        # 예정
    s = rdate(date(2027, 1, 4), date(2027, 4, 1)); add_project("PLANNED", s, add_months(s, random.randint(4, 9)))
projects.sort(key=lambda p: p["start"])
for i, p in enumerate(projects):          # 착수일 순으로 ID 재부여 (트리거 채번 결과도 연도 순)
    p["project_id"] = i + 1
PRJ = {p["project_id"]: p for p in projects}

project_skills = []
for p in projects:
    for name, _ in random.sample(SKILLS, random.randint(3, 6)):
        project_skills.append((p["project_id"], SKILL_ID[name], random.randint(2, 5)))

# --------------------------------------------------------------------- 투입 (트리거 규칙 준수)
busy = {e["emp_id"]: [] for e in DEVS}       # emp_id -> [(start, end, rate)]
assignments = []                            # dict
aid = 1

def max_rate(emp_id, s, e):
    pts = {s} | {b[0] for b in busy[emp_id] if s <= b[0] <= e}
    return max(sum(b[2] for b in busy[emp_id] if b[0] <= p <= b[1]) for p in pts)

def available(emp, role_id, s, e, rate):
    return (GRADE_LEVEL[emp["grade"]] >= ROLE_MIN[role_id] and emp["hire"] <= s
            and not (emp["emp_id"] in RESERVED and e >= BENCH_FROM)
            and max_rate(emp["emp_id"], s, e) + rate <= 100)

def assign(p, emp, role_id, s, e, rate=100, note=None):
    global aid
    assignments.append(dict(assignment_id=aid, project_id=p["project_id"], emp_id=emp["emp_id"], role_id=role_id,
                            start=s, end=e, rate=rate, note=note))
    busy[emp["emp_id"]].append((s, e, rate)); aid += 1

def pick(p, role_id, s, e, rate=100, prefer=None):
    cands = [EMP[prefer]] if prefer and available(EMP[prefer], role_id, s, e, rate) else []
    if not cands:
        cands = [d for d in DEVS if available(d, role_id, s, e, rate)
                 and not any(a["project_id"] == p["project_id"] and a["emp_id"] == d["emp_id"]
                             and a["start"] <= e and a["end"] >= s for a in assignments)]
    if not cands:
        return None
    # 등급이 직무 요건에 가까운 사람 우선(고급 인력 낭비 방지), 동률은 무작위
    cands.sort(key=lambda d: (GRADE_LEVEL[d["grade"]] - ROLE_MIN[role_id], random.random()))
    return cands[0]

completed = [p for p in projects if p["status"] == "COMPLETED"]
inprog = [p for p in projects if p["status"] == "IN_PROGRESS"]
for p in projects:                                  # 종료 프로젝트는 실제 종료일 = 종료예정일
    p["actual_end"] = p["end"] if p["status"] == "COMPLETED" else None

# ---- [시나리오 A] 변경요청 시나리오 정의: (진행중 프로젝트 순번, 제목, 내용, 사유, [검토 차수...], 반영 여부)
#      검토 차수 = (연장 일수, 추가금액, 검토의견, 결정, 결정사유, 결정자, 고객동의, 확인근거)
CR_PLAN = [
    (0, "통계 대시보드 화면 추가", "상담 이력을 일·주·월 단위로 보여 주는 관리자용 통계 대시보드 화면 3종을 추가해 달라는 요청",
        "운영 부서가 상담 품질 지표를 매주 확인해야 함",
        [(14, 5_000_000, "화면 3종 추가와 집계 쿼리 개발. 프로그래머 1명 2주 추가 필요", "APPROVED", "요청 범위가 타당하고 증액으로 비용 보전", 1,
          "AGREED", "고객사 이메일 회신 (변경 합의서 첨부)")], True),
    (0, "관리자 권한 세분화", "관리자 계정을 상담 관리자와 운영 관리자로 나누고 메뉴 접근 권한을 분리해 달라는 요청",
        "고객사 내부 보안 감사 지적 사항",
        [(10, 3_000_000, "권한 테이블 추가와 메뉴 접근 제어 수정, 통합 테스트 1주 추가", "PENDING", None, None, "PENDING", None)], False),
    (1, "외부 결제(PG) 연동 추가", "온라인 결제 대행사(PG) 연동과 결제 취소·환불 화면을 추가해 달라는 요청",
        "유료 서비스 출시 일정이 앞당겨짐",
        [(21, 12_000_000, "PG 사 인증 일정 포함 3주 소요, 보안 점검 필요", "APPROVED", "매출 영향이 커서 우선 승인", 2, "PENDING", None)], False),
    (2, "보고서 PDF 출력 기능", "조회 화면의 결과를 PDF 보고서로 내려받는 기능 추가 요청",
        "임원 보고용 자료 작성 시간 단축",
        [(7, 2_000_000, "출력 템플릿 5종 개발 1주", "REJECTED", "기존 계약의 '조회 결과 출력' 범위에 포함되어 추가 비용 없이 기존 일정 안에서 처리", 1, "PENDING", None)], False),
    (3, "영문(다국어) 화면 지원", "전체 화면을 영문으로도 제공해 달라는 요청",
        "해외 지사 사용자 추가",
        [(20, 8_000_000, "전 화면 문구 분리와 번역 검수 포함 20일", "APPROVED", "해외 지사 확대 계획과 일치", 1, "AGREED", "주간 회의록 (고객사 서명)"),
         (10, 4_000_000, "고객이 범위를 주요 화면 12개로 축소 → 재검토, 10일·400만 원", "PENDING", None, None, "PENDING", None)], False),
    (4, "모바일 반응형 화면 적용", "현장 직원이 휴대폰으로 조회할 수 있도록 주요 화면을 반응형으로 바꿔 달라는 요청",
        "현장 점검 업무의 모바일 전환", [], False),
    (5, "데이터 이관 범위 확대", "기존 시스템 데이터 이관 범위를 최근 5년에서 최근 10년으로 늘려 달라는 요청",
        "과거 이력 조회 수요",
        [(30, 15_000_000, "이관 대상 4배 증가, 정합성 검증 2주 추가", "APPROVED", "필요성은 인정, 비용은 고객 부담 조건", 2, "DECLINED", "고객사 예산 부족으로 거절 (전화 확인 후 이메일 회신)")], False),
    (6, "실시간 알림 기능 추가", "결재 요청이 오면 메신저와 이메일로 즉시 알림을 보내는 기능 추가 요청",
        "결재 지연 민원 증가",
        [(30, 6_000_000, "알림 서버 구성과 메신저 연동 4주", "APPROVED", "고객 만족도 개선 효과가 큼", 2, "AGREED", "변경 합의서 서명본 (우편 수령)")], True),
]
for pi, *_rest, applied in CR_PLAN:              # 반영된 요청은 종료예정일·계약금액을 미리 늘려 둠
    if applied:
        p = inprog[pi]
        ext, add = _rest[3][0][0], _rest[3][0][1]
        p["orig_end"], p["orig_amount"] = p["end"], p["amount"]
        p["end"] = p["end"] + timedelta(days=ext)
        p["amount"] = p["amount"] + add
PM01_COMPLETED = completed[-1]["project_id"]    # pm01 이 PM 인 종료 프로젝트 (가장 최근 종료)
PM01_INPROG = inprog[0]["project_id"]
DEV01_INPROG = inprog[1]["project_id"]

for p in projects:
    if p["status"] == "PLANNED":
        continue
    s, e = p["start"], p["end"]
    days = (e - s).days
    pct = lambda f: s + timedelta(days=int(days * f))
    prefer_pm = 3 if p["project_id"] in (PM01_COMPLETED, PM01_INPROG) else None
    pm = pick(p, 1, s, e, prefer=prefer_pm)
    if pm: assign(p, pm, 1, s, e)
    pl = pick(p, 2, s, e)
    if pl: assign(p, pl, 2, s, e)
    is_inprog = p["status"] == "IN_PROGRESS"
    for _ in range(1 if is_inprog else random.randint(1, 2)):      # 분석자: 전반부, 50% 투입 허용
        rate = random.choice([50, 100])
        a = pick(p, 3, s, pct(0.5), rate)
        if a: assign(p, a, 3, s, pct(0.5), rate, "분석 단계 투입" if rate == 100 else "분석 단계 50% 투입")
    d = pick(p, 4, pct(0.15), pct(0.7))                             # 설계자
    if d: assign(p, d, 4, pct(0.15), pct(0.7), 100, "설계 단계 투입")
    n_prog = random.randint(2, 3) if is_inprog else random.randint(2, 5)
    for i in range(n_prog):                                        # 프로그래머
        ps = s if i % 2 == 0 else pct(0.25)
        prefer = 4 if (p["project_id"] == DEV01_INPROG and i == 0) else None
        pr = pick(p, 5, ps, e, prefer=prefer)
        if pr: assign(p, pr, 5, ps, e, 100, None if i % 2 == 0 else "개발 단계 중간 투입")
    for _ in range(1 if is_inprog else random.randint(1, 2)):      # 테스터: 후반부
        t = pick(p, 6, pct(0.6), e)
        if t: assign(p, t, 6, pct(0.6), e, 100, "테스트 단계 투입")

# --------------------------------------------------------------------- 평가 (종료 프로젝트)
ITEM_IDS = {"WORK": 1, "COMM": 2}
evaluations, customer_evals, pm_evals, peer_evals, eval_details = [], [], [], [], []
ev_id = 1
quality = {e["emp_id"]: min(5.0, max(2.0, random.gauss(4.0, 0.6))) for e in DEVS}

def score_for(emp_id):
    return int(min(5, max(1, round(quality[emp_id] + random.gauss(0, 0.5)))))

def add_eval(p, evaluatee, etype, status, eval_date, with_details=True):
    global ev_id
    this = ev_id
    evaluations.append((this, p["project_id"], evaluatee, etype, status,
                        eval_date if with_details else None,
                        random.choice(COMMENTS[score_for(evaluatee)]) if with_details and random.random() < 0.5 else None))
    if with_details:
        for code, iid in ITEM_IDS.items():
            sc = score_for(evaluatee)
            eval_details.append((this, iid, sc, random.choice(COMMENTS[sc])))
    ev_id += 1
    return this

token_counter = 0
def token():
    global token_counter
    token_counter += 1
    return f"{random.getrandbits(128):032x}"

for p in completed:
    members = [a for a in assignments if a["project_id"] == p["project_id"]]
    pm = next((a["emp_id"] for a in members if a["role_id"] == 1), None)
    member_ids = sorted({a["emp_id"] for a in members})
    base_date = p["end"] + timedelta(days=random.randint(3, 14))
    is_demo = p["project_id"] == PM01_COMPLETED      # pm01 의 프로젝트는 평가가 '진행 중' 상태로 남겨 데모에 사용
    # PM 평가
    if pm:
        targets = [m for m in member_ids if m != pm]
        if is_demo:
            targets = targets[:-2]                      # 2명은 미평가 → 데모에서 입력
        for m in targets:
            e = add_eval(p, m, "PM", "SUBMITTED", base_date)
            pm_evals.append((e, pm, 1 if quality[m] >= 4.5 else 0))
    # 동료 평가 : 각자 2~3명
    for ev in member_ids:
        others = [m for m in member_ids if m != ev]
        k = min(len(others), random.randint(2, 3))
        if is_demo and ev == pm:
            k = min(1, len(others))
        for m in random.sample(others, k):
            e = add_eval(p, m, "PEER", "SUBMITTED", base_date + timedelta(days=random.randint(0, 5)))
            peer_evals.append((e, ev, 1))
    # 고객 평가 : 발주처 담당자 1명이 전원 평가 (PM 이 의뢰)
    if pm:
        contact = random.choice(CONTACTS_BY_CLIENT[p["client"]])
        for m in member_ids:
            if is_demo:
                e = add_eval(p, m, "CUSTOMER", "REQUESTED", None, with_details=False)
                customer_evals.append((e, contact, pm, base_date, token(), None))
            else:
                e = add_eval(p, m, "CUSTOMER", "REPORTED", base_date + timedelta(days=7))
                customer_evals.append((e, contact, pm, base_date, token(), base_date + timedelta(days=9)))

# --------------------------------------------------------------------- [시나리오 A] 변경요청 행
change_requests, change_reviews, change_histories = [], [], []
crid, rvid = 1, 1
for pi, title, content, reason, versions, applied in CR_PLAN:
    p = inprog[pi]
    pm = next(a["emp_id"] for a in assignments if a["project_id"] == p["project_id"] and a["role_id"] == 1)
    contacts_of = CONTACTS_BY_CLIENT[p["client"]]
    req_date = min(p["start"] + timedelta(days=20 + 9 * len(change_requests) % 30), TODAY - timedelta(days=25))
    req_date = max(req_date, p["start"])
    change_requests.append((crid, p["project_id"], contacts_of[0], pm, req_date, title, content, reason))
    d = req_date
    for v, (ext, add, comment, dec, dec_reason, decider, consent, evidence) in enumerate(versions, 1):
        base_end = p["orig_end"] if applied else p["end"]      # 미반영 요청은 현재 종료예정일 기준
        reviewed = d + timedelta(days=3)
        decided = reviewed + timedelta(days=4) if dec != "PENDING" else None
        consented = decided + timedelta(days=4) if consent != "PENDING" else None
        change_reviews.append((rvid, crid, v, pm, base_end + timedelta(days=ext), add, comment, f"{reviewed} 10:00:00",
                               dec, decider, decided, dec_reason, consent,
                               contacts_of[-1] if consent != "PENDING" else None, consented, evidence,
                               pm if consent != "PENDING" else None))
        if applied and v == len(versions):
            change_histories.append((rvid, p["orig_end"], p["end"], p["orig_amount"], p["amount"],
                                     pm if pi == 0 else 2, f"{consented + timedelta(days=2)} 09:30:00"))
        d = (consented or decided or reviewed) + timedelta(days=5)
        rvid += 1
    crid += 1

# --------------------------------------------------------------------- 등급 변경 이력 (과거 승급 기록)
grade_hist = []
order = ["초급", "중급", "고급", "특급"]
for e in random.sample([d for d in DEVS if d["grade"] != "초급"], 8):
    new = e["grade"]; old = order[order.index(new) - 1]
    grade_hist.append((e["emp_id"], old, new, rdate(date(2024, 1, 1), date(2026, 6, 30)), 2, "정기 기술등급 심사 승급"))

# --------------------------------------------------------------------- SQL 출력
parts = [
    "-- =====================================================================",
    "--  SI-PMS 테스트 데이터 (scripts/gen_seed.py 로 자동 생성 - 직접 수정하지 말 것)",
    f"--  기준일 {TODAY}  |  직원 {len(employees)}명 (개발자 {len(DEVS)}) | 프로젝트 {len(projects)} | 투입 {len(assignments)} | 평가 {len(evaluations)}",
    f"--  데모 계정 비밀번호(공통): {DEMO_PASSWORD}   경영진: ceo, exec01   PM: pm01   개발자: dev01",
    "-- =====================================================================",
    "USE si_pms;", "SET NAMES utf8mb4;",
    "",
    "-- 기준(코드) 데이터 ------------------------------------------------------",
    rows("job_role", ["role_id", "role_code", "role_name", "min_grade", "sort_order"], ROLES),
    rows("skill", ["skill_id", "skill_name", "category"], [(i + 1, n, c) for i, (n, c) in enumerate(SKILLS)]),
    rows("eval_item", ["item_id", "item_code", "item_name", "description", "weight"],
         [(1, "WORK", "업무수행", "산출물 품질, 일정 준수, 문제 해결 능력", 1.00),
          (2, "COMM", "커뮤니케이션 능력", "보고, 협업, 고객 응대 태도", 1.00)]),
    rows("eval_type_weight", ["eval_type", "weight", "description"],
         [("CUSTOMER", 0.40, "고객 평가"), ("PM", 0.40, "PM 평가"), ("PEER", 0.20, "동료 평가")]),
    "",
    "-- 발주처 / 담당자 --------------------------------------------------------",
    rows("client", ["client_id", "client_name", "business_reg_no", "industry", "address", "phone"], clients),
    rows("client_contact", ["contact_id", "client_id", "contact_name", "position", "email", "phone", "is_active"], contacts),
    "",
    "-- 직원 (슈퍼타입) : emp_no 는 트리거가 자동 채번 ------------------------------",
    rows("employee", ["emp_id", "emp_name", "resident_reg_no", "education_level", "hire_date", "emp_type", "email", "phone"],
         [(e["emp_id"], e["name"], e["rrn"], e["edu"], e["hire"], e["type"], e["email"], e["phone"]) for e in employees]),
    rows("developer", ["emp_id", "skill_grade", "career_start_date"],
         [(e["emp_id"], e["grade"], e["career_start"]) for e in DEVS]),
    rows("staff", ["emp_id", "department", "job_title"],
         [(e["emp_id"], e["dept"], e["title"]) for e in employees if e["type"] == "STAFF"]),
    rows("user_account", ["emp_id", "login_id", "password_hash", "auth_role"],
         [(e["emp_id"], e["login"], pw_hash, e["role"]) for e in employees]),
    rows("employee_skill", ["emp_id", "skill_id", "proficiency", "years_used", "last_used_date"], emp_skills),
    "",
    "-- 프로젝트 : project_code 는 트리거가 자동 채번 ---------------------------------",
    rows("project", ["project_id", "project_name", "client_id", "start_date", "end_date", "actual_end_date", "status", "contract_amount", "description"],
         [(p["project_id"], p["name"], p["client"], p["start"], p["end"], p["actual_end"], p["status"], p["amount"], p["desc"]) for p in projects]),
    rows("project_skill", ["project_id", "skill_id", "required_level"], project_skills),
    "",
    "-- 투입 (트리거 BR-01~07 검증 통과) -------------------------------------------",
    rows("assignment", ["assignment_id", "project_id", "emp_id", "role_id", "start_date", "end_date", "participation_rate", "note"],
         [(a["assignment_id"], a["project_id"], a["emp_id"], a["role_id"], a["start"], a["end"], a["rate"], a["note"]) for a in assignments]),
    "",
    "-- 평가 (슈퍼타입 → 서브타입 → 상세) ------------------------------------------",
    rows("evaluation", ["eval_id", "project_id", "evaluatee_emp_id", "eval_type", "status", "eval_date", "overall_comment"], evaluations),
    rows("customer_eval", ["eval_id", "contact_id", "requested_by_emp_id", "requested_at", "access_token", "reported_at"], customer_evals),
    rows("pm_eval", ["eval_id", "evaluator_emp_id", "recommend_incentive"], pm_evals),
    rows("peer_eval", ["eval_id", "evaluator_emp_id", "is_anonymous"], peer_evals),
    rows("eval_detail", ["eval_id", "item_id", "score", "comment"], eval_details),
    "",
    "-- [시나리오 A] 고객사 변경요청 (요청번호는 트리거 자동 채번, BR-16~23 검증 통과) --------",
    rows("change_request", ["cr_id", "project_id", "contact_id", "received_by_emp_id", "request_date", "title", "content", "reason"], change_requests),
    rows("change_review", ["review_id", "cr_id", "version_no", "reviewer_emp_id", "proposed_end_date", "additional_amount", "review_comment",
                           "reviewed_at", "decision", "decided_by_emp_id", "decided_at", "decision_reason", "consent", "consent_contact_id",
                           "consent_date", "consent_evidence", "consent_recorded_by"], change_reviews),
    rows("change_history", ["review_id", "before_end_date", "after_end_date", "before_amount", "after_amount", "applied_by_emp_id", "applied_at"],
         change_histories),
    "",
    "-- 기술등급 변경 이력 -------------------------------------------------------",
    rows("grade_history", ["emp_id", "old_grade", "new_grade", "changed_at", "changed_by_emp_id", "reason"], grade_hist),
    "",
]
OUT.write_text("\n".join(parts), encoding="utf-8")

n_pm01_pending_pm = len([a for a in assignments if a["project_id"] == PM01_COMPLETED]) - 1 - len([x for x in pm_evals if x[1] == 3 and PRJ[next(e[1] for e in evaluations if e[0] == x[0])]["project_id"] == PM01_COMPLETED])
print(f"wrote {OUT}  ({OUT.stat().st_size // 1024} KB)")
print(f"employees={len(employees)} devs={len(DEVS)} clients={len(clients)} contacts={len(contacts)} projects={len(projects)} "
      f"assignments={len(assignments)} evaluations={len(evaluations)} details={len(eval_details)}")
print(f"demo: pm01 PM of completed project #{PM01_COMPLETED} ({PRJ[PM01_COMPLETED]['name']}) and in-progress #{PM01_INPROG}; "
      f"dev01 on in-progress #{DEV01_INPROG}")
by_status = {}
for p in projects:
    by_status[p["status"]] = by_status.get(p["status"], 0) + 1
print("projects by status:", by_status)
print("reserved (available now) devs:", sorted(RESERVED))
print(f"change requests={len(change_requests)} reviews={len(change_reviews)} applied={len(change_histories)}")
print("assignments per project:", {p["project_id"]: len([a for a in assignments if a["project_id"] == p["project_id"]]) for p in projects})
