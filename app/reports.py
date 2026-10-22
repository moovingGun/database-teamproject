"""대시보드 및 경영진 리포트 (데모 시나리오 1·2·4·5 의 SQL 과 동일)"""
from datetime import date

from flask import Blueprint, render_template, request, session

from . import db
from .auth import executive_required, login_required

bp = Blueprint("reports", __name__)

# [데모 시나리오 2 - 대표 시나리오 / 성능 실험 대상] 특정 시점의 프로젝트별 투입 인력·직무
SQL_STAFFING_AT = """
SELECT p.project_id, p.project_code, p.project_name, p.status AS project_status, c.client_name,
       e.emp_id, e.emp_no, e.emp_name, d.skill_grade, r.role_name, r.sort_order,
       a.start_date, a.end_date, a.participation_rate
  FROM assignment a
  JOIN project   p ON p.project_id = a.project_id
  JOIN client    c ON c.client_id  = p.client_id
  JOIN employee  e ON e.emp_id     = a.emp_id
  JOIN developer d ON d.emp_id     = a.emp_id
  JOIN job_role  r ON r.role_id    = a.role_id
 WHERE a.start_date <= %s AND a.end_date >= %s
 ORDER BY p.project_code, r.sort_order, e.emp_name"""


@bp.get("/")
@login_required
def index():
    user = session["user"]
    if user["auth_role"] == "EXECUTIVE":
        kpi = db.query("""
            SELECT (SELECT COUNT(*) FROM project WHERE status = 'IN_PROGRESS') AS inprog,
                   (SELECT COUNT(*) FROM project WHERE status = 'PLANNED') AS planned,
                   (SELECT COUNT(DISTINCT emp_id) FROM assignment WHERE CURDATE() BETWEEN start_date AND end_date) AS assigned,
                   (SELECT COUNT(*) FROM developer d JOIN employee e ON e.emp_id = d.emp_id WHERE e.status = 'ACTIVE') AS devs,
                   (SELECT COUNT(*) FROM developer d JOIN employee e ON e.emp_id = d.emp_id
                     WHERE e.status = 'ACTIVE' AND IFNULL((SELECT SUM(participation_rate) FROM assignment a
                        WHERE a.emp_id = d.emp_id AND CURDATE() BETWEEN a.start_date AND a.end_date), 0) < 100) AS available,
                   (SELECT COUNT(*) FROM evaluation WHERE eval_type = 'CUSTOMER' AND status = 'REQUESTED') AS cust_pending,
                   (SELECT COUNT(*) FROM change_request WHERE status = 'REVIEWING') AS cr_pending""", one=True)
        # [데모 시나리오 1] 진행 중 프로젝트별 현재 투입 현황 (프로젝트 ⋈ 발주처 ⋈ 투입 ⋈ 직원 ⋈ 직무)
        staffing = db.query("""
            SELECT p.project_id, p.project_code, p.project_name, c.client_name, p.start_date, p.end_date,
                   COUNT(a.assignment_id) AS headcount,
                   ROUND(IFNULL(SUM(a.participation_rate), 0) / 100, 1) AS fte,
                   MAX(CASE WHEN r.role_code = 'PM' THEN e.emp_name END) AS pm_name,
                   GROUP_CONCAT(CONCAT(r.role_name, ' ', e.emp_name) ORDER BY r.sort_order, e.emp_name SEPARATOR ' · ') AS members
              FROM project p
              JOIN client c ON c.client_id = p.client_id
              LEFT JOIN assignment a ON a.project_id = p.project_id AND CURDATE() BETWEEN a.start_date AND a.end_date
              LEFT JOIN employee e ON e.emp_id = a.emp_id
              LEFT JOIN job_role r ON r.role_id = a.role_id
             WHERE p.status = 'IN_PROGRESS'
             GROUP BY p.project_id, p.project_code, p.project_name, c.client_name, p.start_date, p.end_date
             ORDER BY p.start_date""")
        roles = db.query("""SELECT r.role_name, COUNT(*) AS cnt FROM assignment a JOIN job_role r ON r.role_id = a.role_id
                            WHERE CURDATE() BETWEEN a.start_date AND a.end_date GROUP BY r.role_id, r.role_name, r.sort_order ORDER BY r.sort_order""")
        return render_template("dashboard_exec.html", kpi=kpi, staffing=staffing, roles=roles)

    me = user["emp_id"]
    current = db.query("SELECT * FROM v_assignment_detail WHERE emp_id = %s AND CURDATE() BETWEEN start_date AND end_date ORDER BY start_date", (me,))
    upcoming = db.query("SELECT * FROM v_assignment_detail WHERE emp_id = %s AND start_date > CURDATE() ORDER BY start_date", (me,))
    todo = db.query("""
        SELECT COUNT(*) AS cnt FROM assignment a JOIN project p ON p.project_id = a.project_id
         WHERE p.status = 'COMPLETED' AND a.emp_id <> %s
           AND EXISTS (SELECT 1 FROM assignment x WHERE x.project_id = a.project_id AND x.emp_id = %s)
           AND NOT EXISTS (SELECT 1 FROM evaluation ev JOIN peer_eval pe ON pe.eval_id = ev.eval_id
                            WHERE ev.project_id = a.project_id AND ev.evaluatee_emp_id = a.emp_id AND pe.evaluator_emp_id = %s)""",
        (me, me, me), one=True)
    received = db.query("""SELECT s.*, p.project_code, p.project_name FROM v_project_eval_summary s JOIN project p ON p.project_id = s.project_id
                           WHERE s.evaluatee_emp_id = %s ORDER BY p.end_date DESC LIMIT 5""", (me,))
    return render_template("dashboard_emp.html", current=current, upcoming=upcoming, todo=todo["cnt"], received=received)


