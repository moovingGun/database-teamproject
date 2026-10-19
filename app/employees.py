"""내 정보(조회/수정/보유기술) · 직원 검색(경영진) · 직원 상세(경력/평가 이력)"""
import pymysql
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from . import db
from .auth import DEPARTMENTS, EDUCATIONS, GRADES, executive_required, login_required

bp = Blueprint("employees", __name__)


def _me():
    return session["user"]["emp_id"]


def _is_exec():
    return session["user"]["auth_role"] == "EXECUTIVE"


# ----------------------------------------------------------------- 내 정보
@bp.get("/me")
@login_required
def me():
    return redirect(url_for("employees.detail", emp_id=_me()))


@bp.route("/me/edit", methods=["GET", "POST"])
@login_required
def edit_me():
    emp = db.query("SELECT * FROM v_employee WHERE emp_id = %s", (_me(),), one=True)
    if request.method == "POST":
        f = request.form
        try:
            db.execute("""UPDATE employee SET emp_name=%s, education_level=%s, email=%s, phone=%s WHERE emp_id=%s""",
                       (f["emp_name"].strip(), f["education_level"], f.get("email") or None, f.get("phone") or None, _me()))
            if emp["emp_type"] == "DEV":
                # 기술등급은 본인이 바꿀 수 없음(경영진 심사) → 경력 기산일만 수정
                db.execute("UPDATE developer SET career_start_date=%s WHERE emp_id=%s", (f["career_start_date"], _me()))
            else:
                db.execute("UPDATE staff SET department=%s, job_title=%s WHERE emp_id=%s",
                           (f["department"], f.get("job_title") or None, _me()))
            if f.get("new_password"):
                from werkzeug.security import generate_password_hash
                if len(f["new_password"]) < 8:
                    raise ValueError("비밀번호는 8자 이상이어야 합니다.")
                db.execute("UPDATE user_account SET password_hash=%s WHERE emp_id=%s",
                           (generate_password_hash(f["new_password"], method="pbkdf2:sha256"), _me()))
            db.commit()
            session["user"]["emp_name"] = f["emp_name"].strip()
            session.modified = True
            flash("내 정보가 수정되었습니다.", "success")
            return redirect(url_for("employees.me"))
        except (pymysql.MySQLError, ValueError) as e:
            db.rollback()
            flash("수정 실패: " + db.error_message(e), "danger")
    return render_template("employees/edit.html", emp=emp, educations=EDUCATIONS, departments=DEPARTMENTS)


@bp.route("/me/skills", methods=["GET", "POST"])
@login_required
def my_skills():
    if session["user"]["emp_type"] != "DEV":
        flash("보유 기술은 개발자만 등록할 수 있습니다.", "warning")
        return redirect(url_for("employees.me"))
    if request.method == "POST":
        f = request.form
        try:
            if f.get("action") == "delete":
                db.execute("DELETE FROM employee_skill WHERE emp_id=%s AND skill_id=%s", (_me(), f["skill_id"]))
            else:
                db.execute("""INSERT INTO employee_skill (emp_id, skill_id, proficiency, years_used, last_used_date)
                              VALUES (%s, %s, %s, %s, %s)
                              ON DUPLICATE KEY UPDATE proficiency=VALUES(proficiency), years_used=VALUES(years_used),
                                                      last_used_date=VALUES(last_used_date)""",
                           (_me(), f["skill_id"], f["proficiency"], f.get("years_used") or 0, f.get("last_used_date") or None))
            db.commit()
            flash("보유 기술이 저장되었습니다.", "success")
        except pymysql.MySQLError as e:
            db.rollback()
            flash("저장 실패: " + db.error_message(e), "danger")
        return redirect(url_for("employees.my_skills"))
    mine = db.query("""SELECT es.*, s.skill_name, s.category FROM employee_skill es JOIN skill s ON s.skill_id = es.skill_id
                       WHERE es.emp_id = %s ORDER BY s.category, s.skill_name""", (_me(),))
    skills = db.query("SELECT * FROM skill ORDER BY category, skill_name")
    return render_template("employees/skills.html", mine=mine, skills=skills)


