-- =====================================================================
--  비즈니스 규칙(트리거/제약) 검증 스크립트  — 구축 보고 "제약조건 동작 증빙"
--  실행: docker exec -i si_pms_db mysql -uroot -proot1234 --default-character-set=utf8mb4 --force si_pms < db/demo/constraint_tests.sql
--  * "→ 거부" 테스트는 ERROR 가 출력되어야 정상이며, --force 로 오류 후에도 계속 실행됨
--  * 마지막 ROLLBACK 으로 데이터는 원상 복구
-- =====================================================================
SET NAMES utf8mb4;
START TRANSACTION;

-- 진행 중 프로젝트(중복/투입률 검증용) 와 예정 프로젝트(신규 투입 검증용)
SET @prj_inprog := (SELECT project_id FROM project WHERE status = 'IN_PROGRESS' ORDER BY project_id LIMIT 1);
SET @prj_plan   := (SELECT project_id FROM project WHERE status = 'PLANNED'     ORDER BY project_id LIMIT 1);
SET @prj_done   := (SELECT project_id FROM project WHERE status = 'COMPLETED'   ORDER BY project_id LIMIT 1);
SET @pp_start := (SELECT start_date FROM project WHERE project_id = @prj_plan);
SET @pp_end   := (SELECT end_date   FROM project WHERE project_id = @prj_plan);
SET @pm_done  := (SELECT a.emp_id FROM assignment a JOIN job_role r ON r.role_id = a.role_id WHERE a.project_id = @prj_done AND r.role_code = 'PM' LIMIT 1);
SET @member   := (SELECT a.emp_id FROM assignment a WHERE a.project_id = @prj_done AND a.emp_id <> @pm_done LIMIT 1);
SET @staff    := (SELECT emp_id FROM staff LIMIT 1);
SET @junior   := (SELECT emp_id FROM developer WHERE skill_grade = '초급' LIMIT 1);
-- 예정 프로젝트 기간에 투입이 없는 고급 이상 개발자 2명
SET @expert_free := (SELECT d.emp_id FROM developer d JOIN employee e ON e.emp_id = d.emp_id
                      WHERE d.skill_grade IN ('고급','특급') AND e.hire_date <= @pp_start
                        AND NOT EXISTS (SELECT 1 FROM assignment a WHERE a.emp_id = d.emp_id AND a.start_date <= @pp_end AND a.end_date >= @pp_start)
                      ORDER BY d.emp_id LIMIT 1);
SET @expert_free2 := (SELECT d.emp_id FROM developer d JOIN employee e ON e.emp_id = d.emp_id
                      WHERE d.skill_grade IN ('고급','특급') AND e.hire_date <= @pp_start AND d.emp_id <> @expert_free
                        AND NOT EXISTS (SELECT 1 FROM assignment a WHERE a.emp_id = d.emp_id AND a.start_date <= @pp_end AND a.end_date >= @pp_start)
                      ORDER BY d.emp_id LIMIT 1);
-- 진행 중 프로젝트에 100% 투입된 개발자와, 그 기간과 겹치는 다른 진행 중 프로젝트
SET @busy_dev   := (SELECT emp_id FROM assignment WHERE project_id = @prj_inprog AND participation_rate = 100 LIMIT 1);
SET @busy_start := (SELECT start_date FROM assignment WHERE project_id = @prj_inprog AND emp_id = @busy_dev LIMIT 1);
SET @busy_end   := (SELECT end_date   FROM assignment WHERE project_id = @prj_inprog AND emp_id = @busy_dev LIMIT 1);
SET @other_prj  := (SELECT project_id FROM project WHERE status = 'IN_PROGRESS' AND project_id <> @prj_inprog
                     AND start_date <= @busy_end AND end_date >= @busy_start ORDER BY project_id LIMIT 1);
SELECT '--- 테스트 대상 ---' AS step, @prj_inprog AS prj_inprog, @prj_plan AS prj_plan, @prj_done AS prj_done,
       @expert_free AS expert_free, @expert_free2 AS expert_free2, @busy_dev AS busy_dev, @other_prj AS other_prj;

SELECT '[BR-01] 지원직(STAFF) 투입 → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_plan, @staff, 5, @pp_start, @pp_end);

SELECT '[BR-03] 프로젝트 기간 밖 투입 → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_plan, @expert_free, 5, DATE_SUB(@pp_start, INTERVAL 10 DAY), @pp_end);