@bp.get("/reports/staffing")
@executive_required
def staffing():
    d = request.args.get("date") or date.today().isoformat()
    rows = db.query(SQL_STAFFING_AT, (d, d))
    projects = {}
    for r in rows:
        projects.setdefault(r["project_id"], {"info": r, "members": []})["members"].append(r)
    return render_template("reports/staffing.html", d=d, projects=projects, total=len(rows))


@bp.get("/reports/evaluations")
@executive_required
def evaluations():
    project_id = request.args.get("project_id", type=int)
    projects = db.query("SELECT project_id, project_code, project_name FROM project WHERE status = 'COMPLETED' ORDER BY end_date DESC")
    # [데모 시나리오 4] 프로젝트별 피평가자 평가 종합 (고객/PM/동료 가중 평균 → 인센티브 등급)
    rows = db.query(f"""
        SELECT s.*, e.emp_no, e.emp_name, d.skill_grade, p.project_code, p.project_name, p.end_date
          FROM v_project_eval_summary s
          JOIN employee  e ON e.emp_id = s.evaluatee_emp_id
          JOIN developer d ON d.emp_id = s.evaluatee_emp_id
          JOIN project   p ON p.project_id = s.project_id
         {"WHERE s.project_id = %s" if project_id else ""}
         ORDER BY p.end_date DESC, s.weighted_score DESC""", (project_id,) if project_id else None)
    details = []
    if project_id:
        details = db.query("""
            SELECT ev.eval_id, ev.eval_type, ev.status, ev.eval_date, ev.overall_comment,
                   te.emp_name AS evaluatee_name,
                   COALESCE(cc.contact_name, pe1.emp_name, pe2.emp_name) AS evaluator_name,
                   s.avg_score, s.work_score, s.comm_score,
                   GROUP_CONCAT(CONCAT(it.item_name, ': ', dt.score, '점 - ', IFNULL(dt.comment, '')) ORDER BY it.item_id SEPARATOR ' / ') AS detail_text
              FROM evaluation ev
              JOIN employee te ON te.emp_id = ev.evaluatee_emp_id
              LEFT JOIN v_eval_score s ON s.eval_id = ev.eval_id
              LEFT JOIN customer_eval ce ON ce.eval_id = ev.eval_id
              LEFT JOIN client_contact cc ON cc.contact_id = ce.contact_id
              LEFT JOIN pm_eval pm ON pm.eval_id = ev.eval_id
              LEFT JOIN employee pe1 ON pe1.emp_id = pm.evaluator_emp_id
              LEFT JOIN peer_eval pr ON pr.eval_id = ev.eval_id
              LEFT JOIN employee pe2 ON pe2.emp_id = pr.evaluator_emp_id
              LEFT JOIN eval_detail dt ON dt.eval_id = ev.eval_id
              LEFT JOIN eval_item it ON it.item_id = dt.item_id
             WHERE ev.project_id = %s
             GROUP BY ev.eval_id, ev.eval_type, ev.status, ev.eval_date, ev.overall_comment, te.emp_name,
                      cc.contact_name, pe1.emp_name, pe2.emp_name, s.avg_score, s.work_score, s.comm_score
             ORDER BY te.emp_name, FIELD(ev.eval_type, 'CUSTOMER', 'PM', 'PEER')""", (project_id,))
    return render_template("reports/evaluations.html", rows=rows, projects=projects, project_id=project_id, details=details)


