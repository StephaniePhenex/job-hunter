# Day 7 Bonus — 详细开发计划与交付说明

## 目标（对照 MVP 计划原文）

| 项 | 说明 |
|----|------|
| 极简前端 | 单页表格 + `StaticFiles`，无构建步骤，与 API 同域 |
| 标签 | `jobs.tags` JSON 数组；由 LLM 在打分结果中返回受控 slug |
| 已申请 | `applied_at` 可空时间戳；`PATCH /jobs/{id}/applied` 幂等更新 |

## 架构决策

1. **存储**：在 `Job` 上使用 `JSON` 列存 `tags`（非单独关联表），与「MVP 不过度工程」一致；PostgreSQL 下升级为 JSONB（迁移脚本已区分方言）。
2. **Schema 演进**：继续不用 Alembic；`schema_upgrade.upgrade_job_table()` 对已有 SQLite/Postgres 库 `ALTER TABLE` 补列。
3. **标签来源**：扩展 `ScoreResult.tags`，与 `match_score` 同一次 LLM 调用产出；Pydantic 校验 + 白名单风格 prompt，失败降级为空列表。
4. **前端**：原生 JS 模块、CSS 变量与 `prefers-color-scheme`；`fetch` JSON API；applied 用 PATCH；扫描触发 `POST /run-scan` 后轮询 `GET /scan-status`。
5. **安全**：列表中链接与文本做转义；PATCH 仅更新 `applied_at`，不暴露额外攻击面。

## 实施顺序（实际执行）

1. 数据模型与迁移辅助 → 2. LLM + pipeline 写回 tags → 3. REST PATCH + `_job_to_dict` → 4. `main.py` 挂载静态资源与 `/` → 5. `app/static/*` UI → 6. pytest + README。

## 验收清单

- [x] 浏览器打开 `http://127.0.0.1:8000/` 可见表格与操作
- [x] `PATCH /jobs/{id}/applied` 行为与 404
- [x] 新扫描任务写入的岗位含 `tags`（需配置 `GEMINI_API_KEY` 或 `OPENAI_API_KEY`）
- [x] 旧数据库启动时自动补列

## 后续可选增强（未做）

- 按 `tag` query 过滤 `GET /jobs`
- 标签纯规则引擎（无 API key 时）
- Docker / CI 中 Playwright 与前端 E2E