SELECT '[BR-04] 동일 프로젝트 기간 중복 투입 → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_inprog, @busy_dev, 6, @busy_start, @busy_end);

SELECT '[BR-05] 투입률 100% 초과 (이미 100% 투입된 개발자를 겹치는 기간의 다른 프로젝트에 50% 추가) → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date, participation_rate)
SELECT @other_prj, @busy_dev, 5, GREATEST(start_date, @busy_start), LEAST(end_date, @busy_end), 50 FROM project WHERE project_id = @other_prj;

SELECT '[정상] 가용 고급 개발자를 예정 프로젝트 PM 으로 투입 → 성공 (1 row)' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_plan, @expert_free, 1, @pp_start, @pp_end);
SELECT ROW_COUNT() AS inserted_rows;

SELECT '[BR-06] 같은 기간 두 번째 PM → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_plan, @expert_free2, 1, @pp_start, @pp_end);

SELECT '[BR-07] 초급 개발자를 PL 로 → 거부' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date) VALUES (@prj_plan, @junior, 2, @pp_start, @pp_end);

SELECT '[BR-05/CHECK] 투입률 120% → 거부 (트리거가 CHECK 보다 먼저 검증)' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date, participation_rate) VALUES (@prj_plan, @expert_free2, 5, @pp_start, @pp_end, 120);

SELECT '[정상] 같은 개발자를 50% + 50% 로 서로 다른 두 프로젝트에 투입 → 성공' AS test;
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date, participation_rate) VALUES (@prj_plan, @expert_free2, 3, @pp_start, @pp_end, 50);
INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date, participation_rate)
SELECT project_id, @expert_free2, 3, GREATEST(start_date, @pp_start), LEAST(end_date, @pp_end), 50 FROM project WHERE status = 'PLANNED' AND project_id <> @prj_plan AND start_date <= @pp_end AND end_date >= @pp_start LIMIT 1;
SELECT ROW_COUNT() AS inserted_rows;

SELECT '[BR-08] 진행 중 프로젝트에 평가 등록 → 거부' AS test;
INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type) VALUES (@prj_inprog, @busy_dev, 'PEER');

SELECT '[BR-09] 미참여자를 피평가자로 → 거부' AS test;
INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type) VALUES (@prj_done, @expert_free, 'PEER');

SELECT '[BR-13] PM 이 아닌 사람의 PM 평가 → 거부' AS test;
INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type) VALUES (@prj_done, @pm_done, 'PM');
INSERT INTO pm_eval (eval_id, evaluator_emp_id) VALUES (LAST_INSERT_ID(), @member);

SELECT '[BR-14] 자기 자신 동료 평가 → 거부' AS test;
INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type) VALUES (@prj_done, @member, 'PEER');
INSERT INTO peer_eval (eval_id, evaluator_emp_id) VALUES (LAST_INSERT_ID(), @member);

SELECT '[BR-10] PEER 평가에 PM 서브타입 등록 → 거부' AS test;
INSERT INTO pm_eval (eval_id, evaluator_emp_id) VALUES (LAST_INSERT_ID(), @pm_done);

SELECT '[CHECK] 평점 6점 → 거부' AS test;
INSERT INTO eval_detail (eval_id, item_id, score) VALUES (LAST_INSERT_ID(), 1, 6);

SELECT '[UK] 로그인 ID 중복(dev01) → 거부' AS test;
INSERT INTO employee (emp_name, resident_reg_no, education_level, hire_date, emp_type) VALUES ('테스트', '990101-1234567', '학사', CURDATE(), 'DEV');
INSERT INTO user_account (emp_id, login_id, password_hash) VALUES (LAST_INSERT_ID(), 'dev01', 'x');

SELECT '[BR-02] 사번 자동 채번 확인 (E26xxxx) → 성공' AS test;
SELECT emp_no FROM employee WHERE resident_reg_no = '990101-1234567';

SELECT '[BR-15] 기술등급 변경 → grade_history 자동 기록 → 성공' AS test;
SET @app_user_id = 1, @grade_change_reason = '검증 테스트';
UPDATE developer SET skill_grade = '중급' WHERE emp_id = @junior;
SELECT emp_id, old_grade, new_grade, changed_by_emp_id, reason FROM grade_history WHERE emp_id = @junior ORDER BY history_id DESC LIMIT 1;

