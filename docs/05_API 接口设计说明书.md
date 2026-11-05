# doc 4 API 接口设计说明书

> 项目名称：AgenticCommerce（自主智能体电商）
> 版本：v1\.0
> 编制日期：2026\-09\-23
> 编制方：飞流智能科技
> 客户：环球出海科技有限公司
> 技术栈：Python 3\.12 \+ FastAPI \+ LangChain 1\.3\.7 \+ LangGraph 1\.2\.4 \+ PostgreSQL 16 \+ pgvector \+ Redis
> 
> 

---

# 引言

## 1\.1 文档目的

本文档定义 AgenticCommerce 平台对外提供的所有 HTTP API 与 WebSocket 接口，作为前端开发、后端开发、测试工程师、第三方集成方的共同契约。文档覆盖认证、模型厂商、知识库、SKU、批次、任务、文案、素材、合规报告、打包下载、审计日志、刊登（二期）以及任务实时追踪 WebSocket 协议。

本文档面向：

- 前端工程师：按接口字段与响应格式开发页面；

- 后端工程师：按接口契约实现路由与服务；

- 测试工程师：按请求/响应示例编写用例；

- 运维工程师：按限流、幂等、鉴权规则配置网关。

## 1\.2 设计依据

- 《01\_客户需求纪要\.md》

- 《02\-需求规格说明书\.md》v1\.2

- 《系统架构设计\.md》v1\.0

- 《数据库设计\.md》v1\.2

---

# 接口规范

## 2\.1 接口前缀与版本

所有 HTTP 接口统一前缀 `/api/v1`。版本演进策略：

- `/api/v1`：一期工程，覆盖认证、厂商、知识库、SKU、任务、素材、合规、审计；

- `/api/v2`：二期工程，覆盖多平台一键刊登；如需破坏性变更，新增版本而非修改 v1。

WebSocket 接口同样带版本前缀：`/api/v1/ws/tasks/{task_id}`。

## 2\.2 请求方法语义
| 方法 | 语义 | 使用场景 |
| :--- | :--- | :--- |
| GET | 查询资源 | 列表、详情、导出 |
| POST | 创建资源或执行动作 | 创建、测试连接、重试、发布 |
| PUT | 全量更新资源 | 更新 SKU、更新厂商 |
| PATCH | 部分更新资源（本项目暂不使用，统一用 PUT） | — |
| DELETE | 删除资源 | 删除文档、删除 SKU |

## 2\.3 请求头规范
| Header | 必填 | 说明 |
| :--- | :--- | :--- |
| Authorization | 是 | Bearer <access_token> |
| Content-Type | 是 | application/json，文件上传用 multipart/form-data |
| X-Request-ID | 否 | 客户端生成的请求 ID，用于追踪；不传由服务端生成 |
| Idempotency-Key | 否 | 写接口幂等键，UUID 格式 |
| Accept-Language | 否 | 语言偏好，默认 zh-CN |
| X-Client-Version | 否 | 客户端版本，如 web-1.0.0 |

## 2\.4 响应格式规范

所有 HTTP 响应统一为 JSON：

json

\{  "code": 200,  "data": \{\},  "message": "成功"\}

- `code`：业务状态码，与 HTTP 状态码一致；

- `data`：业务数据，可为对象、数组、分页对象；无数据时为 `null`；

- `message`：描述信息，成功为“成功”，失败为错误描述。

## 2\.5 时间与字段命名

- 时间格式：ISO 8601 带时区，如 `2026-09-23T10:00:00+08:00`；

- 字段命名：小写 snake\_case，如 `tenant_id`、`create_time`；

- ID 格式：32 位无连字符 UUID，如 `a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6`；

- 布尔值：使用 `0` / `1`（smallint）或 `true` / `false`，本项目统一用 `0` / `1`。

## 2\.6 空值处理

- 可选字段无值时返回 `null`，不返回空字符串；

- 数组字段无值时返回 `[]`，不返回 `null`；

- 对象字段无值时返回 `{}`，不返回 `null`。

---

# 统一响应格式

## 3\.1 成功响应

```JSON
{
  "code": 200,
  "data": {
    "id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "name": "无线蓝牙耳机 Pro Max",
    "status": "active"
  },
  "message": "成功"
}
```

## 3\.2 分页响应

```JSON
{
  "code": 200,
  "data": {
    "total": 128,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "sku_code": "SKU-2026-001",
        "name": "无线蓝牙耳机 Pro Max",
        "platform": "amazon",
        "status": "active"
      }
    ]
  },
  "message": "成功"
}
```

## 3\.3 错误响应

```JSON
{
  "code": 400,
  "data": null,
  "message": "请求参数错误：sku_code 不能为空"
}
```

---

# 错误码规范
| code | message | 说明 | 触发场景 |
| :--- | :--- | :--- | :--- |
| 200 | 成功 | 请求成功 | 正常业务 |
| 400 | 参数错误 | 请求参数缺失或格式错误 | 缺必填字段、类型错误 |
| 401 | 未认证 | JWT 缺失或过期 | Token 无效 |
| 403 | 无权限 | 角色权限不足或跨租户访问 | 运营访问审计日志 |
| 404 | 资源不存在 | 请求的资源不存在 | 任务 ID 不存在 |
| 409 | 资源冲突 | 唯一约束冲突 | SKU 编码重复 |
| 413 | 请求体过大 | 超过 Body 限制 | 上传文件 > 20MB |
| 422 | 参数校验失败 | Pydantic 校验失败 | 邮箱格式错误 |
| 429 | 限流/配额超限 | 触发限流或配额 | 超 600 次/分钟 |
| 500 | 服务端错误 | 未捕获异常 | 内部错误 |
| 503 | 服务不可用 | 依赖服务不可用 | 数据库宕机 |

---

# 认证与授权

## 5\.1 JWT 结构

Access Token 采用 HS256 签名，Payload 示例：

```JSON
{
  "sub": "00000000000000000000000000000002",
  "tenant_id": "00000000000000000000000000000001",
  "user_name": "系统管理员",
  "role": "tenant_admin",
  "exp": 1758614400,
  "iat": 1758610800,
  "jti": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"
}
```

字段说明：
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| sub | string | 用户 ID (32 位 UUID) |
| tenant_id | string | 租户 ID |
| user_name | string | 用户姓名 |
| role | string | 角色：tenant_admin / operator / designer / auditor |
| exp | int | 过期时间戳 |
| iat | int | 签发时间戳 |
| jti | string | Token 唯一 ID |

