"""[조별 특화 시나리오 A] 고객사 변경요청 및 승인 관리
접수(PM) → 검토안 작성(PM) → 내부 승인·반려(경영진) → 고객 동의 기록(PM) → 계획 반영(PM·경영진)
규칙 BR-16 ~ BR-23 은 DB 트리거·프로시저가 검증하고, 화면은 그 메시지를 그대로 보여 준다."""
import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from . import db
from .auth import executive_required, login_required

bp = Blueprint("changes", __name__)
CR_STATUS_KO = {"RECEIVED": "접수", "REVIEWING": "결정 대기", "APPROVED": "고객 동의 대기", "AGREED": "반영 대기",
                "APPLIED": "반영 완료", "REJECTED": "반려", "DECLINED": "고객 거절"}
DECISION_KO = {"PENDING": "결정 대기", "APPROVED": "승인", "REJECTED": "반려"}
CONSENT_KO = {"PENDING": "확인 전", "AGREED": "동의", "DECLINED": "거절"}


def _me():
    return session["user"]["emp_id"]


def _is_exec():
    return session["user"]["auth_role"] == "EXECUTIVE"


def _is_pm(project_id):
    return db.query("""SELECT 1 FROM assignment a JOIN job_role r ON r.role_id = a.role_id
                        WHERE a.project_id = %s AND a.emp_id = %s AND r.role_code = 'PM' LIMIT 1""",
                    (project_id, _me()), one=True) is not None


