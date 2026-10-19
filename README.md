# SI-PMS — SI 프로젝트 인력·평가 관리 시스템

Database Design Team Project (Fall 2026). 100명 규모 SI 업체의 **프로젝트–투입 인력–직무–기간** 관리와 **프로젝트 종료 시 고객/PM/동료 평가** 를 지원하는 사내 웹 시스템.

| 구분 | 내용 |
|---|---|
| DBMS | MySQL 8.0 (Docker) — 21 테이블, 4 뷰, 10 트리거, 2 프로시저 |
| 웹 | Python 3 + Flask + PyMySQL (서버 렌더링, ORM 미사용 → 데모 SQL 과 화면 1:1) |
| 설계 | IE 표기법 ERD, 직원·평가 슈퍼타입-서브타입, 발주처 별도 엔티티, M:N 전부 해소, 1:N Total:Total 없음 |

## 빠른 시작

```bash
# 1) DB 기동 (최초 실행 시 db/init/*.sql 이 자동 적재됨: 스키마 → 트리거/뷰 → 테스트 데이터)
docker compose up -d

# 2) 웹 앱
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run.py          # http://127.0.0.1:5001
```

데모 계정 (비밀번호 공통 `pass1234`)

| 아이디 | 역할 | 용도 |
|---|---|---|
| `ceo`, `exec01` | 경영진 | 직원 검색, 투입 관리, 시점별 현황, 평가/인센티브 리포트 |
| `pm01` | 개발자(특급), 종료 프로젝트 PM | PM 평가 입력, 고객 평가 의뢰·보고 |
| `dev01` | 개발자(중급) | 내 정보/기술 관리, 동료 평가 |

DB 재적재: `./db/reset.sh` (컨테이너 유지) 또는 `docker compose down -v && docker compose up -d`
MySQL 접속: `docker exec -it si_pms_db mysql -upms -ppms1234 si_pms`

## 디렉터리

```
db/init/      00_privileges.sql  01_schema.sql(DDL)  02_logic.sql(프로시저·트리거·뷰)  03_seed.sql(테스트 데이터)
db/demo/      demo_scenarios.sql(데모 시나리오 S1~S6)  constraint_tests.sql(비즈니스 규칙 검증)
db/perf/      perf_indexes.sql(성능 향상 기법 적용)
scripts/      gen_seed.py(시드 생성기)  gen_table_spec.py(테이블 정의서 생성)  perf_benchmark.py(성능 실험)
app/          Flask 앱 (auth / employees / projects / evaluations / reports 블루프린트 + templates)
docs/         산출물 문서 (아래)
```

## 산출물 문서 (과제 일정 대응)

| 일정 | 산출물 | 파일 |
|---|---|---|
| 10/26 분석 보고 | 요구사항 정의서 | `docs/01_요구사항정의서.md` |
| 11/09 설계 보고 | E-R Diagram (IE 표기) | `docs/02_ERD.md` (Mermaid), `docs/erd.dbml` (dbdiagram.io) |
| | 데이터베이스 정의서 | `docs/03_테이블정의서.md` (DB 에서 자동 생성) |
| | CRUD Matrix | `docs/04_CRUD매트릭스.md` |
| 11/23 구축 보고 | 생성·적재 스크립트, 증빙 | `db/init/*.sql`, `db/demo/constraint_tests.sql` |
| 12/07 최종 보고 | 데모 시나리오 (SQL) | `docs/05_데모시나리오.md`, `docs/05_데모시나리오_실행결과.txt` |
| | 성능 향상 기법 및 실험 결과 | `docs/06_성능향상기법_실험.md`, `docs/06_perf_results.md` |
| | 핵심 설계 결정 보고서 | `docs/07_핵심설계결정.md` |
| | 시스템 아키텍처 | 본 문서 §아키텍처 |

## 아키텍처

```
브라우저 ──HTTP──▶ Flask (app/)                         ──PyMySQL──▶ MySQL 8.0 (si_pms)
             auth        회원가입·ID 중복확인·로그인·권한      │  employee ⊃ developer | staff, user_account
             employees   내 정보·보유기술·직원 검색·경력       │  client → client_contact → project → assignment
             projects    프로젝트·투입(트리거 검증)·종료 처리   │  evaluation ⊃ customer_eval | pm_eval | peer_eval → eval_detail
             evaluations 평가 할 일·PM/동료 평가·고객 평가 의뢰 │  트리거: 채번(BR-02), 투입 검증(BR-01~07), 평가 검증(BR-08~14), 이력(BR-15)
             reports     대시보드·시점별 현황·평가·인센티브     │  뷰: v_employee, v_assignment_detail, v_eval_score, v_project_eval_summary
발주처 담당자 ──토큰 링크──▶ /customer-eval/<token> (로그인 없음)
```

- **무결성 규칙은 DB 에서** (트리거/CHECK/UNIQUE/FK) — UI 를 거치지 않는 SQL 적재에도 동일 적용. 위반 시 `SIGNAL` 메시지를 화면에 그대로 표시
- **워크플로우/권한은 앱에서** (경영진 전용 라우트, 본인 정보만 수정, 의뢰 PM 만 보고)
- 비밀번호 PBKDF2-SHA256 해시, 주민등록번호 화면 마스킹, 모든 쿼리 파라미터 바인딩

## 성능 실험 재현

```bash
.venv/bin/python scripts/perf_benchmark.py --rows 1000000   # 별도 DB si_pms_perf 에 100만 건 적재 후 A/B/C 비교, 종료 시 삭제
```