## 5\.2 Token 有效期与刷新
| Token | 有效期 | 说明 |
| :--- | :--- | :--- |
| access_token | 1 小时 | 用于业务请求 |
| refresh_token | 7 天 | 用于刷新 access_token |

刷新流程：

1. access\_token 过期 → 返回 401；

2. 客户端用 refresh\_token 调用 `POST /api/v1/auth/refresh`；

3. 服务端校验 refresh\_token → 签发新的 access\_token；

4. refresh\_token 过期 → 重新登录。

## 5\.3 角色权限矩阵
| 资源 | tenant_admin | operator | designer | auditor |
| :--- | :--- | :--- | :--- | :--- |
| 用户管理 | CRUD | R | R | R |
| 模型厂商 | CRUD | R | R | R |
| 知识库 | CRUD | R | R | R |
| SKU | CRUD | CRUD | R | R |
| 批次 | CRUD | CRUD | R | R |
| 任务 | CRUD | CRUD | R | R |
| 文案 | CRUD | CRUD | CRUD | R |
| 素材 | CRUD | CRUD | CRUD | R |
| 合规报告 | R | R | R | R |
| 打包下载 | CRUD | CRUD | R | R |
| 审计日志 | R | - | - | R |
| 刊登（二期） | CRUD | CRUD | - | R |

---

# 多租户隔离

- 客户端不需要传 `tenant_id`，服务端从 JWT 的 `tenant_id` 声明解析；

- 所有查询自动附加 `tenant_id` 过滤条件；

- 跨租户访问资源时返回 403；

- WebSocket 连接时校验 JWT，禁止跨租户订阅。

示例：运营 A 属于租户 T1，尝试访问租户 T2 的任务：

```JSON
{
  "code": 403,
  "data": null,
  "message": "无权限访问该资源"
}
```

---

# 分页规范

请求参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| page | int | 否 | 1 | 页码，从 1 开始 |
| size | int | 否 | 10 | 每页条数，最大 100 |

响应字段：
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| total | int | 总条数 |
| page | int | 当前页码 |
| size | int | 每页条数 |
| items | array | 数据列表 |

示例：

```Bash
GET /api/v1/skus?page=2&size=20
```

---

# 幂等规范

- 写接口（POST / PUT）支持 `Idempotency-Key` 请求头；

- Key 为 UUID 格式，客户端生成；

- 服务端用 Redis 缓存 Key 与首次响应，TTL 24 小时；

- 相同 Key 重复请求 → 返回首次响应，不重复执行业务；

- 未传 Key → 不启用幂等。

示例：

```Bash
POST /api/v1/tasks
Idempotency-Key: 7f3e9c2b4a5d6e8f1a2b3c4d5e6f7a8b
```

---

# 限流规范
| 接口类别 | 限流阈值 | 说明 |
| :--- | :--- | :--- |
| 通用接口 | 600 次/分钟 | 按租户维度 |
| 任务创建类 | 60 次/分钟 | POST /api/v1/tasks、POST /api/v1/batches |
| 登录接口 | 10 次/分钟 | 按 IP 维度 |
| 文件上传 | 30 次/分钟 | 按租户维度 |

超限返回：

```JSON
{
  "code": 429,
  "data": null,
  "message": "请求过于频繁，请稍后重试"
}
```

响应头带 `Retry-After`。

---

# 文件上传规范

- 请求方式：`multipart/form-data`

- 支持格式：pdf、txt、md、docx、csv、xlsx

- 最大大小：20MB

- 字段名统一为 `file`

- 服务端校验文件类型与大小，不通过返回 413

示例：

```Bash
curl -X POST /api/v1/knowledge-docs \
  -H "Authorization: Bearer <token>" \
  -F "file=@brand-guidelines.pdf" \
  -F "category=brand_visual" \
  -F "doc_type=brand_guide"
```



---

# WebSocket 协议

## 11\.1 设计原则

- 连接按用户维度建立：每个用户浏览器只建立 1 条 WebSocket 连接；

- 订阅按任务维度管理：一条连接可订阅多个任务，一个任务可被多条连接订阅；

- 切换任务不重连：通过订阅 / 取消订阅消息动态管理；

- 租户隔离：连接时校验 JWT，禁止订阅其他租户的任务。

## 11\.2 连接地址

```Plain Text
ws://localhost:8002/api/v1/ws?token=<access_token>
wss://api.agentic-commerce.com/api/v1/ws?token=<access_token>
```

注意：连接地址中不带 `task_id`，只带 `token`。

## 11\.3 连接与鉴权

1. 客户端携带 JWT 建立连接；

2. 服务端校验 JWT，解析 `tenant_id`、`user_id`；

3. 校验通过 → 接受连接；失败 → 返回 401 并关闭。

## 11\.4 订阅协议

### 11\.4\.1 订阅任务

客户端发送：

```JSON
{
  "action": "subscribe",
  "task_ids": ["f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"]
}
```

服务端响应：

```JSON
{
  "action": "subscribe_ack",
  "task_ids": ["f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"],
  "status": "ok"
}
```

### 11\.4\.2 取消订阅

```JSON
{
  "action": "unsubscribe",
  "task_ids": ["f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"]
}
```

### 11\.4\.3 订阅批次下所有任务

```JSON
{
  "action": "subscribe_batch",
  "batch_id": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4"
}
```

### 11\.4\.4 心跳

```JSON
{ "action": "ping" }
```

服务端响应：

```JSON
{ "action": "pong", "timestamp": "2026-09-23T10:00:00+08:00" }
```

## 11\.5 事件推送格式

服务端推送事件统一格式：

```JSON
{
  "event_type": "node_start",
  "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
  "node_name": "orchestrator",
  "status": "running",
  "sequence": 1,
  "timestamp": "2026-09-23T10:00:00+08:00",
  "data": {}
}
```

事件类型：
| event_type | 触发时机 | data 内容 |
| :--- | :--- | :--- |
| node_start | 节点开始执行 | {node_name, input_summary} |
| node_complete | 节点执行完成 | {node_name, elapsed_ms, token_usage, cost, output_summary} |
| node_error | 节点执行失败 | {node_name, error} |
| task_complete | 任务整体完成 | {task_id, status, total_cost, total_tokens} |
| task_error | 任务整体失败 | {task_id, error} |
| task_cancelled | 任务被取消 | {task_id} |

## 11\.6 订阅管理

### 11\.6\.1 服务端数据结构

```Plain Text
task_id → Set<WebSocket>
batch_id → Set<WebSocket>
WebSocket → Set<task_id>
```

