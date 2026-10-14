# 采集模块管理前端接口清单

## 概述

本文档列出采集模块管理前端页面所需的所有后端接口。所有接口均基于 BOSS 直聘数据采集控制文档设计，遵循 RESTful 规范。

## 基础信息

- 基础路径: `/api/collection`
- 数据格式: JSON
- 认证方式: 待定（建议 JWT Token）
- 时间格式: ISO 8601 带时区（如 `2026-08-21T09:50:10+08:00`）

## 接口列表

### 1. 获取当前任务状态

**接口**: `GET /api/collection/status`

**描述**: 获取当前采集任务的状态信息，包括任务状态、进度、计数等。

**请求参数**: 无

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "run_id": "boss-20260821-095010",
    "status": "completed",
    "mode": "once",
    "started_at": "2026-08-21T09:50:10+08:00",
    "finished_at": "2026-08-21T09:54:37+08:00",
    "current_keyword": "Python",
    "current_city": "北京",
    "current_round": 1,
    "total_rounds": 1,
    "listed": 12,
    "details": 8,
    "new": 0,
    "skipped": 12,
    "errors": 0,
    "last_error": null,
    "next_run_at": null,
    "cdp_status": "page_available",
    "browser_page_status": "boss_job_detail",
    "database_total": 126133,
    "database_boss_total": 488,
    "database_new_count": 0
  }
}
```

**状态枚举**:
- `idle`: 空闲
- `preparing`: 准备中
- `waiting_for_browser`: 等待浏览器
- `running`: 运行中
- `waiting_next_round`: 等待下一轮
- `stopped`: 已停止
- `completed`: 已完成
- `error`: 错误
- `auth_required`: 需要登录
- `verification_detected`: 需要验证
- `cdp_unavailable`: CDP不可用

### 2. 启动采集任务

**接口**: `POST /api/collection/start`

**描述**: 启动一个新的采集任务。

**请求参数**:
```json
{
  "mode": "once",  // 必填: once, limited, continuous
  "rounds": 3,     // 可选: 仅当 mode=limited 时必填
  "keywords": ["Python", "Java"],  // 可选: 关键词列表
  "cities": ["101010100", "101020100"],  // 可选: 城市代码列表
  "pages": 1,      // 可选: 每轮页数
  "detail_limit": 8,  // 可选: 详情上限
  "max_jobs": 12,  // 可选: 岗位上限
  "page_delay_min": 15,  // 可选: 页面最小间隔(秒)
  "page_delay_max": 30,  // 可选: 页面最大间隔(秒)
  "settle_min": 5,  // 可选: 页面稳定最小等待(秒)
  "settle_max": 10,  // 可选: 页面稳定最大等待(秒)
  "switch_interval_min": 360,  // 可选: 组合切换最小间隔(秒)
  "switch_interval_max": 720,  // 可选: 组合切换最大间隔(秒)
  "check_cdp": true  // 可选: 启动前检查CDP
}
```

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "run_id": "boss-20260821-095010"
  }
}
```

### 3. 停止采集任务

**接口**: `POST /api/collection/stop`

**描述**: 停止当前运行的采集任务。

**请求参数**:
```json
{
  "run_id": "boss-20260821-095010"  // 可选: 任务ID，不传则停止当前任务
}
```

**响应数据**:
```json
{
  "code": 200,
  "message": "任务已停止"
}
```

### 4. 获取采集进度

**接口**: `GET /api/collection/progress`

**描述**: 获取当前采集任务的实时进度。

**请求参数**: 无

**响应数据**: 同"获取当前任务状态"

### 5. 获取采集统计数据

**接口**: `GET /api/collection/stats`

**描述**: 获取采集数据的统计信息，包括数据库总量、数据质量等。

