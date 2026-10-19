SET NAMES utf8mb4;
-- 애플리케이션 계정(pms)에 성능 실험용 DB(si_pms_perf) 권한 부여
GRANT ALL PRIVILEGES ON si_pms_perf.* TO 'pms'@'%';
FLUSH PRIVILEGES;
