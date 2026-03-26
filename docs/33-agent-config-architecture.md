# Agent 配置管理系统 - Architecture Design

- ID: 33
- Topic: `agent-config`
- Stage: `architecture`
- Status: Draft
- File: `33-agent-config-architecture.md`
- Upstream: [32-agent-config-prd.md](./32-agent-config-prd.md)
- Downstream: N/A

## Requirement Mapping
| PRD 验收项 | 设计决策 |
| --- | --- |
| 统一 agent 配置注册中心 | 新建 `agent_configs` 表 + `agent_config_service.py` |
| 运行时动态修改 | 每次请求从 DB 读取配置，无缓存 |
| 管理后台 API | `app/api/routes/admin.py` CRUD + test |
| 向后兼容 | `AGENT_DEFAULTS` 字典兜底 + 环境变量回退 |
| 改造现有 LLM 服务 | 增加可选 `db` 参数，渐进式改造 |

## System Design

### 数据模型

```sql
CREATE TABLE agent_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name VARCHAR(64) UNIQUE NOT NULL,
    display_name VARCHAR(128) NOT NULL,
    description TEXT,
    provider VARCHAR(32) NOT NULL,          -- siliconflow / whatai
    model VARCHAR(128) NOT NULL,
    base_url VARCHAR(512),                  -- null = 使用 provider 默认 base_url
    api_key_ref VARCHAR(64),                -- null = 使用 provider 默认 api_key
    temperature FLOAT DEFAULT 0.2,
    timeout_seconds INTEGER DEFAULT 180,
    max_tokens INTEGER,
    system_prompt TEXT,
    user_prompt_template TEXT,
    is_enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 配置解析优先级

```
1. agent_configs 表中 node_name 匹配的记录
2. AGENT_DEFAULTS[node_name] + llm_settings 环境变量
```

### 核心服务

```python
# agent_config_service.py

@dataclass(frozen=True)
class ResolvedAgentConfig:
    node_name: str
    display_name: str
    provider: str
    model: str
    base_url: str
    api_key: str           # 解密后的实际密钥
    temperature: float
    timeout_seconds: int
    max_tokens: Optional[int]
    system_prompt: Optional[str]
    user_prompt_template: Optional[str]
    is_enabled: bool
    source: str            # "database" | "default"

def get_agent_config(db: Session, node_name: str) -> ResolvedAgentConfig:
    """查询 DB → 回退 AGENT_DEFAULTS → 组合完整配置"""

def get_llm_client_for_agent(db: Session, node_name: str) -> tuple[BaseLlmClient, ResolvedAgentConfig]:
    """构建 BaseLlmClient + 返回完整配置（含 prompt）"""
```

### API 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/admin/agents` | 列出所有 agent（合并 DB + DEFAULTS）|
| GET | `/api/admin/agents/{node_name}` | 获取单个 agent 详情 |
| PUT | `/api/admin/agents/{node_name}` | 创建或更新配置 (upsert) |
| POST | `/api/admin/agents/{node_name}/test` | 发送测试 prompt 验证连通性 |

### 改造策略

各 LLM service 的改造遵循相同模式：

```python
# 改造前
def analyze_question(question_text: str, *, grade: str = ""):
    client = get_siliconflow_client()
    payload = {"model": client.default_model, ...}

# 改造后
def analyze_question(question_text: str, *, grade: str = "", db: Session = None):
    if db:
        llm_client, config = get_llm_client_for_agent(db, "question_analyze")
        model = config.model
        system_prompt = config.system_prompt or _DEFAULT_SYSTEM_PROMPT
    else:
        # 向后兼容回退
        client = get_siliconflow_client()
        llm_client = client.base_client
        model = client.default_model
        system_prompt = _DEFAULT_SYSTEM_PROMPT
    payload = {"model": model, ...}
```

### 需修改的文件清单

| 文件 | 改动 |
|------|------|
| `app/db/models/agent_config.py` | **新建** AgentConfig 模型 |
| `app/db/models/__init__.py` | 注册新模型 |
| `app/services/agent_config_service.py` | **新建** 配置服务 |
| `app/api/routes/admin.py` | **新建** 管理路由 |
| `app/schemas/admin.py` | **新建** 管理 Schema |
| `app/api/router.py` | 注册 admin 路由 |
| `app/services/llm_client_service.py` | BaseLlmClient 增加工厂方法 |
| `app/services/ocr_service.py` | 改用 agent 配置 |
| `app/services/question_analysis_service.py` | 改用 agent 配置 |
| `app/services/diagram_llm_service.py` | 改用 agent 配置 |
| `app/api/routes/ocr.py` | 传递 db session |
| `alembic/versions/xxx_add_agent_configs.py` | **新建** 迁移脚本 |
| `lf-smart-paper-web/src/services/api.js` | 增加 admin API 函数 |
| `lf-smart-paper-web/src/pages/management/WorkspacePage.jsx` | 增加 Agent 管理区域 |

### 数据流

```
请求 → route (注入 db) → service 调用 get_llm_client_for_agent(db, node_name)
  → agent_config_service 查询 DB
    → 有记录: 用 DB 配置 + provider 密钥 构建 BaseLlmClient
    → 无记录: 用 AGENT_DEFAULTS + 环境变量 构建 BaseLlmClient
  → 返回 (llm_client, config) → service 使用 client 发起 LLM 调用
```

### 测试方案
1. 单元测试：`agent_config_service` 的回退逻辑
2. 接口测试：admin API 的 CRUD + test
3. 回归测试：OCR、题目分析、SVG 生成功能正常
4. 手动验证：前端管理页面可编辑和测试 agent
