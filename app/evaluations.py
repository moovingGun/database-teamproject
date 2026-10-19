"""프로젝트 평가: 할 일 목록 · PM/동료 평가 입력 · 고객 평가 의뢰(PM) → 외부 입력 → 보고"""
import secrets

import pymysql
from flask import (Blueprint, abort, flash, redirect, render_template, request,
                   session, url_for)

from . import db
from .auth import login_required

bp = Blueprint("evaluations", __name__)
TYPE_KO = {"CUSTOMER": "고객 평가", "PM": "PM 평가", "PEER": "동료 평가"}
STATUS_KO = {"REQUESTED": "의뢰됨", "SUBMITTED": "제출", "REPORTED": "보고완료"}


def _me():
    return session["user"]["emp_id"]


def _items():
    return db.query("SELECT * FROM eval_item WHERE is_active = 1 ORDER BY item_id")


@bp.get("/evaluations")
@login_required
def tasks():
    me = _me()
    projects = db.query("""
        SELECT DISTINCT p.project_id, p.project_code, p.project_name, p.end_date, p.client_id,
               EXISTS (SELECT 1 FROM assignment a2 JOIN job_role r ON r.role_id = a2.role_id
                        WHERE a2.project_id = p.project_id AND a2.emp_id = %s AND r.role_code = 'PM') AS is_pm
          FROM project p JOIN assignment a ON a.project_id = p.project_id
         WHERE a.emp_id = %s AND p.status = 'COMPLETED'
         ORDER BY p.end_date DESC""", (me, me))
    for p in projects:
        pid = p["project_id"]
        p["peer_todo"] = db.query("""
            SELECT e.emp_id, e.emp_name, GROUP_CONCAT(DISTINCT r.role_name) AS roles
              FROM assignment a JOIN employee e ON e.emp_id = a.emp_id JOIN job_role r ON r.role_id = a.role_id
             WHERE a.project_id = %s AND a.emp_id <> %s
               AND NOT EXISTS (SELECT 1 FROM evaluation ev JOIN peer_eval pe ON pe.eval_id = ev.eval_id
                                WHERE ev.project_id = a.project_id AND ev.evaluatee_emp_id = a.emp_id
                                  AND pe.evaluator_emp_id = %s)
             GROUP BY e.emp_id, e.emp_name""", (pid, me, me))
        if p["is_pm"]:
            p["pm_todo"] = db.query("""
                SELECT e.emp_id, e.emp_name, GROUP_CONCAT(DISTINCT r.role_name) AS roles
                  FROM assignment a JOIN employee e ON e.emp_id = a.emp_id JOIN job_role r ON r.role_id = a.role_id
                 WHERE a.project_id = %s AND a.emp_id <> %s
                   AND NOT EXISTS (SELECT 1 FROM evaluation ev JOIN pm_eval pe ON pe.eval_id = ev.eval_id
                                    WHERE ev.project_id = a.project_id AND ev.evaluatee_emp_id = a.emp_id)
                 GROUP BY e.emp_id, e.emp_name""", (pid, me))
            p["customer"] = db.query("""SELECT ev.status, COUNT(*) AS cnt, MIN(ce.access_token) AS token
                                          FROM evaluation ev JOIN customer_eval ce ON ce.eval_id = ev.eval_id
                                         WHERE ev.project_id = %s GROUP BY ev.status""", (pid,))
            p["contacts"] = db.query("SELECT * FROM client_contact WHERE client_id = %s AND is_active = 1", (p["client_id"],))
    received = db.query("""SELECT s.*, p.project_code, p.project_name FROM v_project_eval_summary s
                            JOIN project p ON p.project_id = s.project_id
                           WHERE s.evaluatee_emp_id = %s ORDER BY p.end_date DESC""", (me,))
    return render_template("evaluations/tasks.html", projects=projects, received=received, status_ko=STATUS_KO)


@bp.route("/evaluations/new", methods=["GET", "POST"])
@login_required
def new():
    project_id = request.values.get("project_id", type=int)
    etype = request.values.get("eval_type")
    evaluatee_id = request.values.get("evaluatee_emp_id", type=int)
    if etype not in ("PM", "PEER") or not project_id or not evaluatee_id:
        abort(400)
    p = db.query("SELECT * FROM project WHERE project_id = %s", (project_id,), one=True)
    target = db.query("SELECT * FROM v_employee WHERE emp_id = %s", (evaluatee_id,), one=True)
    items = _items()
    if not p or not target:
        abort(404)
    if request.method == "POST":
        f = request.form
        try:
            # 슈퍼타입(evaluation) → 서브타입(pm_eval | peer_eval) → 상세(eval_detail) 를 한 트랜잭션으로
            eval_id = db.execute(
                """INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type, status, eval_date, overall_comment)
                   VALUES (%s, %s, %s, 'SUBMITTED', CURDATE(), %s)""",
                (project_id, evaluatee_id, etype, f.get("overall_comment") or None))
            if etype == "PM":
                db.execute("INSERT INTO pm_eval (eval_id, evaluator_emp_id, recommend_incentive) VALUES (%s, %s, %s)",
                           (eval_id, _me(), 1 if f.get("recommend_incentive") else 0))
            else:
                db.execute("INSERT INTO peer_eval (eval_id, evaluator_emp_id, is_anonymous) VALUES (%s, %s, %s)",
                           (eval_id, _me(), 1 if f.get("is_anonymous") else 0))
            for it in items:
                db.execute("INSERT INTO eval_detail (eval_id, item_id, score, comment) VALUES (%s, %s, %s, %s)",
                           (eval_id, it["item_id"], f[f"score_{it['item_id']}"], f.get(f"comment_{it['item_id']}") or None))
            db.commit()
            flash(f"{TYPE_KO[etype]}가 제출되었습니다. (대상: {target['emp_name']})", "success")
            return redirect(url_for("evaluations.tasks"))
        except (pymysql.MySQLError, KeyError) as e:
            db.rollback()
            msg = "모든 항목의 평점을 선택해 주세요." if isinstance(e, KeyError) else db.error_message(e)
            flash("제출 실패: " + msg, "danger")
    return render_template("evaluations/form.html", p=p, target=target, items=items, etype=etype, type_ko=TYPE_KO)


