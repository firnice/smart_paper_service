# =============================================================================
# 部署配置（复制此文件为 llm_secrets.py 并填写真实值，不要提交到 git）
# =============================================================================

# --- 管理员账号 ---
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "请修改为强密码"

# --- JWT 签名密钥（生产环境务必替换）---
# 生成方式：python3 -c "import secrets; print(secrets.token_hex(32))"
ADMIN_JWT_SECRET = ""
STUDENT_JWT_SECRET = ""

# --- CORS 允许的前端域名（逗号分隔）---
CORS_ORIGINS = "https://your-frontend.com"

# --- 数据库 & 存储 ---
DATABASE_URL = ""          # 留空使用默认 SQLite
STORAGE_BASE_DIR = ""      # 留空使用默认 storage/ 目录
STORAGE_BASE_URL = "https://your-domain/static"

# =============================================================================
# LLM 服务配置
# =============================================================================

SILICONFLOW_API_KEY = "sk-please-fill"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
# Alternative: https://api.siliconflow.com/v1
SILICONFLOW_MODEL = "deepseek-ai/DeepSeek-V3"
SILICONFLOW_OCR_MODEL = "Qwen/Qwen2-VL-72B-Instruct"  # Any VLM/OCR model from SiliconFlow
SILICONFLOW_TIMEOUT_SECONDS = 180

WHATAI_API_KEY = "sk-please-fill"
WHATAI_BASE_URL = "https://api.whatai.cc/v1"
WHATAI_DIAGRAM_CROP_MODEL = "gemini-3.1-flash-image-preview"
WHATAI_DIAGRAM_SVG_MODEL = "gemini-3.1-pro-preview"
WHATAI_TIMEOUT_SECONDS = 180