**请求参数**: 无

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "database_total": 126133,
    "database_boss_total": 488,
    "database_new_count": 0,
    "latest_crawled_at": "2026-08-20T12:20:44+08:00",
    "data_quality": {
      "empty_source_detail": 0,
      "duplicate_source_detail": 0,
      "placeholder_empty_url": 0,
      "duties_nonempty": 243,
      "status_distribution": [
        {"status": "cleaned", "count": 488}
      ]
    }
  }
}
```

### 6. 获取历史任务列表

**接口**: `GET /api/collection/history`

**描述**: 获取历史采集任务列表，支持分页和筛选。

**请求参数**:
- `page`: 页码，默认 1
- `page_size`: 每页条数，默认 10
- `status`: 状态筛选
- `mode`: 模式筛选
- `start_date`: 开始日期
- `end_date`: 结束日期

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "items": [
      {
        "run_id": "boss-20260821-095010",
        "mode": "once",
        "status": "completed",
        "started_at": "2026-08-21T09:50:10+08:00",
        "finished_at": "2026-08-21T09:54:37+08:00",
        "listed": 12,
        "details": 8,
        "new": 0,
        "skipped": 12,
        "errors": 0,
        "keywords": ["Python"],
        "cities": ["北京"]
      }
    ],
    "total": 1
  }
}
```

### 7. 获取采集参数配置

**接口**: `GET /api/collection/config`

**描述**: 获取当前采集参数配置。

**请求参数**: 无

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "mode": "once",
    "keywords": ["Python", "Java", "前端", "后端", "数据分析", "人工智能", "产品经理", "项目经理"],
    "cities": [
      {"name": "北京", "code": "101010100"},
      {"name": "上海", "code": "101020100"},
      {"name": "深圳", "code": "101280600"}
    ],
    "pages": 1,
    "detail_limit": 8,
    "max_jobs": 12,
    "page_delay_min": 15,
    "page_delay_max": 30,
    "settle_min": 5,
    "settle_max": 10,
    "switch_interval_min": 360,
    "switch_interval_max": 720,
    "rounds": 0,
    "check_cdp_before_start": true
  }
}
```

### 8. 更新采集参数配置

**接口**: `PUT /api/collection/config`

**描述**: 更新采集参数配置。

**请求参数**: 同"获取采集参数配置"的响应数据

**响应数据**:
```json
{
  "code": 200,
  "message": "配置已更新"
}
```

### 9. 获取CDP状态

**接口**: `GET /api/collection/cdp-status`

**描述**: 获取 CDP 连接状态和浏览器页面信息。

**请求参数**: 无

**响应数据**:
```json
{
  "code": 200,
  "data": {
    "endpoint": "http://127.0.0.1:9333",
    "reachable": true,
    "boss_page_count": 1,
    "last_checked_at": "2026-08-21T09:50:10+08:00",
    "page_targets": [
      {
        "type": "page",
        "url": "https://www.zhipin.com/job_detail/...",
        "title": "Python开发工程师"
      }
    ]
  }
}
```

### 10. 获取数据库统计

**接口**: `GET /api/collection/database-stats`

**描述**: 获取数据库统计信息，包括总量、来源分布等。

**请求参数**: 无

**响应数据**: 同"获取采集统计数据"

## 错误响应

所有接口在出错时返回统一格式：
```json
{
  "code": 400,
  "message": "错误信息",
  "error": "详细错误描述"
}
```

常见错误码：
- 400: 请求参数错误
- 401: 未授权
- 403: 禁止访问
- 404: 资源不存在
- 500: 服务器内部错误

## 注意事项

1. 所有时间字段均使用 ISO 8601 格式，带时区信息。
2. 任务状态转换应遵循状态机模型。
3. 启动任务前建议检查 CDP 连接状态。
4. 停止任务时应使用任务 ID 绑定，避免误停其他任务。
5. 数据库统计建议缓存，避免频繁查询。
6. 历史任务列表应支持分页和筛选。
7. 配置更新后应重新加载配置。
8. 建议前端每 30 秒自动刷新状态。
