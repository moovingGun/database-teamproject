"""[조별 특화 시나리오 B] 프로젝트 평가 기반 역량 개선 및 교육 이수 관리
교육 담당자: 평가·보유 기술 검토 → 역량개선계획 수립 → 교육 종료 후 수료 기록
직원: 내 계획 확인 → 추천 과정의 일정에 신청·취소
경영진·교육 담당자: 계획별 미신청·신청·수료 현황, 교육과정별 수요 조회
규칙 BR-24 ~ BR-29 는 DB 트리거가 검증한다. 수료해도 기술등급은 바뀌지 않는다(별도 절차)."""
import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from . import db
from .auth import login_required, trainer_required

bp = Blueprint("training", __name__)
PLAN_STATUS_KO = {"NOT_APPLIED": "미신청", "APPLIED": "신청", "NOT_COMPLETED": "미수료", "COMPLETED": "수료"}
ENROLL_KO = {"APPLIED": "신청", "CANCELLED": "취소", "COMPLETED": "수료", "NOT_COMPLETED": "미수료"}
FIELD_KO = {"TECH": "기술", "COMM": "의사소통", "MGMT": "관리", "QUALITY": "품질"}

SESSIONS_SQL = """
SELECT ts.*, tc.course_name, tc.field,
       (SELECT COUNT(*) FROM training_enrollment x WHERE x.session_id = ts.session_id AND x.status <> 'CANCELLED') AS enrolled
  FROM training_session ts JOIN training_course tc ON tc.course_id = ts.course_id"""


def _me():
    return session["user"]["emp_id"]


def _can_view_reports():
    u = session["user"]
    return u["auth_role"] == "EXECUTIVE" or u.get("is_trainer")


def _run(sql, params, ok_msg, back):
    try:
        db.execute(sql, params)
        db.commit()
        flash(ok_msg, "success")
    except pymysql.MySQLError as e:
        db.rollback()
        flash("처리 거부: " + db.error_message(e), "danger")
    return redirect(back)


@bp.get("/training")
@trainer_required
def manage():
    # 종료 프로젝트 참여자 중 평가 종합점수가 낮은 순 (계획이 이미 있는 건 제외) — 판단은 담당자가 한다
    candidates = db.query("""
        SELECT s.project_id, p.project_code, p.project_name, s.evaluatee_emp_id AS emp_id, e.emp_name, d.skill_grade,
               s.weighted_score, s.customer_score, s.pm_score, s.peer_score,
               (SELECT ROUND(AVG(v.comm_score), 2) FROM v_eval_score v WHERE v.project_id = s.project_id AND v.evaluatee_emp_id = s.evaluatee_emp_id) AS comm_avg,
               (SELECT ROUND(AVG(v.work_score), 2) FROM v_eval_score v WHERE v.project_id = s.project_id AND v.evaluatee_emp_id = s.evaluatee_emp_id) AS work_avg
          FROM v_project_eval_summary s
          JOIN project p ON p.project_id = s.project_id AND p.status = 'COMPLETED'
          JOIN employee e ON e.emp_id = s.evaluatee_emp_id
          JOIN developer d ON d.emp_id = s.evaluatee_emp_id
         WHERE NOT EXISTS (SELECT 1 FROM development_plan dp WHERE dp.emp_id = s.evaluatee_emp_id AND dp.project_id = s.project_id)
         ORDER BY s.weighted_score LIMIT 12""")
    plans = db.query("SELECT * FROM v_training_plan ORDER BY created_date DESC, plan_id DESC")
    pending = db.query("""
        SELECT te.enroll_id, e.emp_name, tc.course_name, ts.start_at, ts.end_at, ts.place
          FROM training_enrollment te JOIN development_plan dp ON dp.plan_id = te.plan_id
          JOIN employee e ON e.emp_id = dp.emp_id
          JOIN training_session ts ON ts.session_id = te.session_id
          JOIN training_course tc ON tc.course_id = ts.course_id
         WHERE te.status = 'APPLIED' AND ts.end_at <= NOW() ORDER BY ts.end_at""")
    sessions = db.query(SESSIONS_SQL + " WHERE ts.end_at > NOW() ORDER BY ts.start_at")
    return render_template("training/manage.html", candidates=candidates, plans=plans, pending=pending, sessions=sessions,
                           plan_ko=PLAN_STATUS_KO, field_ko=FIELD_KO)


@bp.route("/training/plans/new", methods=["GET", "POST"])
@trainer_required
def new_plan():
    emp_id = request.values.get("emp_id", type=int)
    project_id = request.values.get("project_id", type=int)
    if request.method == "POST":
        f = request.form
        try:
            db.execute("""INSERT INTO development_plan (emp_id, project_id, course_id, manager_emp_id, improvement_goal, reason,
                                                        created_date, due_date)
                          VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s)""",
                       (emp_id, project_id, f["course_id"], _me(), f["improvement_goal"].strip(), f["reason"].strip(), f["due_date"]))
            db.commit()
            flash("역량개선계획을 등록했습니다. 직원 화면에 추천 교육으로 표시됩니다.", "success")
            return redirect(url_for("training.manage"))
        except (pymysql.MySQLError, KeyError) as e:
            db.rollback()
            flash("등록 거부: " + (db.error_message(e) if isinstance(e, pymysql.MySQLError) else "필수 항목을 입력하세요."), "danger")
    emp = db.query("SELECT * FROM v_employee WHERE emp_id = %s", (emp_id,), one=True)
    p = db.query("SELECT * FROM project WHERE project_id = %s", (project_id,), one=True)
    if not emp or not p:
        abort(404)
    summary = db.query("SELECT * FROM v_project_eval_summary WHERE project_id = %s AND evaluatee_emp_id = %s",
                       (project_id, emp_id), one=True)
    comments = db.query("""
        SELECT ev.eval_type, it.item_name, dt.score, dt.comment
          FROM evaluation ev JOIN eval_detail dt ON dt.eval_id = ev.eval_id JOIN eval_item it ON it.item_id = dt.item_id
         WHERE ev.project_id = %s AND ev.evaluatee_emp_id = %s ORDER BY dt.score, FIELD(ev.eval_type, 'CUSTOMER', 'PM', 'PEER')""",
                        (project_id, emp_id))
    skills = db.query("""SELECT s.skill_name, es.proficiency FROM employee_skill es JOIN skill s ON s.skill_id = es.skill_id
                         WHERE es.emp_id = %s ORDER BY es.proficiency DESC""", (emp_id,))
    courses = db.query("""SELECT tc.*, s.skill_name FROM training_course tc LEFT JOIN skill s ON s.skill_id = tc.skill_id
                          ORDER BY tc.field, tc.course_name""")
    return render_template("training/plan_new.html", emp=emp, p=p, summary=summary, comments=comments, skills=skills,
                           courses=courses, field_ko=FIELD_KO)


