# AgenticCommerce — AI 编码协作指南与工程规范 (CLAUDE.md)

本文档是 **AgenticCommerce（自主智能体电商融合平台）** 项目的最高工程指引与 AI 开发军规。所有参与本项目的 AI 编码助手和研发人员必须严格遵守本文档所规定的架构规范、数据规范与编码准则。

---

## 一、项目定位与业务背景

- **项目名称**：AgenticCommerce（自主智能体电商）
- **业务合作方**：环球出海科技有限公司（跨境电商大卖家） × 飞流智能科技
- **核心使命**：解决跨境运营劳动密集、素材制作周期长（5-10天）、文案同质化、广告法违规封店高风险等痛点。
- **一期交付边界**：
  1. **7-Agent 工作流**：自动化完成需求分析、多卖点文案、视觉 Prompt 设计、图片/视频渲染与合规质检，将生产周期压缩至**分钟级**。
  2. **RAG 私有知识库**：基于 PostgreSQL pgvector 沉淀品牌视觉规范、广告法违禁词与类目爆款经验。
  3. **Agent 可观测工作台**：DAG 状态图、节点耗时、Token 统计、Prompt 轨迹与输入输出结构化监控。
  4. **素材审核与打包下载**：一期终点为“生成 → 审核/在线编辑 → 打包下载手动刊登”。
- **二期规划边界**：Amazon、TikTok Shop、Shopify、Temu 多平台 API 对接与一键刊登。

---

## 二、六大架构开发军规 (P0 级强约束)

### 1. 多租户数据隔离原则 (Multi-Tenancy)
- **表结构要求**：除全局租户定义表 `ac_tenant` 外，**所有业务表必须显式包含字段** `tenant_id varchar(32) NOT NULL` 并建立索引。
- **查询与写入过滤**：所有 Repository 查询、Service 业务逻辑、以及 pgvector 向量距离计算，**必须强制带上 `tenant_id` 过滤条件**，严防越权。
- **代码示例**：
  ```python
  stmt = select(Sku).where(Sku.id == sku_id, Sku.tenant_id == current_tenant_id, Sku.is_deleted == 0)
  ```

### 2. 数据库主键与审计字段规范
- **主键规范**：全局统一采用 `varchar(32)`，格式为 **32 位无连字符小写 UUID**（`uuid.uuid4().hex`）。
- **外键约束**：**严禁使用数据库物理外键约束（FOREIGN KEY）**。所有外键关联统一采用 `xxx_id varchar(32)` 逻辑外键，并通过索引加速关联查询。
- **7 大必要审计字段**：所有核心业务实体必须继承 `AuditMixin`，具备以下字段：
  - `id`: `varchar(32)`，主键
  - `tenant_id`: `varchar(32)`，租户隔离标识
  - `created_by`: `varchar(32)`，创建人 ID
  - `updated_by`: `varchar(32)`，最后修改人 ID
  - `create_time`: `timestamp with time zone`，创建时间（默认当前 UTC）
  - `update_time`: `timestamp with time zone`，更新时间（自动更新）
  - `is_deleted`: `smallint`，逻辑删除标识（`0`: 正常, `1`: 已删除）

### 3. API 接口契约与响应规范
- **路径前缀**：所有业务 API 统一前缀为 `/api/v1`。
- **统一响应结构**：
  ```json
  {
    "code": 200,
    "data": {},
    "message": "成功"
  }
  ```
- **命名规范**：JSON 字段命名严格采用小写蛇形 `snake_case`；时间采用 ISO 8601 标准字符串带时区。
- **布尔值表达**：在数据库层与接口交互时，布尔值推荐使用 `0` / `1`（smallint）。
- **认证与鉴权**：接口认证统一采用 JWT Bearer Token，必须通过 FastAPI `Depends(get_current_user_and_tenant)` 注入，不得在路由函数内部裸调。

