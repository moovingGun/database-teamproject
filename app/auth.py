"""회원가입(사번 자동 채번, ID 중복 체크) / 로그인 / 권한 데코레이터"""
import re
from functools import wraps

import pymysql
from flask import (Blueprint, abort, flash, jsonify, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db

bp = Blueprint("auth", __name__, url_prefix="/auth")

EDUCATIONS = ["고졸", "전문학사", "학사", "석사", "박사"]
GRADES = ["초급", "중급", "고급", "특급"]
DEPARTMENTS = {"MARKETING": "마케팅", "MANAGEMENT": "경영관리", "RND": "연구개발"}
LOGIN_RE = re.compile(r"^[a-z0-9_]{4,20}$")
RRN_RE = re.compile(r"^\d{6}-\d{7}$")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not session.get("user"):
            flash("로그인이 필요합니다.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*a, **kw)
    return wrapped


def executive_required(view):
    """경영진(EXECUTIVE) 전용: 타 직원 정보 검색, 투입 관리, 리포트"""
    @wraps(view)
    def wrapped(*a, **kw):
        user = session.get("user")
        if not user:
            return redirect(url_for("auth.login", next=request.path))
        if user["auth_role"] != "EXECUTIVE":
            abort(403)
        return view(*a, **kw)
    return wrapped


def login_id_taken(login_id):
    return db.query("SELECT 1 FROM user_account WHERE login_id = %s", (login_id,), one=True) is not None


@bp.get("/check-id")
def check_id():
    """회원가입 화면의 [중복확인] 버튼 → JSON"""
    login_id = (request.args.get("login_id") or "").strip().lower()
    if not LOGIN_RE.match(login_id):
        return jsonify(available=False, message="아이디는 영문 소문자/숫자/_ 4~20자여야 합니다.")
    if login_id_taken(login_id):
        return jsonify(available=False, message=f"'{login_id}' 는 이미 등록된 아이디입니다. 다른 아이디를 입력해 주세요.")
    return jsonify(available=True, message=f"'{login_id}' 는 사용 가능한 아이디입니다.")


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    form = request.form if request.method == "POST" else {}
    errors = {}
    if request.method == "POST":
        login_id = (form.get("login_id") or "").strip().lower()
        pw, pw2 = form.get("password") or "", form.get("password2") or ""
        emp_type = form.get("emp_type")

        if not LOGIN_RE.match(login_id):
            errors["login_id"] = "아이디는 영문 소문자/숫자/_ 4~20자여야 합니다."
        elif login_id_taken(login_id):
            errors["login_id"] = f"'{login_id}' 는 이미 등록된 아이디입니다. 중복되지 않는 새 아이디를 입력해 주세요."
        if len(pw) < 8:
            errors["password"] = "비밀번호는 8자 이상이어야 합니다."
        elif pw != pw2:
            errors["password2"] = "비밀번호 확인이 일치하지 않습니다."
        if not (form.get("emp_name") or "").strip():
            errors["emp_name"] = "이름을 입력해 주세요."
        rrn = (form.get("resident_reg_no") or "").strip()
        if not RRN_RE.match(rrn):
            errors["resident_reg_no"] = "주민등록번호 형식은 000000-0000000 입니다."
        elif db.query("SELECT 1 FROM employee WHERE resident_reg_no = %s", (rrn,), one=True):
            errors["resident_reg_no"] = "이미 등록된 주민등록번호입니다."
        if form.get("education_level") not in EDUCATIONS:
            errors["education_level"] = "최종학력을 선택해 주세요."
        if not form.get("hire_date"):
            errors["hire_date"] = "입사일을 입력해 주세요."
        if emp_type == "DEV":
            if form.get("skill_grade") not in GRADES:
                errors["skill_grade"] = "기술등급을 선택해 주세요."
            if not form.get("career_start_date"):
                errors["career_start_date"] = "경력 기산일을 입력해 주세요."
        elif emp_type == "STAFF":
            if form.get("department") not in DEPARTMENTS:
                errors["department"] = "부서를 선택해 주세요."
        else:
            errors["emp_type"] = "직원 구분을 선택해 주세요."

        if not errors:
            try:
                # 슈퍼타입 → 서브타입 → 계정 순으로 한 트랜잭션에 등록. 사번은 트리거가 채번.
                db.execute(
                    """INSERT INTO employee (emp_name, resident_reg_no, education_level, hire_date, emp_type, email, phone)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (form["emp_name"].strip(), rrn, form["education_level"], form["hire_date"], emp_type,
                     form.get("email") or None, form.get("phone") or None))
                emp = db.query("SELECT emp_id, emp_no FROM employee WHERE resident_reg_no = %s", (rrn,), one=True)
                if emp_type == "DEV":
                    db.execute("INSERT INTO developer (emp_id, skill_grade, career_start_date) VALUES (%s, %s, %s)",
                               (emp["emp_id"], form["skill_grade"], form["career_start_date"]))
                else:
                    db.execute("INSERT INTO staff (emp_id, department, job_title) VALUES (%s, %s, %s)",
                               (emp["emp_id"], form["department"], form.get("job_title") or None))
                db.execute("INSERT INTO user_account (emp_id, login_id, password_hash) VALUES (%s, %s, %s)",
                           (emp["emp_id"], login_id, generate_password_hash(pw, method="pbkdf2:sha256")))
                db.commit()
                flash(f"회원가입이 완료되었습니다. 부여된 사번: {emp['emp_no']}  — 로그인해 주세요.", "success")
                return redirect(url_for("auth.login"))
            except pymysql.MySQLError as e:
                db.rollback()
                if e.args and e.args[0] == 1062 and "uk_account_login" in str(e):
                    errors["login_id"] = "이미 등록된 아이디입니다. 다른 아이디를 입력해 주세요."
                else:
                    flash("가입 처리 중 오류: " + db.error_message(e), "danger")
    return render_template("auth/signup.html", form=form, errors=errors,
                           educations=EDUCATIONS, grades=GRADES, departments=DEPARTMENTS)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = (request.form.get("login_id") or "").strip().lower()
        row = db.query(
            """SELECT a.emp_id, a.login_id, a.password_hash, a.auth_role, a.is_active,
                      e.emp_name, e.emp_no, e.emp_type
                 FROM user_account a JOIN employee e ON e.emp_id = a.emp_id
                WHERE a.login_id = %s""", (login_id,), one=True)
        if row and row["is_active"] and check_password_hash(row["password_hash"], request.form.get("password") or ""):
            session.clear()
            session["user"] = {k: row[k] for k in ("emp_id", "login_id", "auth_role", "emp_name", "emp_no", "emp_type")}
            db.execute("UPDATE user_account SET last_login_at = NOW() WHERE emp_id = %s", (row["emp_id"],))
            db.commit()
            return redirect(request.args.get("next") or url_for("reports.index"))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "danger")
    return render_template("auth/login.html")


@bp.get("/logout")
def logout():
    session.clear()
    flash("로그아웃되었습니다.", "info")
    return redirect(url_for("auth.login"))
