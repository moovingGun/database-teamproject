#!/usr/bin/env bash
# 전 화면 점검: 경영진(ceo) · PM(pm01) · 개발자(dev01) 로 로그인해 모든 조회 화면을 호출하고
# HTTP 상태와 템플릿 오류 여부를 출력한다. 데이터는 바꾸지 않는다.
#   ./scripts/smoke_test.sh [http://127.0.0.1:5001]
set -u
B=${1:-http://127.0.0.1:5001}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0
login() { curl -s -c "$T/$1" -o /dev/null "$B/auth/login"; curl -s -b "$T/$1" -c "$T/$1" -o /dev/null -d "login_id=$1&password=pass1234" "$B/auth/login"; }
check() { # user path expected
  code=$(curl -s -b "$T/$1" -o "$T/page" -w "%{http_code}" "$B$2")
  err=$(grep -c -iE "Traceback|Internal Server Error|UndefinedError|jinja2.exceptions" "$T/page")
  mark="ok"; { [ "$code" != "$3" ] || [ "$err" != "0" ]; } && { mark="FAIL"; fail=$((fail+1)); }
  printf "%-5s %-6s %-60s %s (기대 %s)\n" "$mark" "$1" "$2" "$code" "$3"
}
for u in ceo pm01 dev01; do login $u; done
CR=$(curl -s -b "$T/ceo" "$B/reports/changes" | grep -o '/changes/[0-9]*' | head -1)
TOKEN=$(curl -s -b "$T/pm01" "$B/evaluations" | grep -o '/customer-eval/[0-9a-f]*' | head -1)
for p in / /projects "/projects?status=COMPLETED" /projects/1 /projects/15 /projects/25 /projects/new /employees \
         "/employees?emp_type=DEV&grade=%EA%B3%A0%EA%B8%89&skill_id=10&available_on=2026-11-01" /employees/3 /employees/1 \
         /me/edit /evaluations "/reports/staffing?date=2025-06-01" /reports/staffing /reports/evaluations \
         "/reports/evaluations?project_id=1" /reports/incentive "/reports/incentive?year=2025" /reports/changes \
         "/reports/changes?status=REVIEWING" "$CR"; do check ceo "$p" 200; done
for p in / /evaluations /me/skills /projects/14 /projects/15 "$CR"; do check pm01 "$p" 200; done
check pm01 /employees/4 403
check pm01 /reports/changes 403
for p in / /me/edit /me/skills /evaluations /projects/16; do check dev01 "$p" 200; done
check dev01 /employees 403
check dev01 /employees/3 403
check dev01 "$CR" 403
[ -n "$TOKEN" ] && check anon "$TOKEN" 200
check anon /auth/signup 200
echo "---"; [ $fail -eq 0 ] && echo "전체 통과" || { echo "실패 $fail 건"; exit 1; }