# ----------------------------------------------------------------- 직원 검색 (경영진)
@bp.get("/employees")
@executive_required
def search():
    a = request.args
    where, params = ["1=1"], []
    if a.get("q"):
        where.append("(e.emp_name LIKE %s OR e.emp_no LIKE %s)"); params += [f"%{a['q']}%", f"%{a['q']}%"]
    if a.get("emp_type"):
        where.append("e.emp_type = %s"); params.append(a["emp_type"])
    if a.get("grade"):
        where.append("e.skill_grade = %s"); params.append(a["grade"])
    if a.get("skill_id"):
        where.append("EXISTS (SELECT 1 FROM employee_skill es WHERE es.emp_id = e.emp_id AND es.skill_id = %s)")
        params.append(a["skill_id"])
    if a.get("available_on"):
        # 해당 일자에 투입률 합계 100% 미만인 개발자 (가용 인력)
        where.append("""e.emp_type = 'DEV' AND IFNULL((SELECT SUM(participation_rate) FROM assignment x
                         WHERE x.emp_id = e.emp_id AND x.start_date <= %s AND x.end_date >= %s), 0) < 100""")
        params += [a["available_on"], a["available_on"]]
    rows = db.query(f"""
        SELECT e.*, 
               (SELECT GROUP_CONCAT(DISTINCT p.project_name ORDER BY p.project_name SEPARATOR ', ')
                  FROM assignment x JOIN project p ON p.project_id = x.project_id
                 WHERE x.emp_id = e.emp_id AND CURDATE() BETWEEN x.start_date AND x.end_date) AS current_projects,
               (SELECT IFNULL(SUM(participation_rate),0) FROM assignment x
                 WHERE x.emp_id = e.emp_id AND CURDATE() BETWEEN x.start_date AND x.end_date) AS current_rate
          FROM v_employee e
         WHERE {' AND '.join(where)}
         ORDER BY e.emp_type, e.skill_grade DESC, e.emp_no""", params)
    skills = db.query("SELECT * FROM skill ORDER BY category, skill_name")
    return render_template("employees/list.html", rows=rows, skills=skills, grades=GRADES, args=a)


# ----------------------------------------------------------------- 직원 상세 (본인 또는 경영진)
@bp.get("/employees/<int:emp_id>")
@login_required
def detail(emp_id):
    if emp_id != _me() and not _is_exec():
        abort(403)
    emp = db.query("SELECT * FROM v_employee WHERE emp_id = %s", (emp_id,), one=True)
    if not emp:
        abort(404)
    skills = db.query("""SELECT es.*, s.skill_name, s.category FROM employee_skill es JOIN skill s ON s.skill_id = es.skill_id
                         WHERE es.emp_id = %s ORDER BY es.proficiency DESC, s.skill_name""", (emp_id,))
    # [데모 시나리오 3] 개인별 경력(프로젝트 참여 이력)
    career = db.query("""SELECT * FROM v_assignment_detail WHERE emp_id = %s ORDER BY start_date DESC""", (emp_id,))
    evals = db.query("""SELECT s.*, p.project_code, p.project_name, p.end_date
                          FROM v_project_eval_summary s JOIN project p ON p.project_id = s.project_id
                         WHERE s.evaluatee_emp_id = %s ORDER BY p.end_date DESC""", (emp_id,))
    history = db.query("""SELECT h.*, e.emp_name AS changed_by_name FROM grade_history h
                          LEFT JOIN employee e ON e.emp_id = h.changed_by_emp_id
                         WHERE h.emp_id = %s ORDER BY h.changed_at DESC""", (emp_id,))
    return render_template("employees/detail.html", emp=emp, skills=skills, career=career, evals=evals,
                           history=history, grades=GRADES, is_self=(emp_id == _me()))


@bp.post("/employees/<int:emp_id>/grade")
@executive_required
def change_grade(emp_id):
    """기술등급 변경 → BR-15 트리거가 grade_history 자동 기록"""
    try:
        db.execute("SET @app_user_id = %s, @grade_change_reason = %s", (_me(), request.form.get("reason") or "경영진 등급 조정"))
        db.execute("UPDATE developer SET skill_grade = %s WHERE emp_id = %s", (request.form["skill_grade"], emp_id))
        db.commit()
        flash("기술등급이 변경되었고 이력이 기록되었습니다.", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("변경 실패: " + db.error_message(e), "danger")
    return redirect(url_for("employees.detail", emp_id=emp_id))
