import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, session

from . import db


def _load_dotenv():
    """python-dotenv 없이 .env 를 읽는다 (KEY=VALUE, # 주석)."""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def create_app():
    _load_dotenv()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key"),
        DB=dict(
            host=os.environ.get("DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("DB_PORT", "3306")),
            user=os.environ.get("DB_USER", "pms"),
            password=os.environ.get("DB_PASSWORD", "pms1234"),
            database=os.environ.get("DB_NAME", "si_pms"),
        ),
    )
    app.teardown_appcontext(db.close_db)

    from . import auth, changes, employees, projects, evaluations, reports, training
    app.register_blueprint(auth.bp)
    app.register_blueprint(employees.bp)
    app.register_blueprint(projects.bp)
    app.register_blueprint(evaluations.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(changes.bp)
    app.register_blueprint(training.bp)

    @app.context_processor
    def inject_globals():
        return dict(
            current_user=session.get("user"),
            is_executive=(session.get("user") or {}).get("auth_role") == "EXECUTIVE",
            is_trainer=bool((session.get("user") or {}).get("is_trainer")),
            today=date.today(),
            now=datetime.now(),
        )

    @app.template_filter("won")
    def won(v):
        return f"{int(v):,}원" if v is not None else "-"

    @app.template_filter("pct")
    def pct(v):
        return f"{v}%" if v is not None else "-"

    return app