- 任务产生事件时，查 `task_id → Set<WebSocket>`，逐个推送；

- 连接关闭时，从所有订阅集合中移除。

### 11\.6\.2 订阅上限

- 单连接订阅任务数上限：50；

- 单任务订阅连接数上限：200；

- 超过上限返回错误：

```JSON
{
  "action": "subscribe_nack",
  "task_ids": ["f1a2b3c4..."],
  "message": "订阅任务数超过上限 50"
}
```

### 11\.6\.3 权限校验

订阅时校验：

- 任务属于当前用户的租户；

- 用户角色有权限查看该任务；

- 校验失败 → 返回 `subscribe_nack`，不建立订阅。

## 11\.7 断线重连与事件补发

### 11\.7\.1 重连

客户端断线后自动重连：

```Plain Text
ws://localhost:8002/api/v1/ws?token=<token>&resume_token=<last_sequence_map>
```

`resume_token` 是客户端上次断开时保存的 `{task_id: last_sequence}` 映射，Base64 编码。

### 11\.7\.2 事件补发

服务端根据 `resume_token`，从 `last_sequence + 1` 开始补发未消费事件。

### 11\.7\.3 事件缓存
| 项 | 值 |
| :--- | :--- |
| 存储 | Redis |
| Key 格式 | ws:events:{task_id} |
| Value | 事件列表（ZSET，按 sequence 排序） |
| TTL | 1 小时 |
| 容量 | 单任务最多保留最近 1000 条事件 |

超过 1 小时的事件不再补发，客户端需重新拉取任务详情。

### 11\.7\.4 重连失败

如果 `resume_token` 过期或无效：

```JSON
{
  "action": "resume_failed",
  "message": "resume_token 无效或已过期，请重新拉取任务详情"
}
```

客户端应调用 `GET /api/v1/tasks/{id}` 与 `GET /api/v1/tasks/{id}/nodes` 恢复完整状态。

## 11\.8 完整交互示例

```JavaScript
// 1. 建立连接
const ws = new WebSocket(`ws://localhost:8002/api/v1/ws?token=${token}`);

ws.onopen = () => {
  // 2. 订阅任务
  ws.send(JSON.stringify({
    action: "subscribe",
    task_ids: ["f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6"]
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // 3. 处理订阅确认
  if (data.action === "subscribe_ack") {
    console.log("订阅成功:", data.task_ids);
    return;
  }

  // 4. 处理事件
  if (data.event_type) {
    console.log("事件:", data.event_type, data.node_name, data.status);
    // 根据事件类型更新前端 DAG 与详情面板
  }
};

// 5. 心跳
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ action: "ping" }));
  }
}, 30000);

// 6. 切换任务
function switchTask(newTaskId, oldTaskId) {
  ws.send(JSON.stringify({ action: "unsubscribe", task_ids: [oldTaskId] }));
  ws.send(JSON.stringify({ action: "subscribe", task_ids: [newTaskId] }));
}

// 7. 断线重连
ws.onclose = () => {
  setTimeout(() => reconnect(), 3000);
};
```

---

# 接口详细设计

## 12\.1 认证与用户

### 12\.1\.1 登录

接口路径：`POST /api/v1/auth/login`
功能说明：邮箱 \+ 密码登录，返回 JWT
权限要求：公开（无需认证）

请求头：
| Header | 必填 | 说明 |
| :--- | :--- | :--- |
| Content-Type | 是 | application/json |

请求体：

```JSON
{
  "email": "admin@agentic-commerce.local",
  "password": "admin123"
}
```

请求体字段说明：
| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| email | string | 是 | 登录邮箱 |
| password | string | 是 | 登录密码 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600,
    "user": {
      "id": "00000000000000000000000000000002",
      "tenant_id": "00000000000000000000000000000001",
      "name": "系统管理员",
      "email": "admin@agentic-commerce.local",
      "role": "tenant_admin"
    }
  },
  "message": "登录成功"
}
```

响应字段说明：
| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| access_token | string | 访问令牌 |
| refresh_token | string | 刷新令牌 |
| expires_in | int | access_token 有效期（秒） |
| user | object | 用户信息 |

错误码：
| code | message | 说明 |
| :--- | :--- | :--- |
| 400 | 参数错误 | 邮箱或密码为空 |
| 401 | 用户名或密码错误 | 凭证错误 |
| 429 | 登录过于频繁 | 超过 10 次/分钟 |

业务规则：

- 连续登录失败 5 次，账号锁定 30 分钟；

- 登录成功后 `login_fail_count` 清零。

幂等性：不支持

限流：10 次/分钟（按 IP）

示例请求：

```Bash
curl -X POST http://localhost:8002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@agentic-commerce.local","password":"admin123"}'
```

---

### 12\.1\.2 登出

接口路径：`POST /api/v1/auth/logout`
功能说明：登出，服务端将当前 Token 加入黑名单
权限要求：登录用户

请求头：
| Header | 必填 | 说明 |
| :--- | :--- | :--- |
| Authorization | 是 | Bearer Token |

响应示例：

```JSON
{
  "code": 200,
  "data": null,
  "message": "登出成功"
}
```

业务规则：Token 加入 Redis 黑名单，TTL 等于 Token 剩余有效期。

幂等性：支持

限流：默认 600 次/分钟

---

### 12\.1\.3 刷新 Token

接口路径：`POST /api/v1/auth/refresh`
功能说明：用 refresh\_token 换取新的 access\_token
权限要求：公开

请求体：

```JSON
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
  },
  "message": "刷新成功"
}
```

错误码：
| code | message | 说明 |
| :--- | :--- | :--- |
| 401 | refresh_token 无效或已过期 | 需重新登录 |

限流：默认 600 次/分钟

---

### 12\.1\.4 当前用户信息

