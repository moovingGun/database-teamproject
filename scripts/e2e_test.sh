#!/usr/bin/env bash
# 쓰기 흐름 점검 (데이터가 바뀌므로 끝나면 ./db/reset.sh 로 되돌릴 것)
#   ./scripts/e2e_test.sh [http://127.0.0.1:5001]
# 각 단계는 화면에 뜨는 메시지(flash)와 DB 결과를 함께 출력한다. [기대] 와 실제를 비교하면 된다.
set -u
B=${1:-http://127.0.0.1:5001}
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
q() { docker exec -i si_pms_db mysql -uroot -proot1234 --default-character-set=utf8mb4 -N si_pms -e "$1" 2>/dev/null; }
flash() { grep -o '<div class="flash [a-z]*">[^<]*' "$T/p" | sed 's/<div class="flash //; s/">/ | /'; }
login() { curl -s -c "$T/$1" -o /dev/null "$B/auth/login"; curl -s -b "$T/$1" -c "$T/$1" -o /dev/null -d "login_id=$1&password=${2:-pass1234}" "$B/auth/login"; }
post() { local u=$1 path=$2; shift 2; curl -s -b "$T/$u" -c "$T/$u" -o "$T/p" -L "$@" "$B$path"; flash; }
for u in ceo pm01 dev01; do login $u; done

echo "== 1. 회원가입: 중복 ID [기대: 에러 메시지]"
curl -s -c "$T/new" -o /dev/null "$B/auth/signup"
F=(--data-urlencode password=test12345 --data-urlencode password2=test12345 --data-urlencode emp_name=테스트신입
   --data-urlencode resident_reg_no=990505-1123456 --data-urlencode education_level=학사 --data-urlencode hire_date=2026-10-19
   --data-urlencode emp_type=DEV --data-urlencode skill_grade=초급 --data-urlencode career_start_date=2026-10-19)
curl -s -b "$T/new" -o "$T/p" --data-urlencode login_id=dev01 "${F[@]}" "$B/auth/signup"; grep -o 'class="err">[^<]*' "$T/p"
echo "== 2. 회원가입: 새 ID [기대: 사번 E26xxxx 부여]"
post new /auth/signup --data-urlencode login_id=hong_test01 "${F[@]}"
login hong_test01 test12345; q "SELECT emp_no, login_id FROM employee e JOIN user_account a USING(emp_id) WHERE login_id='hong_test01'"

echo "== 3. PM 평가 입력 → 같은 팀원 재입력 [기대: 성공 후 BR-13 거부]"
TARGET=$(curl -s -b "$T/pm01" "$B/evaluations" | grep -o 'project_id=[0-9]*&amp;eval_type=PM&amp;evaluatee_emp_id=[0-9]*' | head -1 | sed 's/&amp;/\&/g')
post pm01 "/evaluations/new?$TARGET" --data-urlencode score_1=5 --data-urlencode score_2=4 --data-urlencode comment_1=핵심모듈완수 --data-urlencode recommend_incentive=1
post pm01 "/evaluations/new?$TARGET" --data-urlencode score_1=3 --data-urlencode score_2=3

echo "== 4. 고객 평가: 토큰 링크로 제출 → PM 보고 [기대: REPORTED]"
TOKEN=$(curl -s -b "$T/pm01" "$B/evaluations" | grep -o '/customer-eval/[0-9a-f]*' | head -1)
PRJ=$(q "SELECT ev.project_id FROM customer_eval ce JOIN evaluation ev USING(eval_id) WHERE ce.access_token='${TOKEN##*/}'")
curl -s -o "$T/c" "$B$TOKEN"; A=()
for i in $(grep -o 'name="score_[0-9]*_1"' "$T/c" | grep -o '[0-9]*_1' | cut -d_ -f1 | sort -u); do A+=(--data-urlencode "score_${i}_1=5" --data-urlencode "score_${i}_2=4"); done
curl -s -o "$T/c2" "${A[@]}" "$B$TOKEN"; grep -o '<h1>[^<]*' "$T/c2"
curl -s -b "$T/pm01" -o /dev/null -X POST "$B/projects/$PRJ/customer-eval/report"
q "SELECT status, COUNT(*) FROM evaluation WHERE project_id=$PRJ AND eval_type='CUSTOMER' GROUP BY status"

echo "== 5. 투입: 100% 투입자 추가 [기대: BR-05 거부] / 가용 개발자 [기대: 성공]"
post ceo /projects/16/assignments --data-urlencode emp_id=3 --data-urlencode role_id=5 --data-urlencode start_date= --data-urlencode end_date= --data-urlencode participation_rate=50
post ceo /projects/16/assignments --data-urlencode emp_id=5 --data-urlencode role_id=6 --data-urlencode start_date=2026-11-01 --data-urlencode end_date= --data-urlencode participation_rate=100

echo "== 6. 기술등급 변경 [기대: 이력 자동 기록]"
post ceo /employees/5/grade --data-urlencode skill_grade=특급 --data-urlencode reason=e2e승급
q "SELECT old_grade, new_grade, changed_by_emp_id, reason FROM grade_history WHERE emp_id=5 ORDER BY history_id DESC LIMIT 1"

echo "== 7. 프로젝트 등록 → 착수 → PM 투입 → 종료 [기대: 번호 자동, 실제 종료일 따로 기록]"
curl -s -b "$T/ceo" -o /dev/null --data-urlencode project_name=e2e프로젝트 --data-urlencode client_id=1 --data-urlencode start_date=2026-11-01 \
  --data-urlencode end_date=2027-03-31 --data-urlencode status=PLANNED --data-urlencode contract_amount=100000000 "$B/projects/new"
P=$(q "SELECT MAX(project_id) FROM project")
curl -s -b "$T/ceo" -o /dev/null -d action=start "$B/projects/$P/status"
curl -s -b "$T/ceo" -o /dev/null --data-urlencode emp_id=7 --data-urlencode role_id=1 --data-urlencode start_date= --data-urlencode end_date= --data-urlencode participation_rate=100 "$B/projects/$P/assignments"
curl -s -b "$T/ceo" -o /dev/null -d "action=complete&actual_end_date=2027-01-31" "$B/projects/$P/status"
q "SELECT project_code, status, end_date AS 종료예정일, actual_end_date AS 실제종료일, (SELECT MAX(end_date) FROM assignment WHERE project_id=$P) AS 투입종료 FROM project WHERE project_id=$P"

echo "== 8. 개발자: 보유 기술 추가·정보 수정·동료 평가"
curl -s -b "$T/dev01" -o /dev/null -d "skill_id=2&proficiency=4&years_used=2.5&last_used_date=2026-10-01" "$B/me/skills"
curl -s -b "$T/dev01" -o /dev/null --data-urlencode emp_name=김상훈 --data-urlencode education_level=석사 --data-urlencode phone=010-1111-2222 --data-urlencode career_start_date=2019-07-13 "$B/me/edit"
PEER=$(curl -s -b "$T/dev01" "$B/evaluations" | grep -o 'project_id=[0-9]*&amp;eval_type=PEER&amp;evaluatee_emp_id=[0-9]*' | head -1 | sed 's/&amp;/\&/g')
post dev01 "/evaluations/new?$PEER" --data-urlencode score_1=4 --data-urlencode score_2=5 --data-urlencode is_anonymous=1
q "SELECT education_level, phone FROM employee WHERE emp_id=4"

echo "== 9. [시나리오 A] 변경요청 전체 흐름: 접수 → 검토안 → 승인 → 고객 동의 → 반영"
P15=$(q "SELECT CONCAT(end_date,' ',contract_amount) FROM project WHERE project_id=15"); echo "반영 전 project 15: $P15"
C=$(q "SELECT contact_id FROM client_contact WHERE client_id=(SELECT client_id FROM project WHERE project_id=15) LIMIT 1")
post pm01 /projects/15/changes --data-urlencode contact_id=$C --data-urlencode request_date=2026-10-20 --data-urlencode title=e2e검색필터추가 --data-urlencode content=상담이력검색필터 --data-urlencode reason=운영요청
CR=$(q "SELECT MAX(cr_id) FROM change_request"); NEWEND=$(q "SELECT DATE_ADD(end_date, INTERVAL 7 DAY) FROM project WHERE project_id=15")
post pm01 /changes/$CR/reviews --data-urlencode proposed_end_date=$NEWEND --data-urlencode additional_amount=1000000 --data-urlencode review_comment=1주추가
RV=$(q "SELECT MAX(review_id) FROM change_review WHERE cr_id=$CR")
echo "-- PM 이 승인 시도 [기대: 403]"; curl -s -b "$T/pm01" -o /dev/null -w "%{http_code}\n" -d "review_id=$RV&decision=APPROVED" "$B/changes/$CR/decision"
echo "-- 승인 전 고객 동의 [기대: BR-22 거부]"; post pm01 /changes/$CR/consent -d "review_id=$RV&contact_id=$C&consent_date=2026-10-21&consent=AGREED"
echo "-- 승인 전 반영 [기대: BR-23 거부]"; post pm01 /changes/$CR/apply -d "review_id=$RV"
post ceo /changes/$CR/decision --data-urlencode review_id=$RV --data-urlencode decision=APPROVED --data-urlencode decision_reason=e2e승인
OTHER=$(q "SELECT contact_id FROM client_contact WHERE client_id<>(SELECT client_id FROM project WHERE project_id=15) LIMIT 1")
echo "-- 다른 발주처 담당자로 동의 [기대: BR-22 거부]"; post pm01 /changes/$CR/consent -d "review_id=$RV&contact_id=$OTHER&consent_date=2026-10-21&consent=AGREED"
post pm01 /changes/$CR/consent -d "review_id=$RV&contact_id=$C&consent_date=2026-10-21&consent=AGREED" --data-urlencode consent_evidence=이메일회신
post pm01 /changes/$CR/apply -d "review_id=$RV"
echo "-- 같은 검토안 재반영 [기대: BR-23 거부]"; post pm01 /changes/$CR/apply -d "review_id=$RV"
q "SELECT cr_no, status FROM change_request WHERE cr_id=$CR; SELECT before_end_date, after_end_date, before_amount, after_amount FROM change_history WHERE review_id=$RV; SELECT end_date, contract_amount FROM project WHERE project_id=15"

echo "== 10. [시나리오 A] 위반 사례"
echo "-- 종료 프로젝트에 변경요청 [기대: BR-16 거부]"; C14=$(q "SELECT contact_id FROM client_contact WHERE client_id=(SELECT client_id FROM project WHERE project_id=14) LIMIT 1")
post pm01 /projects/14/changes --data-urlencode contact_id=$C14 --data-urlencode request_date=2026-10-20 --data-urlencode title=x --data-urlencode content=x
echo "-- 다른 발주처 담당자의 요청 [기대: BR-17 거부]"; post pm01 /projects/15/changes --data-urlencode contact_id=$OTHER --data-urlencode request_date=2026-10-20 --data-urlencode title=x --data-urlencode content=x
echo "-- 투입보다 이른 종료예정일 반영 [기대: BR-23 거부]"
post pm01 /projects/15/changes --data-urlencode contact_id=$C --data-urlencode request_date=2026-10-20 --data-urlencode title=e2e일정단축 --data-urlencode content=조기종료요청
CR2=$(q "SELECT MAX(cr_id) FROM change_request"); EARLY=$(q "SELECT DATE_ADD(start_date, INTERVAL 30 DAY) FROM project WHERE project_id=15")
post pm01 /changes/$CR2/reviews --data-urlencode proposed_end_date=$EARLY --data-urlencode additional_amount=-1000000
RV2=$(q "SELECT MAX(review_id) FROM change_review WHERE cr_id=$CR2")
curl -s -b "$T/ceo" -o /dev/null -d "review_id=$RV2&decision=APPROVED" "$B/changes/$CR2/decision"
curl -s -b "$T/pm01" -o /dev/null -d "review_id=$RV2&contact_id=$C&consent_date=2026-10-21&consent=AGREED" "$B/changes/$CR2/consent"
post pm01 /changes/$CR2/apply -d "review_id=$RV2"
echo "-- 승인 후 재검토(2차) → 1차 반영 시도 [기대: 상태 REVIEWING, BR-19 거부]"
post pm01 /changes/$CR2/reviews --data-urlencode proposed_end_date=$NEWEND --data-urlencode additional_amount=0 --data-urlencode review_comment=재검토
q "SELECT status FROM change_request WHERE cr_id=$CR2"
post pm01 /changes/$CR2/apply -d "review_id=$RV2"
echo "== 11. [시나리오 B] 교육: 계획 수립 → 신청 → 중복 신청 → 취소 → 재신청 → 수료 기록"
login edu01
CAND=$(curl -s -b "$T/edu01" "$B/training" | grep -o 'emp_id=[0-9]*&amp;project_id=[0-9]*' | head -1 | sed 's/&amp;/\&/g')
post edu01 "/training/plans/new?$CAND" --data-urlencode course_id=1 --data-urlencode due_date=2027-03-31 --data-urlencode improvement_goal=e2e의사소통 --data-urlencode reason=e2e평가의견
echo "-- 교육 담당자가 아닌 개발자가 계획 수립 [기대: 403]"; curl -s -b "$T/dev01" -o /dev/null -w "%{http_code}\n" "$B/training/plans/new?$CAND"
PL=$(q "SELECT plan_id FROM development_plan WHERE emp_id=4 ORDER BY plan_id DESC LIMIT 1")
S1=$(q "SELECT session_id FROM training_session WHERE course_id=1 AND start_at > NOW() ORDER BY start_at LIMIT 1")
post dev01 /me/training/apply -d "plan_id=$PL&session_id=$S1"
echo "-- 같은 일정 중복 신청 [기대: BR-27 거부]"; post dev01 /me/training/apply -d "plan_id=$PL&session_id=$S1"
SX=$(q "SELECT session_id FROM training_session WHERE course_id<>1 AND start_at > NOW() LIMIT 1")
echo "-- 추천 과정이 아닌 일정 신청 [기대: BR-26 거부]"; post dev01 /me/training/apply -d "plan_id=$PL&session_id=$SX"
OTHERPL=$(q "SELECT plan_id FROM development_plan WHERE emp_id<>4 LIMIT 1")
echo "-- 남의 계획으로 신청 [기대: 403]"; curl -s -b "$T/dev01" -o /dev/null -w "%{http_code}\n" -d "plan_id=$OTHERPL&session_id=$S1" "$B/me/training/apply"
EN=$(q "SELECT MAX(enroll_id) FROM training_enrollment WHERE plan_id=$PL")
post dev01 /me/training/$EN/cancel --data ""
post dev01 /me/training/apply -d "plan_id=$PL&session_id=$S1"
q "SELECT te.status, COUNT(*) FROM training_enrollment te WHERE plan_id=$PL GROUP BY te.status"
echo "-- 시작 전 교육에 수료 기록 [기대: BR-29 거부]"; EN2=$(q "SELECT MAX(enroll_id) FROM training_enrollment WHERE plan_id=$PL")
post edu01 /training/enrollments/$EN2/result -d "result=COMPLETED"
PEND=$(q "SELECT te.enroll_id FROM training_enrollment te JOIN training_session ts USING(session_id) WHERE te.status='APPLIED' AND ts.end_at <= NOW() LIMIT 1")
echo "-- 끝난 교육 수료 기록 [기대: 성공, 기술등급 그대로]"; G0=$(q "SELECT skill_grade FROM developer WHERE emp_id=(SELECT dp.emp_id FROM training_enrollment te JOIN development_plan dp USING(plan_id) WHERE enroll_id=$PEND)")
post edu01 /training/enrollments/$PEND/result -d "result=COMPLETED"
q "SELECT te.status, d.skill_grade, '$G0' AS before_grade FROM training_enrollment te JOIN development_plan dp USING(plan_id) JOIN developer d ON d.emp_id=dp.emp_id WHERE enroll_id=$PEND"
echo "== 끝. ./db/reset.sh 로 데이터를 되돌리세요."
