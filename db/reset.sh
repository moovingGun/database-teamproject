#!/usr/bin/env bash
# 실행 중인 컨테이너의 DB 를 초기 상태로 재적재 (컨테이너 재생성 없이)
#   ./db/reset.sh
set -euo pipefail
cd "$(dirname "$0")/.."
for f in db/init/00_privileges.sql db/init/01_schema.sql db/init/02_logic.sql db/init/03_seed.sql; do
  echo ">> $f"
  docker exec -i si_pms_db mysql -uroot -proot1234 --default-character-set=utf8mb4 < "$f"
done
echo "done."