接口路径：`GET /api/v1/auth/me`
功能说明：获取当前登录用户信息
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "00000000000000000000000000000002",
    "tenant_id": "00000000000000000000000000000001",
    "name": "系统管理员",
    "email": "admin@agentic-commerce.local",
    "role": "tenant_admin",
    "status": "active",
    "last_login_time": "2026-09-23T10:00:00+08:00"
  },
  "message": "成功"
}
```

---

### 12\.1\.5 用户列表

接口路径：`GET /api/v1/users`
功能说明：查询当前租户下的用户列表
权限要求：租户管理员、运营（只读）

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |
| role | string | 否 | — | 角色筛选 |
| status | string | 否 | — | 状态筛选 |
| keyword | string | 否 | — | 姓名/邮箱模糊搜索 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 25,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "00000000000000000000000000000002",
        "name": "系统管理员",
        "email": "admin@agentic-commerce.local",
        "role": "tenant_admin",
        "status": "active",
        "last_login_time": "2026-09-23T10:00:00+08:00",
        "create_time": "2026-09-01T09:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.1\.6 创建用户

接口路径：`POST /api/v1/users`
功能说明：租户管理员创建子账号
权限要求：租户管理员

请求体：

```JSON
{
  "name": "李雪",
  "email": "lixue@example.com",
  "password": "Initial@123",
  "role": "operator"
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "tenant_id": "00000000000000000000000000000001",
    "name": "李雪",
    "email": "lixue@example.com",
    "role": "operator",
    "status": "active",
    "create_time": "2026-09-23T10:00:00+08:00"
  },
  "message": "创建成功"
}
```

错误码：
| code | message | 说明 |
| :--- | :--- | :--- |
| 409 | 邮箱已存在 | 同租户下邮箱唯一 |

幂等性：支持 Idempotency\-Key

---

### 12\.1\.7 更新用户

接口路径：`PUT /api/v1/users/{id}`
功能说明：更新用户姓名、角色
权限要求：租户管理员

请求体：

```JSON
{
  "name": "李雪（运营总监）",
  "role": "operator"
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "name": "李雪（运营总监）",
    "role": "operator",
    "update_time": "2026-09-23T10:05:00+08:00"
  },
  "message": "更新成功"
}
```

---

### 12\.1\.8 停用/启用用户

接口路径：`POST /api/v1/users/{id}/disable`
接口路径：`POST /api/v1/users/{id}/enable`
功能说明：停用或启用用户账号
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "status": "disabled"
  },
  "message": "已停用"
}
```

---

## 12\.2 模型厂商

### 12\.2\.1 厂商列表

接口路径：`GET /api/v1/providers`
功能说明：查询租户配置的模型厂商
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| type | string | 否 | — | 厂商类型: llm/image/video |
| status | string | 否 | — | active/inactive |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 5,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
        "type": "llm",
        "name": "通义千问",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-plus",
        "api_key_masked": "sk-****1234",
        "is_default": 1,
        "status": "active",
        "create_time": "2026-09-01T09:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```



---

### 12\.2\.2 创建厂商

接口路径：`POST /api/v1/providers`
功能说明：新增模型厂商配置
权限要求：租户管理员

请求体：

```JSON
{
  "type": "llm",
  "name": "OpenAI",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-proj-xxxxxxxxxxxxxxxx",
  "model_name": "gpt-4o-mini",
  "is_default": 0
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "type": "llm",
    "name": "OpenAI",
    "api_key_masked": "sk-****xxxx",
    "status": "active",
    "create_time": "2026-09-23T10:00:00+08:00"
  },
  "message": "创建成功"
}
```

业务规则：

- `api_key` 服务端加密存储；

- 同租户同类型下，最多一个 `is_default=1`。

---

### 12\.2\.3 厂商详情

接口路径：`GET /api/v1/providers/{id}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "type": "llm",
    "name": "通义千问",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "model_name": "qwen-plus",
    "api_key_masked": "sk-****1234",
    "is_default": 1,
    "status": "active",
    "extra_config": {},
    "create_time": "2026-09-01T09:00:00+08:00"
  },
  "message": "成功"
}
```

---

### 12\.2\.4 更新厂商

接口路径：`PUT /api/v1/providers/{id}`
权限要求：租户管理员

请求体：

```JSON
{
  "name": "通义千问（qwen-max）",
  "model_name": "qwen-max",
  "api_key": "sk-new-key-xxxxxxxx"
}
```

---

### 12\.2\.5 删除厂商

接口路径：`DELETE /api/v1/providers/{id}`
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": null,
  "message": "删除成功"
}
```

---

### 12\.2\.6 测试连接

接口路径：`POST /api/v1/providers/{id}/test`
功能说明：测试厂商 API Key 是否有效
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "success": true,
    "latency_ms": 320,
    "message": "连接成功"
  },
  "message": "成功"
}
```

失败示例：

```JSON
{
  "code": 200,
  "data": {
    "success": false,
    "latency_ms": 210,
    "message": "API Key 无效（401）"
  },
  "message": "成功"
}
```

---

### 12\.2\.7 设为默认

接口路径：`POST /api/v1/providers/{id}/set-default`
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "is_default": 1
  },
  "message": "已设为默认"
}
```

业务规则：同租户同类型下，原默认厂商自动置为 0。

---

## 12\.3 知识库

### 12\.3\.1 文档列表

接口路径：`GET /api/v1/knowledge-docs`
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| category | string | 否 | — | 分类 |
| doc_type | string | 否 | — | 文档类型 |
| vector_status | string | 否 | — | 向量化状态 |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 12,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "category": "brand_visual",
        "doc_type": "brand_guide",
        "name": "品牌主视觉规范v2.pdf",
        "file_type": "pdf",
        "file_size": 2048000,
        "vector_status": "success",
        "chunk_count": 45,
        "create_time": "2026-09-20T14:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.3\.2 上传文档

接口路径：`POST /api/v1/knowledge-docs`
权限要求：租户管理员

请求方式：`multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| file | file | 是 | 文件 |
| category | string | 是 | 分类 |
| doc_type | string | 是 | 文档类型 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
    "name": "广告法违禁词表.xlsx",
    "category": "compliance",
    "doc_type": "compliance_rule",
    "vector_status": "processing",
    "create_time": "2026-09-23T10:00:00+08:00"
  },
  "message": "上传成功，正在向量化"
}
```

---

### 12\.3\.3 文档详情

接口路径：`GET /api/v1/knowledge-docs/{id}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "tenant_id": "00000000000000000000000000000001",
    "category": "brand_visual",
    "doc_type": "brand_guide",
    "name": "品牌主视觉规范v2.pdf",
    "file_type": "pdf",
    "file_url": "minio://knowledge/e5f6a7b8...pdf",
    "file_size": 2048000,
    "vector_status": "success",
    "chunk_count": 45,
    "metadata": {},
    "create_time": "2026-09-20T14:00:00+08:00"
  },
  "message": "成功"
}
```

---

### 12\.3\.4 删除文档

接口路径：`DELETE /api/v1/knowledge-docs/{id}`
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": null,
  "message": "删除成功"
}
```

业务规则：删除后立即停止参与检索。

---

### 12\.3\.5 重新向量化

