"""개발 서버 실행:  .venv/bin/python run.py  (http://127.0.0.1:5001)"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=True)
