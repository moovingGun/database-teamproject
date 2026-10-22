SET NAMES utf8mb4;
-- =====================================================================
--  애플리케이션 계정(pms) 권한 — 03_seed.sql 다음에 실행 (테이블이 있어야 테이블 단위 GRANT 가능)
-- ---------------------------------------------------------------------
--  [BR-30] 직원 슈퍼타입-서브타입 전체 참여
--   * employee / developer / staff 는 SELECT·UPDATE 만 허용 (직접 INSERT·DELETE 불가)
--   * 직원 등록은 sp_register_employee(직원 + 서브타입 한 번에)로만 → 서브타입 없는 직원이 생기지 않음
--   * 그 밖의 테이블은 SELECT·INSERT·UPDATE·DELETE, 프로시저는 EXECUTE
--  docker 초기화가 pms 에 준 si_pms 전체 권한(ALL)은 테이블 단위로 좁힐 수 없으므로 먼저 회수한다
-- =====================================================================
USE si_pms;

REVOKE IF EXISTS ALL PRIVILEGES ON `si\_pms`.* FROM 'pms'@'%';
REVOKE IF EXISTS ALL PRIVILEGES ON `si_pms`.* FROM 'pms'@'%';
GRANT SELECT, EXECUTE ON `si_pms`.* TO 'pms'@'%';

DROP PROCEDURE IF EXISTS tmp_grant_app_tables;
DELIMITER $$
CREATE PROCEDURE tmp_grant_app_tables()
BEGIN
  DECLARE v_done INT DEFAULT 0;
  DECLARE v_table VARCHAR(64);
  DECLARE c CURSOR FOR
    SELECT table_name FROM information_schema.tables
     WHERE table_schema = 'si_pms' AND table_type = 'BASE TABLE';
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;
  OPEN c;
  grant_loop: LOOP
    FETCH c INTO v_table;
    IF v_done THEN LEAVE grant_loop; END IF;
    IF v_table IN ('employee', 'developer', 'staff') THEN
      SET @sql = CONCAT('GRANT UPDATE ON si_pms.`', v_table, '` TO ''pms''@''%''');
    ELSE
      SET @sql = CONCAT('GRANT INSERT, UPDATE, DELETE ON si_pms.`', v_table, '` TO ''pms''@''%''');
    END IF;
    PREPARE s FROM @sql;
    EXECUTE s;
    DEALLOCATE PREPARE s;
  END LOOP;
  CLOSE c;
END$$
DELIMITER ;
CALL tmp_grant_app_tables();
DROP PROCEDURE tmp_grant_app_tables;
FLUSH PRIVILEGES;