接口路径：`POST /api/v1/knowledge-docs/{id}/revectorize`
权限要求：租户管理员

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
    "vector_status": "processing"
  },
  "message": "已触发重新向量化"
}
```

---

### 12\.3\.6 查看分块

接口路径：`GET /api/v1/knowledge-docs/{id}/chunks`
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 20 | 每页条数 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 45,
    "page": 1,
    "size": 20,
    "items": [
      {
        "id": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "doc_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "chunk_index": 0,
        "content": "品牌主色调为 #2563EB，辅助色为 #1D4ED8...",
        "doc_type": "brand_guide",
        "metadata": {"page": 1}
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.3\.7 RAG 检索

接口路径：`POST /api/v1/knowledge/search`
权限要求：登录用户

请求体：

```JSON
{
  "query": "品牌调性 合规要求",
  "doc_type": ["brand_guide", "compliance_rule"],
  "top_k": 5,
  "similarity_threshold": 0.5,
  "use_reranker": true
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "query": "品牌调性 合规要求",
    "chunks": [
      {
        "chunk_id": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
        "doc_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
        "doc_name": "品牌主视觉规范v2.pdf",
        "doc_type": "brand_guide",
        "content": "品牌主色调为 #2563EB...",
        "score": 0.87
      }
    ],
    "elapsed_ms": 180
  },
  "message": "成功"
}
```

---

## 12\.4 SKU 与商品

### 12\.4\.1 SKU 列表

接口路径：`GET /api/v1/skus`
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |
| platform | string | 否 | — | 平台筛选 |
| status | string | 否 | — | 状态筛选 |
| keyword | string | 否 | — | SKU 编码/名称模糊搜索 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 128,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "sku_code": "SKU-2026-001",
        "name": "无线蓝牙耳机 Pro Max",
        "platform": "amazon",
        "category": "消费电子",
        "status": "active",
        "create_time": "2026-09-20T10:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.4\.2 创建 SKU

接口路径：`POST /api/v1/skus`
权限要求：运营及以上

请求体：

```JSON
{
  "sku_code": "SKU-2026-001",
  "name": "无线蓝牙耳机 Pro Max",
  "platform": "amazon",
  "category": "消费电子",
  "description": "主动降噪，续航 40 小时",
  "metadata": {"brand": "SoundX", "color": "black"}
}
```

错误码：
| code | message | 说明 |
| :--- | :--- | :--- |
| 409 | SKU 编码已存在 | 租户内唯一 |

幂等性：支持 Idempotency\-Key

---

### 12\.4\.3 SKU 详情

接口路径：`GET /api/v1/skus/{id}`
权限要求：登录用户

---

### 12\.4\.4 更新 SKU

接口路径：`PUT /api/v1/skus/{id}`
权限要求：运营及以上

---

### 12\.4\.5 删除 SKU

接口路径：`DELETE /api/v1/skus/{id}`
权限要求：运营及以上

---

### 12\.4\.6 批量导入 SKU

接口路径：`POST /api/v1/skus/import`
权限要求：运营及以上
请求方式：`multipart/form-data`
| 字段 | 类型 | 必填 | 说明 |
| :--- | :--- | :--- | :--- |
| file | file | 是 | CSV/Excel 文件 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "job_id": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    "total": 50,
    "status": "processing"
  },
  "message": "导入任务已创建"
}
```

---

### 12\.4\.7 下载导入模板

接口路径：`GET /api/v1/skus/import/template`
权限要求：登录用户
响应：文件流（`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`）

---

### 12\.4\.8 查看导入结果

接口路径：`GET /api/v1/skus/import/{job_id}/result`
权限要求：运营及以上

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "job_id": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    "total": 50,
    "success": 47,
    "failed": 3,
    "errors": [
      {"row": 5, "sku_code": "SKU-2026-005", "error": "SKU 编码重复"},
      {"row": 12, "sku_code": "SKU-2026-012", "error": "商品名称为空"},
      {"row": 30, "sku_code": "SKU-2026-030", "error": "平台字段不合法"}
    ]
  },
  "message": "成功"
}
```

---

## 12\.5 批次与任务

### 12\.5\.1 批次列表

接口路径：`GET /api/v1/batches`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 8,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        "name": "黑五预热批次-001",
        "sku_count": 30,
        "status": "running",
        "success_count": 12,
        "failed_count": 1,
        "create_time": "2026-09-23T10:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.5\.2 创建批次

接口路径：`POST /api/v1/batches`
权限要求：运营及以上
限流：60 次/分钟

请求体：

```JSON
{
  "name": "黑五预热批次-001",
  "sku_ids": [
    "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"
  ],
  "config": {
    "content_types": ["copy", "image", "video"],
    "media_type": "mixed",
    "style": "科技感、现代简约",
    "platform": "amazon",
    "language": "zh",
    "llm_provider_id": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
    "image_provider_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
    "video_provider_id": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
  }
}
```

幂等性：支持 Idempotency\-Key

---

### 12\.5\.3 批次详情

接口路径：`GET /api/v1/batches/{id}`
权限要求：登录用户

---

### 12\.5\.4 批次下的任务列表

接口路径：`GET /api/v1/batches/{id}/tasks`
权限要求：登录用户

---

### 12\.5\.5 取消批次

接口路径：`DELETE /api/v1/batches/{id}`
权限要求：运营及以上
业务规则：取消批次下所有未完成的任务。

---

### 12\.5\.6 任务列表

接口路径：`GET /api/v1/tasks`
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |
| batch_id | string | 否 | — | 批次筛选 |
| sku_id | string | 否 | — | SKU 筛选 |
| status | string | 否 | — | 状态筛选 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 30,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        "batch_id": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "sku_code": "SKU-2026-001",
        "status": "running",
        "progress": 62,
        "current_node": "visual_designer",
        "retry_count": 0,
        "started_at": "2026-09-23T10:00:05+08:00",
        "create_time": "2026-09-23T10:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.5\.7 创建单个任务

接口路径：`POST /api/v1/tasks`
权限要求：运营及以上
限流：60 次/分钟

请求体：

```JSON
{
  "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
  "config": {
    "content_types": ["copy", "image"],
    "media_type": "image",
    "style": "科技感、现代简约",
    "platform": "amazon",
    "language": "zh"
  }
}
```

---

### 12\.5\.8 任务详情

接口路径：`GET /api/v1/tasks/{id}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "batch_id": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
    "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "sku_code": "SKU-2026-001",
    "status": "running",
    "progress": 62,
    "current_node": "visual_designer",
    "retry_count": 0,
    "max_retries": 2,
    "trace_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "total_token_usage": {"input": 3200, "output": 1800, "cache": 0},
    "total_cost": 0.0234,
    "started_at": "2026-09-23T10:00:05+08:00",
    "create_time": "2026-09-23T10:00:00+08:00",
    "config": {
      "content_types": ["copy", "image", "video"],
      "media_type": "mixed",
      "style": "科技感、现代简约",
      "platform": "amazon",
      "language": "zh"
    }
  },
  "message": "成功"
}
```

---

### 12\.5\.9 重试任务

接口路径：`POST /api/v1/tasks/{id}/retry`
权限要求：运营及以上

业务规则：

- 仅 `failed` / `cancelled` 状态可重试；

- 重试后 `retry_count +1`，若超过 `max_retries` 则拒绝。

---

### 12\.5\.10 取消任务

接口路径：`POST /api/v1/tasks/{id}/cancel`
权限要求：运营及以上

---

### 12\.5\.11 任务执行链路

接口路径：`GET /api/v1/tasks/{id}/trace`
功能说明：返回 7 个 Agent 节点的执行链路摘要
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "trace_id": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
    "nodes": [
      {"node_name": "orchestrator", "status": "success", "elapsed_ms": 1200},
      {"node_name": "requirement_analyzer", "status": "success", "elapsed_ms": 3400},
      {"node_name": "creative_planner", "status": "success", "elapsed_ms": 2800},
      {"node_name": "visual_designer", "status": "running", "elapsed_ms": 1800},
      {"node_name": "image_generator", "status": "waiting", "elapsed_ms": 0},
      {"node_name": "video_generator", "status": "waiting", "elapsed_ms": 0},
      {"node_name": "quality_reviewer", "status": "waiting", "elapsed_ms": 0}
    ]
  },
  "message": "成功"
}
```

