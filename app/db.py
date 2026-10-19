"""PyMySQL 기반 얇은 DB 접근 계층. 요청(request)당 커넥션 1개, 명시적 commit."""
import pymysql
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = pymysql.connect(
            **current_app.config["DB"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query(sql, params=None, one=False):
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchone() if one else cur.fetchall()


def execute(sql, params=None):
    """INSERT/UPDATE/DELETE 실행 후 lastrowid 반환 (commit 은 호출자가)."""
    with get_db().cursor() as cur:
        cur.execute(sql, params or ())
        return cur.lastrowid


def commit():
    get_db().commit()


def rollback():
    get_db().rollback()


def error_message(exc: Exception) -> str:
    """트리거 SIGNAL(45000) 메시지 등 MySQL 오류를 사용자 메시지로 변환."""
    if isinstance(exc, pymysql.MySQLError) and len(exc.args) >= 2:
        code, msg = exc.args[0], str(exc.args[1])
        if code == 1062:
            return "이미 존재하는 값입니다. (중복 키) " + msg
        if code == 3819:
            return "입력값이 허용 범위를 벗어났습니다. (CHECK 제약) " + msg
        if code == 1452:
            return "참조하는 데이터가 존재하지 않습니다. (외래키 제약)"
        return msg
    return str(exc)
