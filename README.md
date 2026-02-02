# lf-smart-paper-service

FastAPI 后端服务。

## 开发

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

健康检查：`http://localhost:8000/api/health`