---

### 12\.5\.12 节点执行记录列表

接口路径：`GET /api/v1/tasks/{id}/nodes`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 7,
    "page": 1,
    "size": 20,
    "items": [
      {
        "id": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
        "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        "node_name": "orchestrator",
        "status": "success",
        "elapsed_ms": 1200,
        "token_usage": {"input": 320, "output": 180, "cache": 0},
        "cost": 0.005,
        "upstream": null,
        "downstream": "requirement_analyzer",
        "create_time": "2026-09-23T10:00:05+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.5\.13 单节点详情

接口路径：`GET /api/v1/tasks/{id}/nodes/{node_name}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
    "node_name": "orchestrator",
    "status": "success",
    "input": {"product_info": {"sku_code": "SKU-2026-001"}},
    "output": {"task_type": "mixed", "style_direction": "科技感"},
    "prompt_system": "你是一个跨境电商视觉生产的编排调度专家...",
    "prompt_human": "商品信息: {...}\n生成配置: {...}",
    "elapsed_ms": 1200,
    "token_usage": {"input": 320, "output": 180, "cache": 0},
    "cost": 0.005,
    "error": null,
    "upstream": null,
    "downstream": "requirement_analyzer"
  },
  "message": "成功"
}
```

---

## 12\.6 文案与素材

### 12\.6\.1 文案详情

接口路径：`GET /api/v1/copies/{id}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
    "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "language": "zh",
    "title": "SoundX 无线蓝牙耳机 Pro Max｜主动降噪｜40小时续航",
    "bullets": [
      "【主动降噪】-42dB 深度降噪，通勤地铁瞬间安静",
      "【超长续航】单次充电 40 小时，出差一周不用带充电器",
      "【HiFi 音质】10mm 动圈单元，低音澎湃人声清澈",
      "【蓝牙 5.3】双设备连接，游戏延迟低至 60ms",
      "【舒适佩戴】入耳式人体工学设计，久戴不痛"
    ],
    "description": "SoundX Pro Max 采用全新主动降噪芯片...",
    "keywords": ["蓝牙耳机", "降噪耳机", "无线耳机", "长续航"],
    "status": "draft",
    "create_time": "2026-09-23T10:02:00+08:00"
  },
  "message": "成功"
}
```

---

### 12\.6\.2 在线编辑文案

接口路径：`PUT /api/v1/copies/{id}`
权限要求：运营、设计·内容

请求体：

```JSON
{
  "title": "SoundX 无线蓝牙耳机 Pro Max｜降噪｜40h续航",
  "bullets": ["...", "..."],
  "description": "...",
  "keywords": ["蓝牙耳机", "降噪耳机"]
}
```

---

### 12\.6\.3 资产列表

接口路径：`GET /api/v1/assets`
权限要求：登录用户

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| task_id | string | 否 | — | 任务筛选 |
| sku_id | string | 否 | — | SKU 筛选 |
| type | string | 否 | — | image/video/storyboard/copy_file |
| status | string | 否 | — | pending/approved/rejected/failed |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 60,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
        "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
        "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "type": "image",
        "sub_type": "main",
        "url": "minio://assets/main_001.png",
        "meta": {"width": 1024, "height": 1024, "prompt": "..."},
        "status": "pending",
        "is_mock": 0,
        "create_time": "2026-09-23T10:03:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.6\.4 资产详情

接口路径：`GET /api/v1/assets/{id}`
权限要求：登录用户

---

### 12\.6\.5 单素材重新生成

接口路径：`POST /api/v1/assets/{id}/regenerate`
权限要求：运营、设计·内容

请求体：

```JSON
{
  "style_override": "奢华",
  "provider_id": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "new_asset_id": "e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
    "status": "pending"
  },
  "message": "已触发重新生成"
}
```

---

### 12\.6\.6 删除资产

接口路径：`DELETE /api/v1/assets/{id}`
权限要求：运营及以上

---

## 12\.7 合规报告

### 12\.7\.1 合规报告详情

接口路径：`GET /api/v1/compliance-reports/{id}`
权限要求：登录用户

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "id": "f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9",
    "task_id": "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "sku_id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
    "score": 85.5,
    "dimensions": {
      "technical_quality": {"score": 28, "issues": []},
      "content_relevance": {"score": 26, "issues": []},
      "visual_aesthetics": {"score": 17, "issues": ["构图略拥挤"]},
      "compliance": {"score": 14, "issues": ["标题含极限词'最'"]}
    },
    "violations": [
      {"type": "forbidden_word", "target": "title", "word": "最", "suggestion": "改为'非常'"}
    ],
    "passed": 0,
    "suggestions": ["请修改标题中的极限词"],
    "status": "failed",
    "create_time": "2026-09-23T10:05:00+08:00"
  },
  "message": "成功"
}
```

---

### 12\.7\.2 任务下的合规报告

接口路径：`GET /api/v1/tasks/{task_id}/compliance`
权限要求：登录用户

---

## 12\.8 打包下载

### 12\.8\.1 创建打包任务

接口路径：`POST /api/v1/packages`
权限要求：运营及以上

请求体：

```JSON
{
  "task_ids": [
    "f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6",
    "a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7"
  ],
  "include_copy": true,
  "include_image": true,
  "include_video": true,
  "include_storyboard": true
}
```

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "package_id": "a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
    "status": "processing"
  },
  "message": "打包任务已创建"
}
```

