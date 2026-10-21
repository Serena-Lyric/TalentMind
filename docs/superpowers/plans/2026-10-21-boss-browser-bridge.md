# BOSS 普通浏览器采集桥接 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在普通用户浏览器中通过显式点击扩展采集当前招聘页面，避开 BOSS 对远程调试/CDP 的自动安全跳转，同时复用现有 M1 清洗、去重和入库管线。

**Architecture:** 新增本机桥接 API 和 Manifest V3 扩展。用户手动打开搜索页及职位详情；扩展只在点击时读取当前 DOM，通过带令牌的 loopback API 提交，后端严格校验后复用 `RawJD -> clean -> dedup -> save_incremental_jd_rows`。无后台导航、轮询、Cookie 读取或验证码处理。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy/MySQL、Edge Manifest V3、普通 JavaScript、Vue 3。

**Spec:** `docs/superpowers/traps/2026-10-21-boss-security-check-loop.md`、`docs/review/Unified-product-2026-10-21.md`。

## Global Constraints

- 单轮验证最多 1 页、5 条列表身份、5 条详情。
- 不读取或提交 Cookie、密码、Authorization、验证码或完整 HTML。
- 扩展不得自动翻页、自动打开职位、后台轮询或处理人工验证。
- 列表捕获只生成事件，不写 `jd_pool`；只有有效详情可写正式数据。
- 不改冻结 DDL，不迁移正式数据库，不调用收费模型，不做大规模真实采集。
- 所有桥接请求只接受 loopback、固定扩展 Origin 和随机桥接令牌。
- 测试写库仅使用隔离实例，并按唯一会话 ID/URL 在 `finally` 精确清理。

## Review Focus

- 重复点击同一详情时必须幂等，不新增重复行；由 Task 4 的重复捕获测试覆盖。
- 列表元数据不得冒充完整 JD；由 Task 4 的列表/详情分流测试覆盖。
- 登录页、验证页、截断正文和错岗 URL 必须拒绝；由 Task 4 的页面身份测试覆盖。
- 普通网页、错误扩展 ID、缺失/过期令牌和超大请求必须返回 403/413；由 Task 2 的安全测试覆盖。
- 应用重启后会话、事件和原文入口必须可恢复，且不能借用其他会话的捕获；由 Task 3 的持久化测试覆盖。

---

### Task 1: 定义桥接契约

**Files:**
- Create: `backend/app/collect/bridge_schema.py`
- Create: `backend/tests/test_collection_bridge_schema.py`

**Interfaces:**
- Produces: `BridgeCapture`, `BridgeListItem`, `BridgeDetail`, `BridgeSessionCreate`.
- Produces: `validate_capture(payload: dict) -> BridgeCapture`.

- [ ] **Step 1: Write the failing test**

```python
def test_detail_rejects_credentials_html_and_foreign_domain():
    payload = valid_detail(page_url="https://evil.example/job")
    with pytest.raises(ValueError):
        validate_capture(payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_collection_bridge_schema.py -q`

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement strict Pydantic models**

Use `extra='forbid'`, scheme/host allowlists, credential-key rejection, bounded strings, `schema_version='m1-browser-bridge-v1'`, and list limit 5.

- [ ] **Step 4: Run schema tests**

Run: `pytest backend/tests/test_collection_bridge_schema.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/bridge_schema.py backend/tests/test_collection_bridge_schema.py
git commit -m "feat(m1): define browser bridge capture contract"
```

### Task 2: 增加安全桥接入口

**Files:**
- Create: `backend/app/collect/bridge_access.py`
- Create: `backend/tests/test_collection_bridge_access.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `validate_capture()`.
- Produces: `require_bridge_access(request: Request) -> None`.
- Produces: bridge token at `data/local/collection/bridge.token`; header name `X-TalentMind-Bridge-Token`.

- [ ] **Step 1: Write failing authorization tests**

Test missing token, wrong token, non-loopback client, ordinary web Origin, wrong extension Origin, and valid fixed extension Origin.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_collection_bridge_access.py -q`

Expected: FAIL because bridge access is absent.

- [ ] **Step 3: Implement token and Origin validation**

Generate a 32-byte URL-safe token once under `data/local`; compare with `secrets.compare_digest`; allow only the configured stable Edge extension ID and `http://127.0.0.1:18000`/`localhost`.

- [ ] **Step 4: Add narrowly scoped CORS**

Allow only the fixed `chrome-extension://<id>` origin for `/api/collection/bridge/*`; do not add a wildcard origin.

