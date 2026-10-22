#!/usr/bin/env bash
# 전 화면 점검: 경영진(ceo) · PM(pm01) · 개발자(dev01) · 교육 담당자(edu01) 로 로그인해 모든 조회 화면을 호출하고
# HTTP 상태와 템플릿 오류 여부를 출력한다. 데이터는 바꾸지 않는다.
#   ./scripts/smoke_test.sh [http://127.0.0.1:5001]
set -u
B=${1:-http://127.0.0.1:5001}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
q() { docker exec -i si_pms_db mysql -uroot -proot1234 --default-character-set=utf8mb4 -N si_pms -e "$1" 2>/dev/null; }
# 프로젝트 번호는 시드 생성 결과에 따라 바뀌므로 DB 에서 찾는다
PM_INPROG=$(q "SELECT a.project_id FROM assignment a JOIN job_role r USING(role_id) JOIN project p USING(project_id) WHERE a.emp_id=3 AND r.role_code='PM' AND p.status='IN_PROGRESS' LIMIT 1")
PM_DONE=$(q "SELECT a.project_id FROM assignment a JOIN job_role r USING(role_id) JOIN project p USING(project_id) WHERE a.emp_id=3 AND r.role_code='PM' AND p.status='COMPLETED' LIMIT 1")
DEV_INPROG=$(q "SELECT a.project_id FROM assignment a JOIN project p USING(project_id) WHERE a.emp_id=4 AND p.status='IN_PROGRESS' LIMIT 1")
FIRST=$(q "SELECT MIN(project_id) FROM project")
PLANNED=$(q "SELECT MIN(project_id) FROM project WHERE status='PLANNED'")
EVALED=$(q "SELECT project_id FROM evaluation WHERE status<>'REQUESTED' GROUP BY project_id ORDER BY COUNT(*) DESC LIMIT 1")
login() { curl -s -c "$T/$1" -o /dev/null "$B/auth/login"; curl -s -b "$T/$1" -c "$T/$1" -o /dev/null -d "login_id=$1&password=pass1234" "$B/auth/login"; }
check() { # user path expected
  code=$(curl -s -b "$T/$1" -o "$T/page" -w "%{http_code}" "$B$2")
  err=$(grep -c -iE "Traceback|Internal Server Error|UndefinedError|jinja2.exceptions" "$T/page")
  mark="ok"; { [ "$code" != "$3" ] || [ "$err" != "0" ]; } && { mark="FAIL"; fail=$((fail+1)); }
  printf "%-5s %-6s %-60s %s (기대 %s)\n" "$mark" "$1" "$2" "$code" "$3"
}
for u in ceo pm01 dev01 edu01; do login $u; done
CR=$(curl -s -b "$T/ceo" "$B/reports/changes" | grep -o '/changes/[0-9]*' | head -1)
TOKEN=$(curl -s -b "$T/pm01" "$B/evaluations" | grep -o '/customer-eval/[0-9a-f]*' | head -1)
for p in / /projects "/projects?status=COMPLETED" /projects/$FIRST /projects/$PM_INPROG /projects/$PLANNED /projects/new /employees \
         "/employees?emp_type=DEV&grade=%EA%B3%A0%EA%B8%89&skill_id=10&available_on=2026-11-01" /employees/3 /employees/1 \
         /me/edit /evaluations "/reports/staffing?date=2025-06-01" /reports/staffing /reports/evaluations \
         "/reports/evaluations?project_id=$EVALED" /reports/incentive "/reports/incentive?year=2025" /reports/changes \
         "/reports/changes?status=REVIEWING" "$CR" /reports/training "/reports/training?status=NOT_APPLIED"; do check ceo "$p" 200; done
check ceo /training 403
for p in / /evaluations /me/skills /projects/$PM_DONE /projects/$PM_INPROG "$CR"; do check pm01 "$p" 200; done
check pm01 /employees/4 403
check pm01 /reports/changes 403
for p in / /me/edit /me/skills /evaluations /projects/$DEV_INPROG /me/training; do check dev01 "$p" 200; done
check dev01 /training 403
check dev01 /reports/training 403
PLAN=$(curl -s -b "$T/edu01" "$B/training" | grep -o 'plans/new?emp_id=[0-9]*&amp;project_id=[0-9]*' | head -1 | sed 's/&amp;/\&/g')
for p in / /training /reports/training "/training/$PLAN" /projects; do check edu01 "$p" 200; done
check edu01 /employees 403
check dev01 /employees 403
check dev01 /employees/3 403
check dev01 "$CR" 403
[ -n "$TOKEN" ] && check anon "$TOKEN" 200
check anon /auth/signup 200
echo "---"; [ $fail -eq 0 ] && echo "전체 통과" || { echo "실패 $fail 건"; exit 1; }