---

### 12\.8\.2 查询打包状态

接口路径：`GET /api/v1/packages/{id}`
权限要求：运营及以上

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "package_id": "a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
    "status": "completed",
    "download_url": "/api/v1/packages/a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0/download",
    "expires_at": "2026-09-23T11:00:00+08:00",
    "file_size": 15728640
  },
  "message": "成功"
}
```

---

### 12\.8\.3 下载打包文件

接口路径：`GET /api/v1/packages/{id}/download`
权限要求：运营及以上
响应：文件流（`application/zip`）

---

## 12\.9 审计日志

### 12\.9\.1 审计日志列表

接口路径：`GET /api/v1/audit-logs`
权限要求：租户管理员、只读审计

查询参数：
| 参数 | 类型 | 必填 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| user_id | string | 否 | — | 用户筛选 |
| action | string | 否 | — | 动作筛选 |
| start_time | string | 否 | — | 开始时间 |
| end_time | string | 否 | — | 结束时间 |
| page | int | 否 | 1 | 页码 |
| size | int | 否 | 10 | 每页条数 |

响应示例：

```JSON
{
  "code": 200,
  "data": {
    "total": 1520,
    "page": 1,
    "size": 10,
    "items": [
      {
        "id": "b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
        "user_id": "00000000000000000000000000000002",
        "user_name": "系统管理员",
        "action": "create_batch",
        "target_type": "batch",
        "target_id": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
        "ip_address": "192.168.1.100",
        "create_time": "2026-09-23T10:00:00+08:00"
      }
    ]
  },
  "message": "成功"
}
```

---

### 12\.9\.2 审计日志详情

接口路径：`GET /api/v1/audit-logs/{id}`
权限要求：租户管理员、只读审计

---

## 12\.10 刊登（二期）

### 12\.10\.1 刊登记录列表

接口路径：`GET /api/v1/listings`
权限要求：登录用户
说明：二期功能，一期返回空列表。

---

### 12\.10\.2 创建刊登

接口路径：`POST /api/v1/listings`
权限要求：运营及以上
说明：二期功能。

---

### 12\.10\.3 刊登详情

接口路径：`GET /api/v1/listings/{id}`
说明：二期功能。

---

### 12\.10\.4 重试刊登

接口路径：`POST /api/v1/listings/{id}/retry`
说明：二期功能。

---

## 12\.11 WebSocket

### 12\.11\.1 连接与订阅

**连接地址**：`ws://``localhost:8002/api/v1/ws?token=<access_token>`

**说明**：连接时携带 JWT，服务端校验租户归属。连接后通过 subscribe 消息订阅任务。详细协议见第 11 章。

---

# OpenAPI 文档
| 路径 | 说明 |
| :--- | :--- |
| /docs | Swagger UI，交互式 API 文档 |
| /redoc | ReDoc，可读式 API 文档 |
| /openapi.json | OpenAPI 3.0 规范 JSON |

本地访问：`http://localhost:8002/docs`

---