-- ---------------------------------------------------------------------
-- [BR-30] 직원 슈퍼타입-서브타입 (판별자 일치 · 배타)
-- ---------------------------------------------------------------------
SET @st30 := (SELECT emp_id FROM staff WHERE department = 'RND' LIMIT 1);
SET @dv30 := (SELECT emp_id FROM developer LIMIT 1);
SELECT '[BR-30] 지원직 직원에게 개발자 서브타입 추가 → 거부' AS test;
INSERT INTO developer (emp_id, skill_grade, career_start_date) VALUES (@st30, '초급', CURDATE());
SELECT '[BR-30] 개발자 직원에게 지원직 서브타입 추가 → 거부' AS test;
INSERT INTO staff (emp_id, department) VALUES (@dv30, 'RND');
SELECT '[BR-30] 서브타입이 있는 직원의 구분 변경 → 거부' AS test;
UPDATE employee SET emp_type = 'STAFF' WHERE emp_id = @dv30;

-- ---------------------------------------------------------------------
-- [조별 특화 시나리오 A] 변경요청 규칙 (BR-16 ~ BR-23)
-- ---------------------------------------------------------------------
SET @cr_prj := (SELECT project_id FROM change_request WHERE status = 'REVIEWING' ORDER BY cr_id LIMIT 1);
SET @cr_pm  := (SELECT received_by_emp_id FROM change_request WHERE project_id = @cr_prj LIMIT 1);
SET @cr_contact := (SELECT contact_id FROM client_contact WHERE client_id = (SELECT client_id FROM project WHERE project_id = @cr_prj) LIMIT 1);
SET @cr_pending := (SELECT cr_id FROM change_request WHERE status = 'REVIEWING' ORDER BY cr_id LIMIT 1);
SET @rv_pending := (SELECT MAX(review_id) FROM change_review WHERE cr_id = @cr_pending);
SET @rv_decided := (SELECT review_id FROM change_review WHERE decision = 'REJECTED' LIMIT 1);
SET @non_pm := (SELECT a.emp_id FROM assignment a JOIN job_role r ON r.role_id = a.role_id WHERE a.project_id = @cr_prj AND r.role_code <> 'PM' LIMIT 1);

SELECT '[BR-18] PM 이 아닌 참여자가 변경요청 접수 → 거부' AS test;
INSERT INTO change_request (project_id, contact_id, received_by_emp_id, request_date, title, content)
VALUES (@cr_prj, @cr_contact, @non_pm, CURDATE(), 'x', 'x');

SELECT '[BR-19] 차수를 건너뛴 검토안 (3차) → 거부' AS test;
INSERT INTO change_review (cr_id, version_no, reviewer_emp_id, proposed_end_date) VALUES (@cr_pending, 9, @cr_pm, CURDATE());

SELECT '[BR-21] 경영진이 아닌 직원의 승인 → 거부' AS test;
UPDATE change_review SET decision = 'APPROVED', decided_by_emp_id = @cr_pm, decided_at = CURDATE() WHERE review_id = @rv_pending;

SELECT '[BR-20] 결정이 난 검토안의 금액 수정 → 거부' AS test;
UPDATE change_review SET additional_amount = additional_amount + 1 WHERE review_id = @rv_decided;

SELECT '[BR-23] 승인·동의 전 적용이력 직접 입력 → 거부' AS test;
INSERT INTO change_history (review_id, before_end_date, after_end_date, applied_by_emp_id) VALUES (@rv_pending, CURDATE(), CURDATE(), 1);

SELECT '[BR-16] 요청번호 자동 채번 확인 → 성공' AS test;
INSERT INTO change_request (project_id, contact_id, received_by_emp_id, request_date, title, content)
VALUES (@cr_prj, @cr_contact, @cr_pm, CURDATE(), '채번 확인', '채번 확인');
SELECT cr_no, status FROM change_request ORDER BY cr_id DESC LIMIT 1;

