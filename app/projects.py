"""프로젝트 목록/상세 · 등록 · 투입 관리(트리거 검증) · 종료 처리"""
from datetime import date

import pymysql
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from . import db
from .auth import executive_required, login_required

bp = Blueprint("projects", __name__, url_prefix="/projects")
STATUS_KO = {"PLANNED": "예정", "IN_PROGRESS": "진행중", "COMPLETED": "종료", "CANCELLED": "취소"}


@bp.get("")
@login_required
def index():
    status = request.args.get("status", "")
    rows = db.query(f"""
        SELECT p.*, c.client_name,
               (SELECT e.emp_name FROM assignment a JOIN job_role r ON r.role_id = a.role_id
                  JOIN employee e ON e.emp_id = a.emp_id
                 WHERE a.project_id = p.project_id AND r.role_code = 'PM' ORDER BY a.start_date DESC LIMIT 1) AS pm_name,
               (SELECT COUNT(*) FROM assignment a WHERE a.project_id = p.project_id
                   AND CURDATE() BETWEEN a.start_date AND a.end_date) AS current_headcount,
               (SELECT COUNT(DISTINCT a.emp_id) FROM assignment a WHERE a.project_id = p.project_id) AS total_headcount
          FROM project p JOIN client c ON c.client_id = p.client_id
         {"WHERE p.status = %s" if status else ""}
         ORDER BY FIELD(p.status,'IN_PROGRESS','PLANNED','COMPLETED','CANCELLED'), p.start_date DESC""",
        (status,) if status else None)
    return render_template("projects/list.html", rows=rows, status=status, status_ko=STATUS_KO)


@bp.get("/<int:project_id>")
@login_required
def detail(project_id):
    p = db.query("SELECT p.*, c.client_name, c.industry FROM project p JOIN client c ON c.client_id = p.client_id WHERE p.project_id = %s",
                 (project_id,), one=True)
    if not p:
        abort(404)
    me = session["user"]["emp_id"]
    assignments = db.query("SELECT * FROM v_assignment_detail WHERE project_id = %s ORDER BY role_id, start_date", (project_id,))
    req_skills = db.query("""SELECT ps.required_level, s.skill_name, s.category FROM project_skill ps JOIN skill s ON s.skill_id = ps.skill_id
                             WHERE ps.project_id = %s ORDER BY s.category, s.skill_name""", (project_id,))
    contacts = db.query("SELECT * FROM client_contact WHERE client_id = %s AND is_active = 1", (p["client_id"],))
    eval_progress = db.query("""SELECT eval_type, status, COUNT(*) AS cnt FROM evaluation
                                WHERE project_id = %s GROUP BY eval_type, status""", (project_id,))
    customer_evals = db.query("""SELECT ev.eval_id, ev.status, ev.eval_date, e.emp_name AS evaluatee_name,
                                        ce.access_token, ce.reported_at, cc.contact_name
                                   FROM evaluation ev JOIN customer_eval ce ON ce.eval_id = ev.eval_id
                                   JOIN employee e ON e.emp_id = ev.evaluatee_emp_id
                                   JOIN client_contact cc ON cc.contact_id = ce.contact_id
                                  WHERE ev.project_id = %s ORDER BY ev.eval_id""", (project_id,))
    is_pm = any(a["emp_id"] == me and a["role_code"] == "PM" for a in assignments)
    is_member = any(a["emp_id"] == me for a in assignments)
    developers = roles = []
    if session["user"]["auth_role"] == "EXECUTIVE":
        developers = db.query("""SELECT emp_id, emp_no, emp_name, skill_grade FROM v_employee
                                 WHERE emp_type = 'DEV' AND status = 'ACTIVE' ORDER BY skill_grade DESC, emp_name""")
        roles = db.query("SELECT * FROM job_role ORDER BY sort_order")
    return render_template("projects/detail.html", p=p, assignments=assignments, req_skills=req_skills,
                           contacts=contacts, eval_progress=eval_progress, customer_evals=customer_evals,
                           is_pm=is_pm, is_member=is_member, developers=developers, roles=roles, status_ko=STATUS_KO)