### 4. LangGraph 7-Agent 状态机与 P-E-V 循环
- **7-Agent 节点职责**：
  1. `Orchestrator`：任务初始化、参数解析、全局进度管控。
  2. `RequirementAnalyzer`：RAG 检索品牌规范与类目痛点，输出本地化卖点报告。
  3. `CreativePlanner`：生成多卖点文案（标题、五点、描述、关键词）与视频分镜框架。
  4. `VisualDesigner`：RAG 检索品牌视觉文档，生成高水准生图/生视频 Prompt 及负向词。
  5. `ImageGenerator`：调用通义万相 Wan 2.1 等厂商渲染商品主图与卖点场景图。
  6. `VideoGenerator`：调用快手可灵 Kling AI 等厂商生成动态电商短视频。
  7. `QualityReviewer`：RAG 检索合规规则，进行广告法禁词硬扫描与综合质量打分。
- **条件路由机制**：
  - **媒体分支路由**：依据 `config.media_type` 分流至 `ImageGenerator`、`VideoGenerator` 或两者并发。
  - **审核与重试路由 (P-E-V 循环)**：
    - 若命中合规红线禁词（如极限词、虚假功效），必须标记 `is_passed = False`。
    - 若 `is_passed == False` 且 `retry_count < max_retries`（默认 2 次），必须携带违规点与修改建议打回至 `CreativePlanner` 执行针对性重生成。
    - 若重试超过上限，流转至 `END` 节点并标记任务为 `failed`，等待人工介入。

### 5. RAG 知识库检索规范
- **向量维度**：全局统一 1024 维（对应通义千问 `text-embedding-v4` 或 `BGE-large-zh-v1.5`）。
- **距离算法**：PostgreSQL pgvector 余弦距离（`vector_cosine_ops`）。
- **检索阈值**：默认相似度阈值 `>= 0.5`，Top-K 默认为 `5`。
- **租户隔离**：向量表 `ac_knowledge_chunk` 检索时必须附加 `WHERE tenant_id = :tenant_id`。

### 6. 可观测与实时事件推送
- **调用记录**：每个 Agent 节点的每次执行必须向 `ac_task_node_run` 表写入完整的输入输出、提示词、Token 消耗与耗时。
- **WebSocket 推送**：节点开始、成功、失败及任务结束时，通过 `/api/v1/ws` 广播状态变更事件。

---

## 三、代码工程目录规范

