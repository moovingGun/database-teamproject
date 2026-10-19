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

ROLLBACK;
SELECT '검증 종료 (ROLLBACK 완료 - 데이터 변경 없음)' AS done;