@bp.post("/projects/<int:project_id>/customer-eval/request")
@login_required
def request_customer(project_id):
    """PM 이 발주처 담당자에게 참여 직원 전원에 대한 고객 평가를 의뢰 (BR-08, BR-11, BR-12 는 트리거 검증)"""
    contact_id = request.form.get("contact_id", type=int)
    members = db.query("""SELECT DISTINCT a.emp_id FROM assignment a
                           WHERE a.project_id = %s
                             AND NOT EXISTS (SELECT 1 FROM evaluation ev WHERE ev.project_id = a.project_id
                                              AND ev.evaluatee_emp_id = a.emp_id AND ev.eval_type = 'CUSTOMER')""", (project_id,))
    if not members:
        flash("이미 모든 참여자에 대한 고객 평가가 의뢰되어 있습니다.", "warning")
        return redirect(url_for("evaluations.tasks"))
    token = None
    try:
        for m in members:
            eval_id = db.execute("INSERT INTO evaluation (project_id, evaluatee_emp_id, eval_type, status) VALUES (%s, %s, 'CUSTOMER', 'REQUESTED')",
                                 (project_id, m["emp_id"]))
            t = secrets.token_hex(16)
            token = token or t
            db.execute("INSERT INTO customer_eval (eval_id, contact_id, requested_by_emp_id, access_token) VALUES (%s, %s, %s, %s)",
                       (eval_id, contact_id, _me(), t))
        db.commit()
        link = url_for("evaluations.customer_form", token=token, _external=True)
        flash(f"{len(members)}명에 대한 고객 평가를 의뢰했습니다. 담당자 전달용 링크: {link}", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("의뢰 실패: " + db.error_message(e), "danger")
    return redirect(url_for("evaluations.tasks"))


@bp.route("/customer-eval/<token>", methods=["GET", "POST"])
def customer_form(token):
    """발주처 담당자용 외부 평가 화면 (로그인 불필요, 토큰으로 접근). 같은 담당자·프로젝트의 의뢰 건을 한 번에 입력"""
    anchor = db.query("""SELECT ev.project_id, ce.contact_id, p.project_code, p.project_name, p.start_date, p.end_date,
                                c.client_name, cc.contact_name, cc.position
                           FROM customer_eval ce JOIN evaluation ev ON ev.eval_id = ce.eval_id
                           JOIN project p ON p.project_id = ev.project_id JOIN client c ON c.client_id = p.client_id
                           JOIN client_contact cc ON cc.contact_id = ce.contact_id
                          WHERE ce.access_token = %s""", (token,), one=True)
    if not anchor:
        abort(404)
    pending = db.query("""SELECT ev.eval_id, e.emp_name,
                                 (SELECT GROUP_CONCAT(DISTINCT r.role_name) FROM assignment a JOIN job_role r ON r.role_id = a.role_id
                                   WHERE a.project_id = ev.project_id AND a.emp_id = ev.evaluatee_emp_id) AS roles
                            FROM evaluation ev JOIN customer_eval ce ON ce.eval_id = ev.eval_id
                            JOIN employee e ON e.emp_id = ev.evaluatee_emp_id
                           WHERE ev.project_id = %s AND ce.contact_id = %s AND ev.status = 'REQUESTED'
                           ORDER BY e.emp_name""", (anchor["project_id"], anchor["contact_id"]))
    items = _items()
    if request.method == "POST" and pending:
        f = request.form
        try:
            for ev in pending:
                for it in items:
                    db.execute("INSERT INTO eval_detail (eval_id, item_id, score, comment) VALUES (%s, %s, %s, %s)",
                               (ev["eval_id"], it["item_id"], f[f"score_{ev['eval_id']}_{it['item_id']}"],
                                f.get(f"comment_{ev['eval_id']}_{it['item_id']}") or None))
                db.execute("UPDATE evaluation SET status = 'SUBMITTED', eval_date = CURDATE(), overall_comment = %s WHERE eval_id = %s",
                           (f.get(f"overall_{ev['eval_id']}") or None, ev["eval_id"]))
            db.commit()
            return render_template("evaluations/customer_done.html", anchor=anchor, count=len(pending))
        except (pymysql.MySQLError, KeyError) as e:
            db.rollback()
            msg = "모든 항목의 평점을 선택해 주세요." if isinstance(e, KeyError) else db.error_message(e)
            flash("제출 실패: " + msg, "danger")
    return render_template("evaluations/customer_form.html", anchor=anchor, pending=pending, items=items)


@bp.post("/projects/<int:project_id>/customer-eval/report")
@login_required
def report_customer(project_id):
    """PM 이 제출된 고객 평가 결과를 회사에 보고 (SUBMITTED → REPORTED)"""
    try:
        n = db.execute("""UPDATE evaluation ev JOIN customer_eval ce ON ce.eval_id = ev.eval_id
                             SET ev.status = 'REPORTED', ce.reported_at = NOW()
                           WHERE ev.project_id = %s AND ev.status = 'SUBMITTED' AND ce.requested_by_emp_id = %s""",
                       (project_id, _me()))
        db.commit()
        flash("고객 평가 결과를 회사에 보고 처리했습니다.", "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("보고 실패: " + db.error_message(e), "danger")
    return redirect(url_for("evaluations.tasks"))