- [ ] **Step 5: Run security tests**

Run: `pytest backend/tests/test_collection_bridge_access.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/main.py backend/app/collect/bridge_access.py backend/tests/test_collection_bridge_access.py
git commit -m "feat(m1): secure local browser bridge"
```

### Task 3: 持久化桥接会话和事件

**Files:**
- Create: `backend/app/collect/bridge.py`
- Create: `backend/tests/test_collection_bridge_store.py`
- Modify: `backend/app/collect/control.py`

**Interfaces:**
- Consumes: `BridgeSessionCreate`.
- Produces: `create_session(payload) -> BridgeSession`.
- Produces: `append_capture(session_id, capture) -> BridgeCaptureResult`.
- Produces: `finish_session(session_id) -> BridgeSession`.
- Produces event file compatible with `control.get_results()`.

- [ ] **Step 1: Write failing lifecycle tests**

Create a session, append list and detail captures, finish it, reload from disk, and assert identical counts/results; assert a capture for a missing session is rejected.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_collection_bridge_store.py -q`

Expected: FAIL because bridge persistence is absent.

- [ ] **Step 3: Implement isolated storage**

Store sessions in `data/local/collection/bridge/`; use generated `bridge-<uuid>` run IDs; persist captures with canonical JSON and SHA-256; write existing event names so result/history UI can consume them.

- [ ] **Step 4: Make writes atomic and idempotent**

Use temp-file replace for session metadata and capture ID digest to return the previous result on duplicate submission.

- [ ] **Step 5: Run store tests**

Run: `pytest backend/tests/test_collection_bridge_store.py -q`

Expected: PASS and fixture directory absent after teardown.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/collect/bridge.py backend/app/collect/control.py backend/tests/test_collection_bridge_store.py
git commit -m "feat(m1): persist manual browser sessions"
```

### Task 4: 复用 M1 清洗、去重和入库

**Files:**
- Modify: `backend/app/collect/bridge.py`
- Modify: `backend/app/collect/repository.py`
- Create: `backend/tests/test_collection_bridge_ingest.py`
- Create: `backend/app/routers/collection_bridge.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `BridgeCapture`, `append_capture()`.
- Produces: `POST /api/collection/bridge/sessions`.
- Produces: `POST /api/collection/bridge/sessions/{session_id}/captures`.
- Produces: `POST /api/collection/bridge/sessions/{session_id}/finish`.
- Produces: `POST /api/collection/bridge/import`.

- [ ] **Step 1: Write failing ingestion tests**

Use an injected saver double for fast branching tests, then run the same contract against an isolated MySQL fixture to assert list capture produces no insert, valid detail inserts one, duplicate detail inserts zero, and challenge/truncated/foreign URL produce explicit rejection events.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_collection_bridge_ingest.py -q`

Expected: FAIL because bridge ingestion/routes are absent.

- [ ] **Step 3: Implement detail ingestion**

Build `RawJD(source=platform, source_detail=page_url, ...)`, reuse `clean()` and `is_valid_jd()`, then call `save_incremental_jd_rows()` on a serialized transaction. Emit `listed`, `detail`, `persisted`, `rejected`, or `failed` consistently with worker events.

- [ ] **Step 4: Guard formal write boundary**

Reject `description_truncated=True`, login/challenge markers, mutable DOM-only identity, empty detail text, and URL/title mismatch. List metadata never calls the saver.

- [ ] **Step 5: Run route and ingestion tests**

Run: `pytest backend/tests/test_collection_bridge_ingest.py -q`

Expected: PASS; every written fixture has a unique URL and is absent after the fixture teardown query.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/collect/bridge.py backend/app/collect/repository.py backend/app/routers/collection_bridge.py backend/app/main.py backend/tests/test_collection_bridge_ingest.py
git commit -m "feat(m1): ingest browser bridge captures"
```

### Task 5: 实现普通 Edge 扩展

**Files:**
- Create: `frontend/bridge-extension/manifest.json`
- Create: `frontend/bridge-extension/background.js`
- Create: `frontend/bridge-extension/popup.html`
- Create: `frontend/bridge-extension/popup.js`
- Create: `frontend/bridge-extension/extractor.js`
- Create: `frontend/bridge-extension/README.md`
- Create: `frontend/tests/bridgeExtractor.test.ts`

**Interfaces:**
- Consumes: bridge API and token header from Task 2.
- Produces popup actions `capture-list` and `capture-detail`.
- Produces a stable unpacked-extension ID through a committed public `manifest.key`; no private key is needed.

- [ ] **Step 1: Write failing extractor tests**

Run fixtures for BOSS list, BOSS detail, Zhaopin/Liepin redirect pages, truncated detail and unrelated tabs; assert exact accepted/rejected output.

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --experimental-strip-types --test frontend/tests/bridgeExtractor.test.ts`

