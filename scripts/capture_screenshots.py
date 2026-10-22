"""
기능 화면 스크린샷 자동 캡처 (헤드리스 Chrome + DevTools Protocol)
  .venv/bin/python scripts/capture_screenshots.py      →  docs/screenshots/*.jpg
전제: 앱(http://127.0.0.1:5001)과 DB 가 떠 있고, 데이터는 ./db/reset.sh 직후 상태.
* 사용자 Chrome 프로필을 쓰지 않도록 임시 --user-data-dir 로 별도 실행한다.
* 거부 메시지 화면(투입률 초과)은 실제 폼을 제출해 찍지만 DB 가 거부하므로 데이터는 바뀌지 않는다.
"""
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pymysql
import websocket

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
BASE = os.environ.get("APP_URL", "http://127.0.0.1:5001")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333
W, SCALE, MAXH = 1280, 1.5, 1500


def q(sql):
    conn = pymysql.connect(host="127.0.0.1", user="pms", password="pms1234", database="si_pms", charset="utf8mb4")
    with conn.cursor() as cur:
        cur.execute(sql)
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None


class Page:
    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, max_size=None, suppress_origin=True)
        self.mid = 0
        for m in ("Page.enable", "Network.enable", "Runtime.enable"):
            self.call(m)
        self.call("Emulation.setDeviceMetricsOverride", width=W, height=900, deviceScaleFactor=SCALE, mobile=False)

    def call(self, method, **params):
        self.mid += 1
        self.ws.send(json.dumps({"id": self.mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def wait_load(self, timeout=15):
        end = time.time() + timeout
        while time.time() < end:
            self.ws.settimeout(max(0.1, end - time.time()))
            try:
                msg = json.loads(self.ws.recv())
            except websocket.WebSocketTimeoutException:
                break
            if msg.get("method") == "Page.loadEventFired":
                break
        self.ws.settimeout(None)
        time.sleep(0.4)

    def go(self, path):
        self.call("Page.navigate", url=BASE + path)
        self.wait_load()

    def js(self, expr, wait_nav=False):
        r = self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True)
        if wait_nav:
            self.wait_load()
        return r.get("result", {}).get("value")

    def login(self, user):
        self.call("Network.clearBrowserCookies")
        self.go("/auth/login")
        self.js(f"""document.querySelector('[name=login_id]').value='{user}';
                    document.querySelector('[name=password]').value='pass1234';
                    document.querySelector('form').submit();""", wait_nav=True)

    def shot(self, name, anchor=None, height=None):
        y = 0
        if anchor:
            y = max(0, self.js(f"document.querySelector('{anchor}').getBoundingClientRect().top + window.scrollY - 16") or 0)
        full = self.js("document.documentElement.scrollHeight")
        h = min(height or MAXH, full - y)
        data = self.call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                         clip={"x": 0, "y": y, "width": W, "height": h, "scale": 1})["data"]
        png = OUT / f"{name}.png"
        png.write_bytes(base64.b64decode(data))
        jpg = OUT / f"{name}.jpg"
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "78", "--resampleWidth", "1600",
                        str(png), "--out", str(jpg)], check=True, capture_output=True)
        png.unlink()
        print(f"  {jpg.name}  ({jpg.stat().st_size // 1024} KB)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="si-pms-chrome-")
    proc = subprocess.Popen([CHROME, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
                             "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--lang=ko-KR",
                             "--window-size=1280,900", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        target = json.load(urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")))
        p = Page(target["webSocketDebuggerUrl"])

        print("[공통]")
        p.go("/auth/login"); p.shot("01_login", height=700)
        p.go("/auth/signup")
        p.js("""document.getElementById('login_id').value='dev01'; checkId();""")
        time.sleep(0.6); p.shot("02_signup_dup", height=900)

        print("[경영진 ceo]")
        p.login("ceo")
        p.go("/"); p.shot("10_exec_dashboard")
        p.go("/projects"); p.shot("11_projects", height=1100)
        p.go("/projects/15"); p.shot("12_project_detail")
        p.go("/projects/16")   # pm01(박태양)은 같은 기간 P2026-001 에 100% 투입 중 → 50% 추가 시 BR-05
        p.js("""const f=document.querySelector('form[action$="/assignments"]');
                f.querySelector('[name=emp_id]').value='3'; f.querySelector('[name=role_id]').value='5';
                f.querySelector('[name=participation_rate]').value='50'; f.submit();""", wait_nav=True)
        p.shot("13_assignment_rejected", height=760)
        p.go("/reports/staffing?date=2025-06-01"); p.shot("14_staffing_at_date")
        p.go("/employees?emp_type=DEV&skill_id=10&available_on=2026-11-01"); p.shot("15_employee_search", height=1100)
        p.go("/employees/3"); p.shot("16_employee_detail")
        p.go("/reports/evaluations?project_id=1"); p.shot("17_eval_report")
        p.go("/reports/incentive?year=2025"); p.shot("18_incentive", height=1200)
        p.go("/reports/changes"); p.shot("30_change_report")
        cr_pending = q("SELECT cr_id FROM change_request WHERE status='REVIEWING' AND project_id=15 LIMIT 1")
        p.go(f"/changes/{cr_pending}"); p.shot("31_change_decision")
        cr_applied = q("SELECT cr_id FROM change_request WHERE status='APPLIED' AND project_id=15 LIMIT 1")
        p.go(f"/changes/{cr_applied}"); p.shot("32_change_applied")
        p.go("/reports/training"); p.shot("40_training_report")

        print("[PM pm01]")
        p.login("pm01")
        p.go("/evaluations"); p.shot("20_eval_tasks")
        target_emp = q("""SELECT a.emp_id FROM assignment a WHERE a.project_id=14 AND a.emp_id<>3
                          AND NOT EXISTS (SELECT 1 FROM evaluation ev JOIN pm_eval pe USING(eval_id)
                                           WHERE ev.project_id=14 AND ev.evaluatee_emp_id=a.emp_id) LIMIT 1""")
        p.go(f"/evaluations/new?project_id=14&eval_type=PM&evaluatee_emp_id={target_emp}"); p.shot("21_pm_eval_form")
        p.go("/projects/15#changes"); p.shot("33_project_changes", anchor="#changes", height=1050)

        print("[발주처 담당자: 로그인 없음]")
        p.call("Network.clearBrowserCookies")
        token = q("SELECT ce.access_token FROM customer_eval ce JOIN evaluation ev USING(eval_id) WHERE ev.status='REQUESTED' LIMIT 1")
        p.go(f"/customer-eval/{token}"); p.shot("22_customer_eval_form")

        print("[교육 담당자 edu01]")
        p.login("edu01")
        p.go("/training"); p.shot("41_training_manage")
        cand = p.js("document.querySelector('a[href*=\"plans/new\"]').getAttribute('href')")
        p.go(cand); p.shot("42_training_plan_new")

        print("[개발자 dev01]")
        p.login("dev01")
        p.go("/"); p.shot("50_dev_dashboard", height=1000)
        p.go("/me/training"); p.shot("43_my_training")
        p.go("/me/skills"); p.shot("51_my_skills", height=1000)
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    main()