@bp.post("/training/enrollments/<int:enroll_id>/result")
@trainer_required
def record_result(enroll_id):
    done = request.form.get("result") == "COMPLETED"
    return _run("UPDATE training_enrollment SET status = %s, attended = %s WHERE enroll_id = %s",
                ("COMPLETED" if done else "NOT_COMPLETED", 1 if done else int(request.form.get("attended", 0)), enroll_id),
                "수료로 기록했습니다. 기술등급은 자동으로 바뀌지 않습니다." if done else "미수료로 기록했습니다. 재수강은 다른 일정에 새로 신청합니다.",
                url_for("training.manage"))


@bp.get("/me/training")
@login_required
def my_training():
    plans = db.query("SELECT * FROM v_training_plan WHERE emp_id = %s ORDER BY created_date DESC", (_me(),))
    for pl in plans:
        pl["sessions"] = db.query(SESSIONS_SQL + """ WHERE ts.course_id = %s AND ts.start_at > NOW()
                                    AND NOT EXISTS (SELECT 1 FROM training_enrollment y WHERE y.plan_id = %s
                                                     AND y.session_id = ts.session_id AND y.status <> 'CANCELLED')
                                  ORDER BY ts.start_at""", (pl["course_id"], pl["plan_id"]))
        pl["history"] = db.query("""SELECT te.*, ts.start_at, ts.end_at, ts.place FROM training_enrollment te
                                    JOIN training_session ts ON ts.session_id = te.session_id
                                    WHERE te.plan_id = %s ORDER BY te.applied_at DESC""", (pl["plan_id"],))
    return render_template("training/mine.html", plans=plans, plan_ko=PLAN_STATUS_KO, enroll_ko=ENROLL_KO, field_ko=FIELD_KO)


@bp.post("/me/training/apply")
@login_required
def apply():
    plan_id = request.form.get("plan_id", type=int)
    if not db.query("SELECT 1 FROM development_plan WHERE plan_id = %s AND emp_id = %s", (plan_id, _me()), one=True):
        abort(403)            # 신청자는 계획 대상자 본인
    return _run("INSERT INTO training_enrollment (plan_id, session_id) VALUES (%s, %s)",
                (plan_id, request.form.get("session_id", type=int)), "교육을 신청했습니다.", url_for("training.my_training"))


@bp.post("/me/training/<int:enroll_id>/cancel")
@login_required
def cancel(enroll_id):
    if not db.query("""SELECT 1 FROM training_enrollment te JOIN development_plan dp ON dp.plan_id = te.plan_id
                       WHERE te.enroll_id = %s AND dp.emp_id = %s""", (enroll_id, _me()), one=True):
        abort(403)
    return _run("UPDATE training_enrollment SET status = 'CANCELLED' WHERE enroll_id = %s", (enroll_id,),
                "신청을 취소했습니다. 취소 이력은 남습니다.", url_for("training.my_training"))


@bp.get("/reports/training")
@login_required
def report():
    if not _can_view_reports():
        abort(403)
    status = request.args.get("status", "")
    # [데모 시나리오 S8] 직원별 평가 결과 + 역량개선계획 + 신청·수료 현황 (미신청 계획 포함)
    rows = db.query(f"SELECT * FROM v_training_plan {'WHERE plan_status = %s' if status else ''} ORDER BY emp_name",
                    (status,) if status else None)
    demand = db.query("""
        SELECT tc.course_name, tc.field, COUNT(DISTINCT dp.plan_id) AS plans,
               SUM(vp.plan_status = 'NOT_APPLIED') AS not_applied, SUM(vp.plan_status = 'APPLIED') AS applied,
               SUM(vp.plan_status = 'COMPLETED') AS completed,
               (SELECT COUNT(*) FROM training_session ts WHERE ts.course_id = tc.course_id AND ts.start_at > NOW()) AS upcoming_sessions
          FROM training_course tc
          LEFT JOIN development_plan dp ON dp.course_id = tc.course_id
          LEFT JOIN v_training_plan vp ON vp.plan_id = dp.plan_id
         GROUP BY tc.course_id, tc.course_name, tc.field ORDER BY plans DESC, tc.course_name""")
    counts = {r["plan_status"]: r["cnt"] for r in db.query("SELECT plan_status, COUNT(*) AS cnt FROM v_training_plan GROUP BY plan_status")}
    return render_template("reports/training.html", rows=rows, demand=demand, counts=counts, status=status,
                           plan_ko=PLAN_STATUS_KO, enroll_ko=ENROLL_KO, field_ko=FIELD_KO)