Expected: FAIL because extractor is absent.

- [ ] **Step 3: Implement Manifest V3 extension**

Use `activeTab`, `scripting`, `storage`, and localhost host permission only. Register no persistent content script. Read DOM only after popup click via `chrome.scripting.executeScript()`.

Add the public `manifest.key` whose derived ID matches the bridge Origin configured in Task 2, so moving the checkout does not silently change the accepted extension ID.

- [ ] **Step 4: Implement one-click capture**

The popup stores the pairing token locally, shows active bridge session, and sends exactly one request per click. Do not retry automatically after network errors.

- [ ] **Step 5: Run extractor tests and build-independent checks**

Run: `node --experimental-strip-types --test frontend/tests/bridgeExtractor.test.ts`

Expected: PASS; manifest parses and contains no `<all_urls>` or cookie permissions.

- [ ] **Step 6: Commit**

```powershell
git add frontend/bridge-extension frontend/tests/bridgeExtractor.test.ts
git commit -m "feat(m1): add manual Edge capture extension"
```

### Task 6: 接入 TalentMind 人工桥接界面

**Files:**
- Modify: `frontend/src/views/Collection.vue`
- Modify: `frontend/src/api/collection.ts`
- Create: `frontend/src/components/CollectionBridge.vue`
- Create: `frontend/tests/collectionBridge.test.ts`

**Interfaces:**
- Consumes bridge session/capture/import APIs.
- Produces workspace mode `bridge`.

- [ ] **Step 1: Write failing UI tests**

Assert creating a bridge session makes no CDP or browser request; capture counts remain separated; duplicate and rejection reasons render without mutating final counts; finishing requires explicit action.

- [ ] **Step 2: Run tests to verify they fail**

Run: `node --experimental-strip-types --test frontend/tests/collectionBridge.test.ts`

Expected: FAIL because the component is absent.

- [ ] **Step 3: Implement `CollectionBridge.vue`**

Show pairing instructions, token copy, session create/finish, list/detail/persisted/rejected/failed counts, per-item evidence, and JSON template download.

- [ ] **Step 4: Mark BOSS bridge-first**

Keep the existing CDP controls for diagnostics; route BOSS production guidance to the bridge mode when remote-debug access is rejected.

- [ ] **Step 5: Run frontend tests and build**

Run: `pnpm --dir frontend test`

Run: `pnpm --dir frontend run build`

Expected: all tests pass and TypeScript/build exits 0.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/views/Collection.vue frontend/src/api/collection.ts frontend/src/components/CollectionBridge.vue frontend/tests/collectionBridge.test.ts
git commit -m "feat(m1): add browser bridge workflow"
```

### Task 7: 普通浏览器真实验收

**Files:**
- Modify: `docs/review/Unified-product-2026-10-21.md`
- Modify: `docs/superpowers/资产与状态.md`
- Modify: `docs/superpowers/traps/2026-10-21-boss-security-check-loop.md`

**Interfaces:**
- Consumes all prior tasks.
- Produces the final browser-bridge acceptance evidence.

- [ ] **Step 1: Automated verification**

Run the new bridge tests, complete frontend tests/build, and affected backend collection tests. Record any unrelated known failures separately.

- [ ] **Step 2: Load the unpacked extension in ordinary Edge**

Confirm it is not running through remote debugging and grant only the declared permissions.

- [ ] **Step 3: Manual BOSS capture**

In the UI create `BOSS · Java · 北京`; manually open one search page; capture five list identities; manually open one detail and capture it once; repeat capture and verify idempotency.

- [ ] **Step 4: Verify product results**

Check exact URL/source identity, original text, duties, source time, inserted/skipped/rejected counts, result drawer and saved database row. Verify list-only items did not create formal JD rows.

- [ ] **Step 5: Verify safety and cleanup**

Confirm no background requests when idle, no cookie/HTML payload, no automatic navigation, and no test markers remain. Record before/after row counts for the selected production row.

- [ ] **Step 6: Commit final evidence**

```powershell
git add docs/review/Unified-product-2026-10-21.md docs/superpowers/资产与状态.md docs/superpowers/traps/2026-10-21-boss-security-check-loop.md
git commit -m "docs(m1): record browser bridge acceptance"
```