def _run(sql_calls, ok_msg, back):
    try:
        for sql, params in sql_calls:
            db.execute(sql, params)
        db.commit()
        flash(ok_msg, "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("처리 거부: " + db.error_message(e), "danger")
    return redirect(back)


@bp.post("/projects/<int:project_id>/changes")
@login_required
def create(project_id):
    f = request.form
    back = url_for("projects.detail", project_id=project_id) + "#changes"
    if not f.get("title") or not f.get("content"):
        flash("요청 제목과 내용을 입력해 주세요.", "warning")
        return redirect(back)
    return _run([("""INSERT INTO change_request (project_id, contact_id, received_by_emp_id, request_date, title, content, reason)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                  (project_id, f["contact_id"], _me(), f["request_date"], f["title"].strip(), f["content"].strip(),
                   f.get("reason") or None))],
                "변경요청이 접수되었습니다. 요청번호는 자동으로 부여됩니다.", back)


@bp.get("/changes/<int:cr_id>")
@login_required
def detail(cr_id):
    cr = db.query("SELECT * FROM v_change_request WHERE cr_id = %s", (cr_id,), one=True)
    if not cr:
        abort(404)
    is_pm = _is_pm(cr["project_id"])
    if not (_is_exec() or is_pm):
        abort(403)
    p = db.query("SELECT p.*, c.client_name FROM project p JOIN client c ON c.client_id = p.client_id WHERE p.project_id = %s",
                 (cr["project_id"],), one=True)
    reviews = db.query("""
        SELECT rv.*, rp.emp_name AS reviewer, ex.emp_name AS decider, cc.contact_name AS consent_by,
               rc.emp_name AS recorder, h.history_id, h.before_end_date, h.after_end_date, h.before_amount,
               h.after_amount, h.applied_at, ap.emp_name AS applied_by
          FROM change_review rv
          JOIN employee rp ON rp.emp_id = rv.reviewer_emp_id
          LEFT JOIN employee ex ON ex.emp_id = rv.decided_by_emp_id
          LEFT JOIN client_contact cc ON cc.contact_id = rv.consent_contact_id
          LEFT JOIN employee rc ON rc.emp_id = rv.consent_recorded_by
          LEFT JOIN change_history h ON h.review_id = rv.review_id
          LEFT JOIN employee ap ON ap.emp_id = h.applied_by_emp_id
         WHERE rv.cr_id = %s ORDER BY rv.version_no DESC""", (cr_id,))
    contacts = db.query("SELECT * FROM client_contact WHERE client_id = %s AND is_active = 1", (p["client_id"],))
    latest = reviews[0] if reviews else None
    max_assign_end = db.query("SELECT MAX(end_date) AS d FROM assignment WHERE project_id = %s", (p["project_id"],), one=True)["d"]
    return render_template("changes/detail.html", cr=cr, p=p, reviews=reviews, latest=latest, contacts=contacts,
                           is_pm=is_pm, max_assign_end=max_assign_end,
                           cr_status_ko=CR_STATUS_KO, decision_ko=DECISION_KO, consent_ko=CONSENT_KO)


@bp.post("/changes/<int:cr_id>/reviews")
@login_required
def add_review(cr_id):
    f = request.form
    nxt = db.query("SELECT IFNULL(MAX(version_no), 0) + 1 AS v FROM change_review WHERE cr_id = %s", (cr_id,), one=True)["v"]
    return _run([("""INSERT INTO change_review (cr_id, version_no, reviewer_emp_id, proposed_end_date, additional_amount, review_comment)
                     VALUES (%s, %s, %s, %s, %s, %s)""",
                  (cr_id, nxt, _me(), f["proposed_end_date"], f.get("additional_amount") or 0, f.get("review_comment") or None))],
                f"{nxt}차 검토안이 등록되었습니다. 경영진 결정을 기다립니다.", url_for("changes.detail", cr_id=cr_id))


@bp.post("/changes/<int:cr_id>/decision")
@executive_required
def decide(cr_id):
    f = request.form
    decision = "APPROVED" if f.get("decision") == "APPROVED" else "REJECTED"
    return _run([("""UPDATE change_review SET decision = %s, decided_by_emp_id = %s, decided_at = CURDATE(), decision_reason = %s
                      WHERE review_id = %s AND cr_id = %s""",
                  (decision, _me(), f.get("decision_reason") or None, f["review_id"], cr_id))],
                "검토안을 승인했습니다. 고객사 동의를 확인해 주세요." if decision == "APPROVED" else "검토안을 반려했습니다.",
                url_for("changes.detail", cr_id=cr_id))


@bp.post("/changes/<int:cr_id>/consent")
@login_required
def consent(cr_id):
    f = request.form
    agreed = f.get("consent") == "AGREED"
    return _run([("""UPDATE change_review SET consent = %s, consent_contact_id = %s, consent_date = %s,
                            consent_evidence = %s, consent_recorded_by = %s
                      WHERE review_id = %s AND cr_id = %s""",
                  ("AGREED" if agreed else "DECLINED", f["contact_id"], f["consent_date"], f.get("consent_evidence") or None,
                   _me(), f["review_id"], cr_id))],
                "고객 동의를 기록했습니다. 이제 계획에 반영할 수 있습니다." if agreed else "고객 거절을 기록했습니다.",
                url_for("changes.detail", cr_id=cr_id))


@bp.post("/changes/<int:cr_id>/apply")
@login_required
def apply(cr_id):
    return _run([("CALL sp_apply_change(%s, %s)", (request.form["review_id"], _me()))],
                "변경 내용을 프로젝트 계획에 반영하고 변경 전후 값을 이력으로 남겼습니다.",
                url_for("changes.detail", cr_id=cr_id))


@bp.get("/reports/changes")
@executive_required
def report():
    status = request.args.get("status", "")
    # [데모 시나리오 S7] 프로젝트별 변경요청 처리 현황 (미검토·미동의·미반영 요청 포함)
    rows = db.query(f"""SELECT * FROM v_change_request {"WHERE status = %s" if status else ""}
                        ORDER BY project_code, cr_no""", (status,) if status else None)
    counts = {r["status"]: r["cnt"] for r in db.query("SELECT status, COUNT(*) AS cnt FROM change_request GROUP BY status")}
    return render_template("reports/changes.html", rows=rows, status=status, counts=counts,
                           cr_status_ko=CR_STATUS_KO, decision_ko=DECISION_KO, consent_ko=CONSENT_KO)