# 接口清单汇总
| 序号 | 模块 | 方法 | 路径 | 说明 | 权限 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | 认证 | POST | /api/v1/auth/login | 登录 | 公开 |
| 2 | 认证 | POST | /api/v1/auth/logout | 登出 | 登录用户 |
| 3 | 认证 | POST | /api/v1/auth/refresh | 刷新 Token | 公开 |
| 4 | 认证 | GET | /api/v1/auth/me | 当前用户 | 登录用户 |
| 5 | 用户 | GET | /api/v1/users | 用户列表 | 管理员/运营 |
| 6 | 用户 | POST | /api/v1/users | 创建用户 | 管理员 |
| 7 | 用户 | PUT | /api/v1/users/{id} | 更新用户 | 管理员 |
| 8 | 用户 | POST | /api/v1/users/{id}/disable | 停用用户 | 管理员 |
| 9 | 用户 | POST | /api/v1/users/{id}/enable | 启用用户 | 管理员 |
| 10 | 厂商 | GET | /api/v1/providers | 厂商列表 | 登录用户 |
| 11 | 厂商 | POST | /api/v1/providers | 创建厂商 | 管理员 |
| 12 | 厂商 | GET | /api/v1/providers/{id} | 厂商详情 | 登录用户 |
| 13 | 厂商 | PUT | /api/v1/providers/{id} | 更新厂商 | 管理员 |
| 14 | 厂商 | DELETE | /api/v1/providers/{id} | 删除厂商 | 管理员 |
| 15 | 厂商 | POST | /api/v1/providers/{id}/test | 测试连接 | 管理员 |
| 16 | 厂商 | POST | /api/v1/providers/{id}/set-default | 设为默认 | 管理员 |
| 17 | 知识库 | GET | /api/v1/knowledge-docs | 文档列表 | 登录用户 |
| 18 | 知识库 | POST | /api/v1/knowledge-docs | 上传文档 | 管理员 |
| 19 | 知识库 | GET | /api/v1/knowledge-docs/{id} | 文档详情 | 登录用户 |
| 20 | 知识库 | DELETE | /api/v1/knowledge-docs/{id} | 删除文档 | 管理员 |
| 21 | 知识库 | POST | /api/v1/knowledge-docs/{id}/revectorize | 重新向量化 | 管理员 |
| 22 | 知识库 | GET | /api/v1/knowledge-docs/{id}/chunks | 查看分块 | 登录用户 |
| 23 | 知识库 | POST | /api/v1/knowledge/search | RAG 检索 | 登录用户 |
| 24 | SKU | GET | /api/v1/skus | SKU 列表 | 登录用户 |
| 25 | SKU | POST | /api/v1/skus | 创建 SKU | 运营+ |
| 26 | SKU | GET | /api/v1/skus/{id} | SKU 详情 | 登录用户 |
| 27 | SKU | PUT | /api/v1/skus/{id} | 更新 SKU | 运营+ |
| 28 | SKU | DELETE | /api/v1/skus/{id} | 删除 SKU | 运营+ |
| 29 | SKU | POST | /api/v1/skus/import | 批量导入 | 运营+ |
| 30 | SKU | GET | /api/v1/skus/import/template | 下载模板 | 登录用户 |
| 31 | SKU | GET | /api/v1/skus/import/{job_id}/result | 导入结果 | 运营+ |
| 32 | 批次 | GET | /api/v1/batches | 批次列表 | 登录用户 |
| 33 | 批次 | POST | /api/v1/batches | 创建批次 | 运营+ |
| 34 | 批次 | GET | /api/v1/batches/{id} | 批次详情 | 登录用户 |
| 35 | 批次 | GET | /api/v1/batches/{id}/tasks | 批次任务列表 | 登录用户 |
| 36 | 批次 | DELETE | /api/v1/batches/{id} | 取消批次 | 运营+ |
| 37 | 任务 | GET | /api/v1/tasks | 任务列表 | 登录用户 |
| 38 | 任务 | POST | /api/v1/tasks | 创建任务 | 运营+ |
| 39 | 任务 | GET | /api/v1/tasks/{id} | 任务详情 | 登录用户 |
| 40 | 任务 | POST | /api/v1/tasks/{id}/retry | 重试任务 | 运营+ |
| 41 | 任务 | POST | /api/v1/tasks/{id}/cancel | 取消任务 | 运营+ |
| 42 | 任务 | GET | /api/v1/tasks/{id}/trace | 执行链路 | 登录用户 |
| 43 | 任务 | GET | /api/v1/tasks/{id}/nodes | 节点列表 | 登录用户 |
| 44 | 任务 | GET | /api/v1/tasks/{id}/nodes/{node_name} | 节点详情 | 登录用户 |
| 45 | 文案 | GET | /api/v1/copies/{id} | 文案详情 | 登录用户 |
| 46 | 文案 | PUT | /api/v1/copies/{id} | 编辑文案 | 运营/设计 |
| 47 | 素材 | GET | /api/v1/assets | 资产列表 | 登录用户 |
| 48 | 素材 | GET | /api/v1/assets/{id} | 资产详情 | 登录用户 |
| 49 | 素材 | POST | /api/v1/assets/{id}/regenerate | 重新生成 | 运营/设计 |
| 50 | 素材 | DELETE | /api/v1/assets/{id} | 删除资产 | 运营+ |
| 51 | 合规 | GET | /api/v1/compliance-reports/{id} | 合规报告 | 登录用户 |
| 52 | 合规 | GET | /api/v1/tasks/{task_id}/compliance | 任务合规报告 | 登录用户 |
| 53 | 打包 | POST | /api/v1/packages | 创建打包 | 运营+ |
| 54 | 打包 | GET | /api/v1/packages/{id} | 打包状态 | 运营+ |
| 55 | 打包 | GET | /api/v1/packages/{id}/download | 下载打包 | 运营+ |
| 56 | 审计 | GET | /api/v1/audit-logs | 审计日志 | 管理员/审计 |
| 57 | 审计 | GET | /api/v1/audit-logs/{id} | 审计详情 | 管理员/审计 |
| 58 | 刊登 | GET | /api/v1/listings | 刊登列表 | 登录用户（二期） |
| 59 | 刊登 | POST | /api/v1/listings | 创建刊登 | 运营+（二期） |
| 60 | 刊登 | GET | /api/v1/listings/{id} | 刊登详情 | 登录用户（二期） |
| 61 | 刊登 | POST | /api/v1/listings/{id}/retry | 重试刊登 | 运营+（二期） |
| 62 | WebSocket | WS | /api/v1/ws?token=xxx | 任务实时追踪 | 登录用户 |

---

# 附录

## 15\.1 请求/响应示例汇总

### 15\.1\.1 登录

```Bash
curl -X POST http://localhost:8002/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@agentic-commerce.local","password":"admin123"}'
```

### 15\.1\.2 创建批次

```Bash
curl -X POST http://localhost:8002/api/v1/batches \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 7f3e9c2b4a5d6e8f1a2b3c4d5e6f7a8b" \
  -d '{
    "name": "黑五预热批次-001",
    "sku_ids": ["a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"],
    "config": {
      "content_types": ["copy","image","video"],
      "media_type": "mixed",
      "style": "科技感",
      "platform": "amazon",
      "language": "zh"
    }
  }'
```

### 15\.1\.3 上传知识库文档

```Bash
curl -X POST http://localhost:8002/api/v1/knowledge-docs \
  -H "Authorization: Bearer <token>" \
  -F "file=@brand-guidelines.pdf" \
  -F "category=brand_visual" \
  -F "doc_type=brand_guide"
```

### 15\.1\.4 WebSocket 订阅

```JavaScript
const ws = new WebSocket(
  `ws://localhost:8002/api/v1/ws?token=${accessToken}`
);
ws.onopen = () => {
  ws.send(JSON.stringify({
    action: "subscribe",
    task_ids: [taskId]
  }));
};
```

## 15\.2 常见错误场景
| 场景 | 触发条件 | code | 处理建议 |
| :--- | :--- | :--- | :--- |
| 未登录访问 | 无 Authorization 头 | 401 | 跳转登录页 |
| Token 过期 | exp 已过 | 401 | 用 refresh_token 刷新 |
| 跨租户访问 | URL 中 ID 属于其他租户 | 403 | 提示无权限 |
| SKU 编码重复 | 同租户下 sku_code 已存在 | 409 | 修改 SKU 编码 |
| 文件过大 | 上传 > 20MB | 413 | 压缩后重传 |
| 参数校验失败 | 邮箱格式错误 | 422 | 修正参数 |
| 限流超限 | 超过 600 次/分钟 | 429 | 稍后重试 |
| 配额超限 | Token 消耗超日配额 | 429 | 升级套餐 |
| 任务已取消 | 重试已取消任务 | 400 | 重新创建任务 |
| 任务已完成 | 重试已完成任务 | 400 | 无需重试 |
| 重试超限 | retry_count >= max_retries | 400 | 人工介入 |
| 厂商不可用 | 默认厂商 401 | 500 | 切换厂商 |
| 知识库为空 | 无合规规则 | 200 | 提示未配置，放行 |
| WebSocket 断线 | 网络抖动 | — | 自动重连 + 补发 |
| 跨租户订阅 WS | 订阅其他租户任务 | 403 | 拒绝连接 |
| 打包文件过大 | 超过 2GB | 413 | 分卷或异步 |
| 刊登 API 限流 | 平台限流（二期） | 429 | 按平台规则重试 |
| 刊登被拒绝 | 字段不合规（二期） | 400 | 回传原因，引导修正 |