@bp.route("/new", methods=["GET", "POST"])
@executive_required
def new():
    clients = db.query("SELECT * FROM client ORDER BY client_name")
    skills = db.query("SELECT * FROM skill ORDER BY category, skill_name")
    if request.method == "POST":
        f = request.form
        try:
            # 프로젝트번호(project_code)는 BEFORE INSERT 트리거가 P+연도-일련번호 로 채번
            db.execute("""INSERT INTO project (project_name, client_id, start_date, end_date, status, contract_amount, description)
                          VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                       (f["project_name"].strip(), f["client_id"], f["start_date"], f["end_date"], f["status"],
                        f.get("contract_amount") or None, f.get("description") or None))
            pid = db.query("SELECT LAST_INSERT_ID() AS id", one=True)["id"]
            for sid in f.getlist("skill_id"):
                db.execute("INSERT INTO project_skill (project_id, skill_id, required_level) VALUES (%s, %s, 3)", (pid, sid))
            db.commit()
            code = db.query("SELECT project_code FROM project WHERE project_id = %s", (pid,), one=True)["project_code"]
            flash(f"프로젝트가 등록되었습니다. 프로젝트번호: {code}", "success")
            return redirect(url_for("projects.detail", project_id=pid))
        except pymysql.MySQLError as e:
            db.rollback()
            flash("등록 실패: " + db.error_message(e), "danger")
    return render_template("projects/new.html", clients=clients, skills=skills, form=request.form)


@bp.post("/<int:project_id>/assignments")
@executive_required
def add_assignment(project_id):
    p = db.query("SELECT * FROM project WHERE project_id = %s", (project_id,), one=True)
    f = request.form
    if p["status"] in ("COMPLETED", "CANCELLED"):
        flash("종료/취소된 프로젝트에는 투입할 수 없습니다.", "danger")
        return redirect(url_for("projects.detail", project_id=project_id))
    try:
        # 투입 규칙(BR-01~07)은 DB 트리거가 검증 → 위반 시 SIGNAL 메시지를 그대로 표시
        db.execute("""INSERT INTO assignment (project_id, emp_id, role_id, start_date, end_date, participation_rate, note)
                      VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                   (project_id, f["emp_id"], f["role_id"], f["start_date"] or p["start_date"],
                    f["end_date"] or p["end_date"], f.get("participation_rate") or 100, f.get("note") or None))
        db.commit()
        flash("투입이 등록되었습니다.", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("투입 등록 거부: " + db.error_message(e), "danger")
    return redirect(url_for("projects.detail", project_id=project_id))


@bp.post("/<int:project_id>/assignments/<int:assignment_id>/end")
@executive_required
def end_assignment(project_id, assignment_id):
    """조기 철수: 투입 종료일을 앞당김 (이력은 보존)"""
    try:
        db.execute("UPDATE assignment SET end_date = %s WHERE assignment_id = %s AND project_id = %s",
                   (request.form["end_date"], assignment_id, project_id))
        db.commit()
        flash("투입 종료일이 변경되었습니다.", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("변경 실패: " + db.error_message(e), "danger")
    return redirect(url_for("projects.detail", project_id=project_id))


@bp.post("/<int:project_id>/status")
@executive_required
def change_status(project_id):
    """착수(PLANNED→IN_PROGRESS) / 종료(→COMPLETED: 실제 종료일 반영, 열린 투입 정리) / 취소"""
    action = request.form["action"]
    try:
        if action == "start":
            db.execute("UPDATE project SET status='IN_PROGRESS' WHERE project_id=%s AND status='PLANNED'", (project_id,))
        elif action == "complete":
            actual = request.form.get("actual_end_date") or date.today().isoformat()
            db.execute("UPDATE project SET status='COMPLETED', end_date=%s WHERE project_id=%s AND status='IN_PROGRESS'",
                       (actual, project_id))
            db.execute("DELETE FROM assignment WHERE project_id=%s AND start_date > %s", (project_id, actual))
            db.execute("UPDATE assignment SET end_date=%s WHERE project_id=%s AND end_date > %s", (actual, project_id, actual))
        elif action == "cancel":
            db.execute("UPDATE project SET status='CANCELLED' WHERE project_id=%s AND status IN ('PLANNED','IN_PROGRESS')", (project_id,))
        db.commit()
        flash("프로젝트 상태가 변경되었습니다.", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("상태 변경 실패: " + db.error_message(e), "danger")
    return redirect(url_for("projects.detail", project_id=project_id))
