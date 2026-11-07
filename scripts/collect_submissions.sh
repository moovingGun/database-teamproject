#!/usr/bin/env bash
# 제출 파일만 docs/제출물/ 에 일정별로 모은다 (원본을 복사하므로 원본을 고친 뒤 다시 실행)
#   ./scripts/collect_submissions.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=docs/제출물
rm -rf "$OUT"
mkdir -p "$OUT/1차_분석보고_1026" "$OUT/2차_설계보고_1109/ERD" "$OUT/3차_구축보고_1123/SQL" "$OUT/3차_구축보고_1123/적재증빙" "$OUT/4차_최종보고_1207"

# 1차 (10/26): 요구사항 정의서 — Problem Description only, 교수님 예시 양식
cp docs/01-1_요구사항정의서.xlsx "$OUT/1차_분석보고_1026/"

# 2차 (11/09): E-R Diagram · 데이터베이스 정의서 · CRUD Matrix
cp docs/erd/*.png "$OUT/2차_설계보고_1109/ERD/"
cp docs/03-1_CRUD_매트릭스.xlsx docs/03-2_표준용어-도메인-코드정의서.xlsx "$OUT/2차_설계보고_1109/"
[ -f docs/03-3_테이블정의서.xlsx ] && cp docs/03-3_테이블정의서.xlsx "$OUT/2차_설계보고_1109/"
cp docs/08_시나리오_선정.md "$OUT/2차_설계보고_1109/08_시나리오_선정(특화A·B,대표S2).md"

# 3차 (11/23): 생성·적재 스크립트(실행 순서대로) + 적재 증빙
cp db/init/00_privileges.sql db/init/01_schema.sql db/init/02_logic.sql db/init/03_seed.sql db/init/04_privileges.sql "$OUT/3차_구축보고_1123/SQL/"
cp db/demo/constraint_tests.sql "$OUT/3차_구축보고_1123/SQL/05_constraint_tests.sql"
cp docs/05_데모시나리오_실행결과.txt "$OUT/3차_구축보고_1123/적재증빙/"
mkdir -p "$OUT/3차_구축보고_1123/적재증빙/screenshots" && cp docs/screenshots/*.jpg "$OUT/3차_구축보고_1123/적재증빙/screenshots/"

# 4차 (12/07): 데모 시나리오 SQL · 성능 실험 · 설계 결정 (보고서 본문 자료, 최종 양식 변환 전)
cp db/demo/demo_scenarios.sql "$OUT/4차_최종보고_1207/"
cp docs/05_데모시나리오.md docs/06_성능향상기법_실험.md docs/07_핵심설계결정.md docs/08_시나리오_선정.md "$OUT/4차_최종보고_1207/"

cat > "$OUT/README.md" <<'EOF'
# 제출물

과제 PDF 3. Schedule 의 산출물만 일정별로 모았습니다. 원본은 `docs/`·`db/` 에 있고, `./scripts/collect_submissions.sh` 를 실행하면 최신 원본으로 다시 채워집니다. **이 폴더의 파일을 직접 고치지 마세요.**

| 일정 | 산출물 (PDF) | 파일 | 상태 |
|---|---|---|---|
| 1차 10/26 | 요구사항 정의서 ("Problem Description" only) | `1차_분석보고_1026/01-1_요구사항정의서.xlsx` | 제출 완료 |
| 2차 11/09 | E-R Diagram | `2차_설계보고_1109/ERD/*.png` 6장 (IE 표기, 서브타입 기호) | 준비됨 |
| 2차 11/09 | 데이터베이스 정의서 (각주 2: 테이블 정의서 + 조별 특화 비즈니스 로직 고도화 방안) | `2차_설계보고_1109/03-3_테이블정의서.xlsx` (테이블 목록 · 컬럼 정의 · 관계 · DB 객체 · 고도화 방안 5시트) | 준비됨 |
| 2차 11/09 | 표준용어·도메인·코드 정의서 (교수님 예시 03-2) | `2차_설계보고_1109/03-2_표준용어-도메인-코드정의서.xlsx` | 준비됨 |
| 2차 11/09 | CRUD Matrix (교수님 예시 03-1) | `2차_설계보고_1109/03-1_CRUD_매트릭스.xlsx` | 준비됨 |
| 2차 11/09 | 조별 특화 시나리오 선정 (A·B 채택 이유, 대표 데모 S2) — 고도화 방안 보조 자료 | `2차_설계보고_1109/08_시나리오_선정(특화A·B,대표S2).md` | 준비됨 |
| 3차 11/23 | 데이터베이스 생성 및 적재 스크립트 | `3차_구축보고_1123/SQL/00~04*.sql` (실행 순서대로), `05_constraint_tests.sql` (규칙 검증) | 준비됨 |
| 3차 11/23 | 테이블 생성 및 데이터 적재 증빙 | `3차_구축보고_1123/적재증빙/` (데모 실행 결과, 화면 24장) | 준비됨 |
| 4차 12/07 | 최종보고서: 아키텍처, 데모 시나리오(SQL), 성능 실험, 핵심 설계 결정 | `4차_최종보고_1207/` (SQL + 마크다운 자료, 시나리오 선정 포함) | 보고서 양식으로 변환 필요 |

제출 규칙(PDF 4절): 테이블 생성·테스트 데이터 삽입 SQL 은 별도 파일로 반드시 포함. 각 일정 23:59 LMS, 1시간 늦을 때마다 10점 감점.
EOF
echo "collected into $OUT:"; find "$OUT" -type f | sort | sed 's|^docs/제출물/|  |'