-- ---------------------------------------------------------------------
-- [조별 특화 시나리오 B] 역량 개선·교육 규칙 (BR-24 ~ BR-29)
-- ---------------------------------------------------------------------
SET @trainer := (SELECT emp_id FROM staff WHERE is_training_manager = 1 LIMIT 1);
SET @not_trainer := (SELECT emp_id FROM staff WHERE is_training_manager = 0 AND department = 'MANAGEMENT' LIMIT 1);
-- 같은 과정을 추천받은 계획이 2건 이상인 과정의 첫 계획 (정원 초과 검사에 다른 대상자가 필요)
SET @pl := (SELECT MIN(plan_id) FROM development_plan
             WHERE course_id = (SELECT course_id FROM development_plan GROUP BY course_id HAVING COUNT(*) >= 2 ORDER BY course_id LIMIT 1));
SET @pl_course := (SELECT course_id FROM development_plan WHERE plan_id = @pl);
SET @pl_emp := (SELECT emp_id FROM development_plan WHERE plan_id = @pl);
SET @future_ok := (SELECT session_id FROM training_session WHERE course_id = @pl_course AND start_at > NOW()
                     AND session_id NOT IN (SELECT te.session_id FROM training_enrollment te JOIN development_plan dp USING (plan_id)
                                             WHERE dp.emp_id = @pl_emp AND te.status <> 'CANCELLED') ORDER BY start_at LIMIT 1);
SET @future_other := (SELECT session_id FROM training_session WHERE course_id <> @pl_course AND start_at > NOW() LIMIT 1);
SET @past_ok := (SELECT session_id FROM training_session WHERE course_id = @pl_course AND start_at < NOW() LIMIT 1);

SELECT '[BR-24] 진행 중 프로젝트를 근거로 계획 수립 → 거부' AS test;
INSERT INTO development_plan (emp_id, project_id, course_id, manager_emp_id, improvement_goal, reason, created_date, due_date)
VALUES (@pl_emp, @prj_inprog, 1, @trainer, 'x', 'x', CURDATE(), CURDATE());

SELECT '[BR-25] 교육 담당자가 아닌 직원이 계획 수립 → 거부' AS test;
INSERT INTO development_plan (emp_id, project_id, course_id, manager_emp_id, improvement_goal, reason, created_date, due_date)
SELECT emp_id, project_id, 1, @not_trainer, 'x', 'x', CURDATE(), CURDATE() FROM development_plan WHERE plan_id = @pl;

SELECT '[CHECK] 경영관리가 아닌 직원을 교육 담당자로 지정 → 거부' AS test;
UPDATE staff SET is_training_manager = 1 WHERE department = 'MARKETING' LIMIT 1;

SELECT '[BR-26] 추천 과정이 아닌 일정에 신청 → 거부' AS test;
INSERT INTO training_enrollment (plan_id, session_id) VALUES (@pl, @future_other);

SELECT '[BR-29] 이미 시작한 일정에 신청 → 거부' AS test;
INSERT INTO training_enrollment (plan_id, session_id) VALUES (@pl, @past_ok);

SELECT '[정상] 추천 과정의 예정 일정에 신청 → 성공' AS test;
INSERT INTO training_enrollment (plan_id, session_id) VALUES (@pl, @future_ok);
SELECT ROW_COUNT() AS inserted_rows;

SELECT '[BR-27] 같은 일정 중복 신청 → 거부' AS test;
INSERT INTO training_enrollment (plan_id, session_id) VALUES (@pl, @future_ok);

SELECT '[BR-29] 시작 전 교육에 수료 기록 → 거부' AS test;
UPDATE training_enrollment SET status = 'COMPLETED' WHERE plan_id = @pl AND session_id = @future_ok AND status = 'APPLIED';

SELECT '[BR-28] 정원이 찬 일정 신청 → 거부' AS test;
UPDATE training_session SET capacity = (SELECT COUNT(*) FROM training_enrollment WHERE session_id = @future_ok AND status <> 'CANCELLED') WHERE session_id = @future_ok;
INSERT INTO training_enrollment (plan_id, session_id)
SELECT dp.plan_id, @future_ok FROM development_plan dp
 WHERE dp.course_id = @pl_course AND dp.emp_id <> @pl_emp
   AND NOT EXISTS (SELECT 1 FROM training_enrollment x JOIN development_plan y USING (plan_id)
                    WHERE x.session_id = @future_ok AND y.emp_id = dp.emp_id AND x.status <> 'CANCELLED') LIMIT 1;

ROLLBACK;
SELECT '검증 종료 (ROLLBACK 완료 - 데이터 변경 없음)' AS done;
