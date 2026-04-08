#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 参数解析 ────────────────────────────────────────────
MODE="${1:-}"
if [[ -z "$MODE" ]]; then
  echo "用法: $0 <dev|prod> [--debug]"
  echo ""
  echo "  dev          后台启动，单进程，带 --reload"
  echo "  prod         后台启动，多进程 (gunicorn)"
  echo "  --debug      前台运行，显示详细日志 (仅 dev)"
  exit 1
fi
shift

if [[ "$MODE" != "dev" && "$MODE" != "prod" ]]; then
  echo "错误: 环境必须是 dev 或 prod，当前: $MODE"
  exit 1
fi

DEBUG_MODE=false
for arg in "$@"; do
  if [[ "$arg" == "--debug" || "$arg" == "-d" ]]; then
    DEBUG_MODE=true
  fi
done

# ── 基础配置 ────────────────────────────────────────────
PORT="${PORT:-8100}"
APP_MODULE="${APP_MODULE:-app.main:app}"
UVICORN_LOG_LEVEL="${UVICORN_LOG_LEVEL:-info}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/server.log}"
RUN_MIGRATIONS_ON_START="${RUN_MIGRATIONS_ON_START:-true}"
DEV_RELOAD="${DEV_RELOAD:-true}"

STARTUP_TIMEOUT_SEC="${STARTUP_TIMEOUT_SEC:-30}"
STARTUP_CHECK_INTERVAL_SEC="${STARTUP_CHECK_INTERVAL_SEC:-1}"
HEALTH_URL="http://127.0.0.1:$PORT/api/health"
RELOAD_DIR_APP="${RELOAD_DIR_APP:-$ROOT_DIR/app}"
RELOAD_DIR_ALEMBIC="${RELOAD_DIR_ALEMBIC:-$ROOT_DIR/alembic}"

start_dev_server() {
  local use_reload="$1"
  if [[ "$use_reload" == "true" ]]; then
    WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-true}" \
    WATCHFILES_IGNORE_PERMISSION_DENIED="${WATCHFILES_IGNORE_PERMISSION_DENIED:-true}" \
    "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
      --host 0.0.0.0 --port "$PORT" \
      --log-level "$UVICORN_LOG_LEVEL" --reload \
      --reload-dir "$RELOAD_DIR_APP" \
      --reload-dir "$RELOAD_DIR_ALEMBIC" \
      >> "$LOG_FILE" 2>&1 &
  else
    "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
      --host 0.0.0.0 --port "$PORT" \
      --log-level "$UVICORN_LOG_LEVEL" \
      >> "$LOG_FILE" 2>&1 &
  fi
  echo $!
}

# ── 1. 检测并激活 Python 环境 ───────────────────────────
cd "$ROOT_DIR"

if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
  echo "使用已激活的虚拟环境: $VIRTUAL_ENV"
else
  echo "错误: 未找到 .venv 目录，且没有已激活的虚拟环境"
  echo "请先运行: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "错误: 未找到 Python"
  exit 1
fi

# 检查 llm_secrets 配置
if [[ ! -f "app/core/llm_secrets.py" ]]; then
  echo "错误: 缺少 app/core/llm_secrets.py"
  echo "运行: cp app/core/llm_secrets.example.py app/core/llm_secrets.py"
  exit 1
fi

# ── 2. 启动前执行数据库迁移 ─────────────────────────────
if [[ "$RUN_MIGRATIONS_ON_START" == "true" ]]; then
  echo "执行数据库迁移..."
  if ! alembic upgrade head; then
    echo "错误: 数据库迁移失败"
    exit 1
  fi
fi

# ── 3. 如果端口被占用，kill 掉 ──────────────────────────
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
  if [[ -n "$PIDS" ]]; then
    echo "端口 $PORT 被占用 (PID: $PIDS)，正在停止..."
    kill $PIDS 2>/dev/null || true
    sleep 1
    # 再次检查，强制 kill
    PIDS="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
    if [[ -n "$PIDS" ]]; then
      kill -9 $PIDS 2>/dev/null || true
      sleep 0.5
    fi
    echo "已停止"
  fi
fi

# ── 4. 准备日志目录 ─────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── 5. 启动服务 ─────────────────────────────────────────
echo ""
echo "========================================="
echo "启动 Smart Paper Service"
echo "  环境: $MODE"
echo "  端口: $PORT"
echo "  日志: $LOG_FILE"
echo "========================================="

if [[ "$DEBUG_MODE" == true ]]; then
  echo "调试模式：前台运行，Ctrl+C 停止"
  echo ""
  if [[ "$DEV_RELOAD" == "true" ]]; then
    exec env \
      WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-true}" \
      WATCHFILES_IGNORE_PERMISSION_DENIED="${WATCHFILES_IGNORE_PERMISSION_DENIED:-true}" \
      "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
        --host 0.0.0.0 --port "$PORT" \
        --log-level debug --reload \
        --reload-dir "$RELOAD_DIR_APP" \
        --reload-dir "$RELOAD_DIR_ALEMBIC"
  fi
  exec "$PYTHON_BIN" -m uvicorn "$APP_MODULE" \
    --host 0.0.0.0 --port "$PORT" \
    --log-level debug
  # exec 替换当前进程，不会继续往下执行
fi

if [[ "$MODE" == "dev" ]]; then
  if [[ "$DEV_RELOAD" == "true" ]]; then
    WEB_PID="$(start_dev_server true)"
    sleep 2
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
      if tail -50 "$LOG_FILE" | grep -q "Operation not permitted"; then
        echo "检测到文件监听权限问题，回退为无热重载模式"
        WEB_PID="$(start_dev_server false)"
      fi
    fi
  else
    WEB_PID="$(start_dev_server false)"
  fi
else
  WORKERS="${UVICORN_WORKERS:-4}"
  "$PYTHON_BIN" -m gunicorn -k uvicorn.workers.UvicornWorker \
    -b "0.0.0.0:$PORT" "$APP_MODULE" \
    --workers "$WORKERS" \
    --log-level "$UVICORN_LOG_LEVEL" \
    --timeout 180 --graceful-timeout 30 \
    >> "$LOG_FILE" 2>&1 &
  WEB_PID=$!
fi
echo "服务进程已启动 (PID: $WEB_PID)"

# ── 6. 健康检查，确认服务就绪后退出 ─────────────────────
echo "等待服务就绪..."
ELAPSED=0
SERVICE_READY=false

while [[ "$ELAPSED" -lt "$STARTUP_TIMEOUT_SEC" ]]; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    SERVICE_READY=true
    break
  fi

  # 检查进程是否还活着
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo ""
    echo "错误: 服务进程已退出 (PID: $WEB_PID)"
    echo "查看日志: tail -50 $LOG_FILE"
    exit 1
  fi

  sleep "$STARTUP_CHECK_INTERVAL_SEC"
  ELAPSED=$((ELAPSED + STARTUP_CHECK_INTERVAL_SEC))
done

if [[ "$SERVICE_READY" == true ]]; then
  echo ""
  echo "========================================="
  echo "服务启动成功"
  echo "  PID:  $WEB_PID"
  echo "  地址: http://localhost:$PORT"
  echo "  文档: http://localhost:$PORT/docs"
  echo "  日志: tail -f $LOG_FILE"
  echo "========================================="
else
  echo ""
  echo "错误: 服务在 ${STARTUP_TIMEOUT_SEC}s 内未就绪"
  echo "查看日志: tail -50 $LOG_FILE"
  exit 1
fi