```text
agentic-commerce/
├─ app/                                  # 后端代码主目录
│  ├─ agent/                             # LangGraph 7-Agent 工作流与状态定义
│  │  ├─ nodes/                          # 7 个 Agent 节点实现
│  │  ├─ graph.py                        # 状态图构建、节点连接与条件边
│  │  ├─ state.py                        # AgentState 共享状态 TypedDict
│  ├─ api/                               # 接口路由层
│  │  └─ v1/                             # /api/v1 各业务模块路由
│  ├─ clients/                           # 基础设施客户端 (PG, Redis, MinIO, AI厂商)
│  ├─ conf/                              # 运行时配置 (基于 Pydantic Settings)
│  ├─ core/                              # 安全、日志、异常体系、依赖注入、中间件
│  ├─ models/                            # SQLAlchemy 2.0 ORM 数据模型 (14 张实体表)
│  ├─ prompt/                            # 提示词渲染与动态拼接工具
│  ├─ repositories/                      # 仓储层 (数据访问封装，强制 tenant_id)
│  ├─ scripts/                           # 数据库初始化、演示种子数据导入脚本
│  └─ services/                          # 领域服务层 (复杂业务逻辑与事务编排)
├─ conf/                                 # 外部部署与环境变量配置
│  ├─ nginx.conf                         # 统一反向代理配置
│  └─ .env.example                       # 环境变量全量模板
├─ docker/                               # 容器化环境配置
│  ├─ postgres/init.sql                  # 初始化 pgvector 向量扩展
│  ├─ redis/redis.conf                   # Redis 基础持久化配置
│  └─ minio/                             # MinIO 数据配置
├─ frontend/                             # 前端项目 (Vue 3 + Vite + TypeScript)
│  ├─ src/
│  │  ├─ views/                          # 15 个业务页面路由
│  │  ├─ components/workbench/           # Agent 可观测工作台组件 (DAG图/Prompt查看器等)
│  │  ├─ stores/                         # Pinia 状态管理
│  │  ├─ api/                            # Axios 请求封装
│  │  └─ router/                         # 前端路由定义
│  ├─ package.json                       # 前端依赖配置
│  ├─ vite.config.ts                     # Vite 代理与编译配置
│  └─ Dockerfile                         # 前端生产构建镜像
├─ data/                                 # 本地持久化与静态资源目录 (已在 .gitignore 忽略)
│  ├─ postgres/                          # PG 容器数据卷挂载
│  ├─ redis/                             # Redis 容器数据卷挂载
│  ├─ minio/                             # MinIO 资源卷挂载
│  └─ static/                            # 静态资产与 Mock 占位图
├─ logs/                                 # 运行时日志目录 (app/access/agent)
├─ prompts/                              # 集中提示词仓库 (7 个 Agent 的 Prompt 模板)
├─ ailog/                                # AI 执行历史全量审计日志 (时间戳归档)
├─ docs/                                 # 架构设计与需求规格说明书
├─ main.py                               # FastAPI 主入口 (端口 8002)
├─ run_workflow.py                       # CLI 智能体工作流调试脚本
├─ docker-compose.infra.yml              # 开发环境：仅基础设施容器化
├─ docker-compose.yml                    # 生产环境：全栈容器化编排
├─ 一键启动.bat                          # Windows 本地开发便捷启动
├─ 一键停止.bat                          # Windows 本地开发便捷停止
├─ pyproject.toml                        # Python 项目定义与依赖
└─ README.md                             # 项目主说明文档
```

---

## 四、本地开发常用指令

```bash
# 1. 启动本地开发基础设施 (PostgreSQL + pgvector, Redis, MinIO)
docker-compose -f docker-compose.infra.yml up -d

# 2. 安装后端依赖 (推荐使用 uv 或 pip)
uv sync
# 或: pip install -e .

# 3. 初始化数据库表结构
python -m app.scripts.init_db

# 4. 导入初始种子数据
python -m app.scripts.seed_data

# 5. 启动后端开发服务 (热重载，默认 8002 端口)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8002

# 6. 启动前端开发服务 (默认 5173 端口)
cd frontend
npm install
npm run dev

# 7. 停止开发基础设施
docker-compose -f docker-compose.infra.yml down
```

---

## 五、AI 编码与协作准则

1. **类型安全**：Python 后端必须 100% 启用类型注解（Type Hints），使用 Pydantic v2 校验请求数据。
2. **异步优先**：涉及数据库 I/O（`asyncpg`）、HTTP 调用（`httpx`）以及 Redis 操作，一律使用异步函数 `async/await`。
3. **禁止硬编码**：任何密钥、配置项均需定义在 `app.conf.config.Settings` 中，严禁在代码中写死明文密码或外部 API Key。
4. **日志合规**：打印日志时严禁输出用户明文密码、API Key 等敏感数据；关键节点日志必须附带 `trace_id`。

---

## 六、AI 执行日志自动归档准则 (ailog/ 与 execution-logger)

每次 AI 编码助手执行用户任务或重大架构变更时，**必须执行日志落盘归档**：
1. **归档目录**：项目根目录下的 `ailog/`。
2. **文件命名格式**：`ailog/YYYY-MM-DD_HH-mm-ss_<action_slug>.md`。
3. **内容必须完整**：包含执行时间戳、用户原始需求、架构思考与决策逻辑、增删改查文件清单、命令执行记录与最终产出结果。
4. **Skill 联动**：严格遵循 `.claude/skills/execution-logger/SKILL.md` 与 `.agents/skills/execution-logger/SKILL.md` 的指引，确保所有历史操作 100% 可追溯。