@bp.get("/reports/incentive")
@executive_required
def incentive():
    year = request.args.get("year", type=int) or date.today().year
    years = db.query("SELECT DISTINCT YEAR(COALESCE(actual_end_date, end_date)) AS y FROM project WHERE status = 'COMPLETED' ORDER BY y DESC")
    # [데모 시나리오 5] 연도별 인센티브 산정 기초자료 (종료 프로젝트 평가 종합 → 개인별 평균·등급·지급 권고액)
    rows = db.query("""
        SELECT e.emp_id, e.emp_no, e.emp_name, d.skill_grade,
               COUNT(*) AS project_cnt,
               ROUND(AVG(s.weighted_score), 2) AS avg_score,
               SUM(s.incentive_grade = 'S') AS s_cnt, SUM(s.incentive_grade = 'A') AS a_cnt,
               SUM(s.incentive_grade = 'B') AS b_cnt, SUM(s.incentive_grade = 'C') AS c_cnt,
               (SELECT COUNT(*) FROM pm_eval pm JOIN evaluation ev ON ev.eval_id = pm.eval_id JOIN project p2 ON p2.project_id = ev.project_id
                 WHERE ev.evaluatee_emp_id = e.emp_id AND pm.recommend_incentive = 1
                   AND YEAR(COALESCE(p2.actual_end_date, p2.end_date)) = %s) AS pm_recommend_cnt,
               CASE WHEN AVG(s.weighted_score) >= 4.5 THEN 'S' WHEN AVG(s.weighted_score) >= 4.0 THEN 'A'
                    WHEN AVG(s.weighted_score) >= 3.0 THEN 'B' ELSE 'C' END AS final_grade,
               CASE WHEN AVG(s.weighted_score) >= 4.5 THEN 1.5 WHEN AVG(s.weighted_score) >= 4.0 THEN 1.0
                    WHEN AVG(s.weighted_score) >= 3.0 THEN 0.5 ELSE 0 END * 1000000 * COUNT(*) AS recommended_bonus
          FROM v_project_eval_summary s
          JOIN project   p ON p.project_id = s.project_id
          JOIN employee  e ON e.emp_id = s.evaluatee_emp_id
          JOIN developer d ON d.emp_id = s.evaluatee_emp_id
         WHERE p.status = 'COMPLETED' AND YEAR(COALESCE(p.actual_end_date, p.end_date)) = %s
         GROUP BY e.emp_id, e.emp_no, e.emp_name, d.skill_grade
         ORDER BY avg_score DESC, project_cnt DESC""", (year, year))
    return render_template("reports/incentive.html", rows=rows, year=year, years=[y["y"] for y in years])
