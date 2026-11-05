# AgenticCommerce — 智能跨境电商融合平台

<div align="center">

**自主智能体电商内容生成中台 (CBCF Platform)**  
*环球出海科技有限公司 × 飞流智能科技 联合打造*

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2.4-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Vue](https://img.shields.io/badge/Vue-3.4%20%2B%20Vite-4FC08D.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

</div>

---

## 📖 平台全景与背景

**环球出海科技有限公司** 是一家年 GMV 突破 3 亿美元的北美与欧洲跨境电商头部卖家，旗下在 Amazon、TikTok Shop、Shopify 与 Temu 等多个平台全面铺货。面对每日上千款 SKU 的上新需求与短视频带货红利，传统“人工堆叠”模式已到达瓶颈：

- **痛点 1（素材制作周期极长）**：外包设计师/剪辑师单品制作周期长达 **5–10 天**，大促排队严重延误战机。
- **痛点 2（文案撰写低效且同质）**：Amazon 与 TikTok 平台受众偏好割裂，人工编写质量参差不齐、缺乏网感。
- **痛点 3（合规风险高，极易封店）**：欧美广告法审核严格，人工审核易遗漏违禁词，曾因违禁词导致 **300 万美金** 被冻结。
- **痛点 4（企业知识分散断层）**：品牌视觉规范（Brand Guidelines）散落在飞书文档与员工脑中，人员流动导致资产流失。
- **痛点 5（多平台上架繁琐）**：多平台手动复制粘贴上架耗时费力。

**AgenticCommerce 平台** 依托大语言模型与多智能体（Multi-Agent）技术，构建企业私有 RAG 知识库与 7-Agent 协作生成流水线，**将原本 5–10 天的素材制作周期压缩至分钟级完成**，并通过合规硬阻断与 Agent 可观测工作台，打造一站式智能生成中台。

> **工程实施边界说明**：
> - **一期工程（核心产能突围）**：聚焦 AI 7-Agent 生成引擎、PostgreSQL pgvector RAG 合规库、可观测工作台及打包下载。业务终点为“生成 → 审核/在线编辑 → 打包下载手动刊登”。
> - **二期工程（生态闭环）**：多平台（Amazon, TikTok Shop 等）API 对接、店铺授权凭证管理与一键刊登。

---

## 🏛️ 系统架构设计

### 1. 六层分层架构
系统采用“分层架构 + LangGraph 多智能体编排 + WebSocket 事件驱动”的混合架构：

```text
┌─────────────────────────────────────────────────────────────┐
│  第 1 层：前端展示层（Vue 3 + Vite + TypeScript）             │
│  数据看板 | 任务批次 | 素材审核 | 知识库 | Agent 可观测工作台  │
├─────────────────────────────────────────────────────────────┤
│  第 2 层：接口网关层（FastAPI Routers + WebSocket）           │
│  /api/v1 RESTful 路由 | JWT 认证 | 统一响应 | 实时事件推送      │
├─────────────────────────────────────────────────────────────┤
│  第 3 层：领域服务层（Domain Services）                        │
│  用户租户服务 | 任务编排服务 | 知识向量服务 | 厂商调度服务      │
├─────────────────────────────────────────────────────────────┤
│  第 4 层：智能体编排层（LangGraph 7-Agent Workflow）          │
│  Orchestrator → RequirementAnalyzer → CreativePlanner       │
│  → VisualDesigner → Image/Video Generator → QualityReviewer │
├─────────────────────────────────────────────────────────────┤
│  第 5 层：数据访问层（Repositories + Client Pools）           │
│  多租户仓储基类 | PG 会话池 | Redis 客户端 | MinIO 客户端    │
├─────────────────────────────────────────────────────────────┤
│  第 6 层：基础设施层（Infrastructure）                         │
│  PostgreSQL 16 (pgvector) | Redis 7 | MinIO | Docker        │
└─────────────────────────────────────────────────────────────┘
```

### 2. 7-Agent 工作流拓扑与 P-E-V 循环
采用“规划 (Plan) - 执行 (Execute) - 验证 (Verify)”闭环控制，内置合规硬阻断与自动重试机制：

```text
                        ┌──────────────┐
                        │    START     │
                        └──────┬───────┘
                               │
                    ┌──────────▼──────────┐
                    │   Orchestrator      │  编排调度 Agent (任务解析与进度管控)
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │ RequirementAnalyzer │  需求分析 Agent (RAG: 品牌规范/类目痛点)
                    └──────────┬──────────┘
                               │
              ┌────────────────▼────────────────┐
              │        CreativePlanner          │◄────────┐
              │ 创意策划 Agent (多卖点文案/分镜) │         │ (重试流:
              └────────────────┬────────────────┘         │  带修改建议)
                               │                          │
                    ┌──────────▼──────────┐               │
                    │   VisualDesigner    │  视觉设计 Agent (生图/生视频Prompt构建)
                    └──────────┬──────────┘               │
                               │                          │
                    ┌──────────▼──────────┐               │
                    │ 条件路由: media_type │               │
                    └───┬─────────────┬───┘               │
                        │             │                   │
           ┌────────────▼──┐   ┌──────▼────────────┐      │
           │ ImageGenerator│   │  VideoGenerator   │      │
           │ 图片生成 Agent │   │  视频生成 Agent   │      │
           │ (通义万相 2.1) │   │  (快手可灵 Kling) │      │
           └───────┬───────┘   └────────┬──────────┘      │
                   │                    │                 │
                   └──────────┬─────────┘                 │
                              │                           │
                 ┌────────────▼────────────┐              │
                 │     QualityReviewer     │  质量审核 Agent (RAG: 广告法硬阻断/评分)
                 └────────────┬────────────┘              │
                              │                           │
                 ┌────────────▼────────────┐              │
                 │   条件路由: is_passed?   │              │
                 └──┬──────────┬─────────┬─┘              │
                    │          │         │                │
                 passed      retry     failed             │
                    │          │         │                │
                    │          └─────────┴────────────────┘
                    │                   (retry_count <= 2)
                    ▼
                 ┌─────┐
                 │ END │  生成完成 (入库 MinIO/PostgreSQL 并推送前端)
                 └─────┘
```

---

## 🛠️ 技术栈与端口映射

| 组件/服务 | 选型技术 | 默认运行端口 | 用途与说明 |
| :--- | :--- | :--- | :--- |
| **后端主服务** | Python 3.12 / FastAPI / Uvicorn | `8002` | API 业务网关与 WebSocket 任务实时推送 |
| **智能体框架** | LangGraph 1.2.4 / LangChain 1.3.7 | 进程内 | 7-Agent 状态图编排与持久化 Checkpoint |
| **前端工作台** | Vue 3 / Vite / TypeScript / Pinia | `5173` (宿主) / `80` (容器) | Agent 可观测工作台与资产审核编辑中心 |
| **业务数据库** | PostgreSQL 16 + pgvector 插件 | `5432` | 多租户业务数据存储与 1024 维向量 HNSW 检索 |
| **缓存/信号量**| Redis 7-alpine | `6379` | 任务队列、并发信号量控制、Token 缓存 |
| **对象存储** | MinIO 对象存储 | `9000` (API) / `9001` (Console) | 商品主图、卖点图、动态短视频、分镜脚本文件 |
| **反向代理** | Nginx Alpine | `80` / `443` | 生产反向代理网关、静态资源托管与 SSL 终结 |

---

## 📂 项目完整目录结构

```text
agentic-commerce/
├─ app/                                  # 后端代码目录
│  ├─ agent/                             # 智能体与 LangGraph 工作流
│  │  ├─ nodes/                          # 7-Agent 独立实现节点
│  │  │  ├─ orchestrator.py              # 编排调度 Agent
│  │  │  ├─ requirement_analyzer.py      # 需求分析 Agent (集成 RAG)
│  │  │  ├─ creative_planner.py          # 创意策划 Agent (多卖点文案)
│  │  │  ├─ visual_designer.py           # 视觉设计 Agent (Prompt 生成)
│  │  │  ├─ image_generator.py           # 图片生成 Agent (通义万相适配)
│  │  │  ├─ video_generator.py           # 视频生成 Agent (可灵 Kling 适配)
│  │  │  └─ quality_reviewer.py          # 质量审核 Agent (合规硬阻断)
│  │  ├─ graph.py                        # LangGraph 状态图编译与条件分支
│  │  ├─ state.py                        # AgentState 共享状态定义
│  │  ├─ context.py                      # 工作流上下文与 trace_id 跟踪
│  │  └─ llm.py                          # 大模型延迟加载与厂商适配
│  ├─ api/                               # 接口路由层
│  │  └─ v1/                             # /api/v1 业务路由 (认证/SKU/任务/资产/WS等)
│  ├─ clients/                           # 基础设施客户端 (Postgres, Redis, MinIO, AI Factory)
│  ├─ conf/                              # 应用级配置 (Pydantic Settings)
│  ├─ core/                              # 安全 JWT、日志、异常体系、依赖注入、中间件
│  ├─ models/                            # SQLAlchemy 2.0 ORM 实体 (14 张核心业务表)
│  ├─ prompt/                            # 提示词解析与装配工具
│  ├─ repositories/                      # 仓储层 (强制附加 tenant_id 隔离)
│  ├─ scripts/                           # 数据库结构初始化 (init_db) 与初始种子数据导入
│  └─ services/                          # 领域服务层
├─ conf/                                 # 部署与环境配置文件
│  ├─ nginx.conf                         # Nginx 反向代理配置
│  └─ .env.example                       # 环境变量全量示例模板
├─ docker/                               # 容器化环境配置文件
│  ├─ postgres/init.sql                  # 初始化 PostgreSQL pgvector 扩展
│  ├─ redis/redis.conf                   # Redis 持久化配置
│  └─ minio/                             # MinIO 存储配置
├─ frontend/                             # Vue 3 前端代码目录
│  ├─ src/
│  │  ├─ views/                          # 15 个功能模块页面路由
│  │  ├─ components/workbench/           # 可观测工作台组件 (DAG图/Prompt查看器/IO详情)
│  │  ├─ stores/                         # Pinia 状态仓库
│  │  ├─ api/                            # Axios 请求封装
│  │  └─ router/                         # 前端路由
│  ├─ package.json                       # 前端依赖配置
│  ├─ vite.config.ts                     # Vite 代理配置
│  └─ Dockerfile                         # 前端生产构建镜像
├─ data/                                 # 本地持久化与静态资源目录 (已在 .gitignore 忽略)
│  ├─ postgres/                          # PG 容器数据卷映射
│  ├─ redis/                             # Redis 容器数据卷映射
│  ├─ minio/                             # MinIO 资源存储映射
│  └─ static/                            # 静态资产与 Mock 占位图
├─ logs/                                 # 应用业务、访问、Agent 节点日志
├─ prompts/                              # 集中提示词仓库 (7 个 Agent 的 Prompt 模板)
├─ tests/                                # 单元测试、集成测试与 Agent 评估测试
├─ docs/                                 # 需求纪要、SRS 规格书、架构设计、数据库与 API 文档
├─ main.py                               # FastAPI 主入口 (8002 端口)
├─ run_workflow.py                       # CLI 智能体工作流独立运行与测试脚本
├─ docker-compose.infra.yml              # 开发环境仅基础设施编排 (PG, Redis, MinIO)
├─ docker-compose.yml                    # 生产环境全容器化部署编排
├─ 一键启动.bat                          # Windows 本地开发便捷启动脚本
├─ 一键停止.bat                          # Windows 本地开发便捷停止脚本
├─ pyproject.toml                        # 后端 Python 项目配置与依赖清单
├─ CLAUDE.md                             # AI 协作开发指南与六大架构军规
└─ README.md                             # 项目主说明文档
```

---

## 🚀 极速启动指南

### 1. 环境准备
确保本机已安装：
- **Docker & Docker Compose**
- **Python 3.12+**
- **Node.js 20+**
- 推荐安装包管理工具：`uv` (Python) 和 `npm` / `pnpm` (Node)

### 2. 本地开发环境启动（推荐）

#### 步骤一：配置环境变量
```bash
# 复制环境变量模板
cp conf/.env.example .env
# 编辑 .env 文件，填入你的模型 API Key (如 DASHSCOPE_API_KEY)
```

#### 步骤二：启动基础设施容器 (Postgres + Redis + MinIO)
```bash
# 方式 A: 执行 Windows 批处理脚本
一键启动.bat

# 方式 B: 手动执行 Docker Compose
docker-compose -f docker-compose.infra.yml up -d
```

#### 步骤三：安装后端依赖并初始化数据库
```bash
# 安装后端依赖
uv sync
# 或: pip install -e .

# 初始化数据库表结构（创建 14 张核心业务表与 pgvector 扩展）
python -m app.scripts.init_db

# 导入初始演示数据
python -m app.scripts.seed_data
```

#### 步骤四：启动后端与前端服务
```bash
# 终端 1：启动 FastAPI 后端 (支持热重载)
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8002

# 终端 2：启动 Vue 3 前端
cd frontend
npm install
npm run dev
```

### 3. 服务访问控制台速查

| 服务名称 | 访问地址 | 默认账号 / 凭证 |
| :--- | :--- | :--- |
| **前端应用工作台** | `http://localhost:5173` | 界面自主注册或使用演示账号 |
| **后端 API 文档 (Swagger)** | `http://localhost:8002/docs` | 接口免密交互调试 |
| **后端 API 文档 (ReDoc)** | `http://localhost:8002/redoc` | 规范文档展示 |
| **MinIO 对象存储控制台** | `http://localhost:9001` | `minioadmin` / `minioadmin` |
| **PostgreSQL 数据库** | `localhost:5432` | 用户: `postgres` / 库: `agentic_commerce` |

---

## 🔒 核心开发军规速查

在参与本项目开发前，请务必详读 [CLAUDE.md](./CLAUDE.md)。以下为核心要点：
1. **多租户隔离**：所有业务实体必须携带 `tenant_id varchar(32)`，所有查询与向量计算必须包含租户过滤。
2. **主键与审计**：主键为 32 位无连字符 UUID，严禁使用数据库物理外键，所有表包含 7 大必要审计字段。
3. **接口规范**：统一前缀 `/api/v1`，统一响应格式 `{code, data, message}`，命名使用 `snake_case`。
4. **P-E-V 循环**：合规审查命中极限词或禁令必须阻断，重做重试上限为 2 次。

---

## 📑 规格文档中心索引

详细设计规范沉淀在 `docs/` 目录下，详见 [docs/README.md](./docs/README.md)：
- **[01_客户需求纪要.md](./docs/01_客户需求纪要.md)**：客户痛点深度剖析与商业目标对齐
- **[02_软件需求规格说明书（SRS）.md](./docs/02_软件需求规格说明书（SRS）.md)**：F01~F17 完整功能与非功能性需求
- **[03_系统架构设计说明书.md](./docs/03_系统架构设计说明书.md)**：分层设计、7-Agent 状态图拓扑、部署拓扑与中间件机制
- **[04_数据库设计说明书.md](./docs/04_数据库设计说明书.md)**：14 张核心业务表 DDL、索引策略与 pgvector 向量规范
- **[05_API 接口设计说明书.md](./docs/05_API 接口设计说明书.md)**：RESTful 接口契约、WebSocket 实时推送协议与示例

---

## 🗓️ 项目交付路线图 (Roadmap)

```text
2026 Q3 (一期：核心产能突围) ──► 2026 Q4 (二期：平台生态闭环)
├─ 7-Agent 视觉与文案工作流       ├─ Amazon / TikTok Shop API 授权
├─ RAG 企业私有知识库 (pgvector)   ├─ 多平台商品类目属性映射
├─ Agent 可观测工作台与 DAG 可视化  ├─ 一键批量刊登与状态回调
└─ 素材在线审核与打包下载发布      └─ 智能补货与多平台订单数据回流
```

---

## 📄 版权与维护

- **开发团队**：飞流智能科技研发中心
- **客户方**：环球出海科技有限公司
- **技术支持**：架构组 & 智能体工程团队
