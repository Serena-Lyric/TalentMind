# TalentMind Phase 1 M1 and Career Nebula Default Implementation Plan

> **2026-10-22 execution update:** The graph change is delivered as independent Draft PR #48. M1 real validation found and fixed the CN slow-panel stability bug and the Liepin same-page QR login-wall classification. Zhaopin reached a real `pending` record but formal persistence remains blocked until the identity-column migration is separately approved; Liepin requires user login; BOSS bridge awaits manual unpacked-extension installation. This plan's bridge expansion is not a license to continue building browser automation around Windows.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `node-field-v1` the normal Career Nebula default while preserving explicit legacy fallback, and make real BOSS, Zhaopin, and Liepin collection operate from the TalentMind management UI with traceable results.

**Architecture:** The existing Vue galaxy renderer receives a default-space rule change only. BOSS uses a narrowly scoped Manifest V3 Edge extension that reads the page only after user clicks and posts bounded visible text to a loopback bridge; that bridge feeds the existing clean, identity, dedup, and `jd_pool` repository path. Zhaopin/Liepin continue through their existing visible-DOM CDP adapters, whose verified/pending/unknown decisions remain unchanged.

**Tech Stack:** Vue 3, TypeScript, Three.js, FastAPI, Pydantic v2, SQLAlchemy/MySQL, Manifest V3 JavaScript, Node test runner, pytest.

**Spec:** `docs/PRODUCT_DECISIONS.md`, `docs/review/Product-integration-2026-10-21.md`, `docs/review/Zhaopin-identity-pending-2026-10-21.md`, `docs/superpowers/plans/2026-10-21-boss-browser-bridge.md`.

## Global Constraints

- Use only the latest fetched `origin/master` and develop on `codex/phase1-m1-real-collection-20261022`.
- Do not modify node identity, business relations, official graph snapshots, source indexes, M2 formal tables, or Neo4j.
- Default `/graph` without parameters must use `node-field-v1`; `graphSpace=legacy` must preserve all other query parameters.
- Real collection is limited to one platform, one keyword, one city, one page, at most five list entries, and at most five detail attempts.
- Do not bypass login, CAPTCHA, security verification, access limits, or anti-bot controls.
- Do not read or transmit cookies, passwords, authorization headers, full HTML, or private browser storage.
- The bridge accepts only loopback requests, the committed extension origin, the local management origin, and a random token.
- List capture never writes `jd_pool`; only a valid, non-truncated same-URL detail can be persisted.
- Do not execute formal MySQL DDL in this task without separate user approval. A migration-dependent pending write must fail explicitly with `identity_schema_migration_required`.
- Integration tests use isolated databases. Tests that write fixtures must remove them by exact unique keys and report zero leftovers.
- Preserve the two known B3 documentation-source failures; do not rewrite historical evidence to make the suite green.

## Review Focus

- Repeated capture of the same BOSS detail URL must return `skipped`, not insert another row.
- A BOSS list card or truncated/restricted detail must never be written as a complete JD.
- A non-loopback request, ordinary web origin, unknown extension origin, missing token, or stale token must not create or ingest a session.
- Zhaopin must reject a stale panel, unchanged panel, title mismatch, empty body, truncated body, or body that fails existing validity checks.
- A database missing the identity columns must still read history, but must not silently drop pending/content/evidence fields during a write.
- The graph default switch must not rewrite data, disable fixed projection, or lose dataset/camera parameters in the legacy link.

---

### Task 1: Make node-field-v1 the default galaxy

**Files:**
- Modify: `frontend/src/components/GraphPanorama.vue`
- Modify: `frontend/tests/galaxyFieldLifecycle.test.ts`
- Modify: `docs/PRODUCT_DECISIONS.md`
- Modify: `docs/superpowers/资产与状态.md`

**Interfaces:**
- Consumes: existing `nodeFieldMode`, `spatialMode`, `legacySpaceHref`, and `GalaxySpatialField` path.
- Produces: default `nodeFieldMode=true` for ordinary spatial mode; `graphSpace=legacy` keeps it false; fixed projection keeps it false.

- [ ] **Step 1: Write failing behavior tests**

Add assertions to `galaxyFieldLifecycle.test.ts`:

```ts
const plain = graphComponent(undefined, '')
assert.equal(plain.state.nodeFieldMode, true)
assert.match(plain.state.legacySpaceHref, /graphSpace=legacy/)

const legacy = graphComponent(undefined, '?graphSpace=legacy')
assert.equal(legacy.state.nodeFieldMode, false)

const fixed = graphComponent(undefined, '?graphCamera=fixed')
assert.equal(fixed.state.nodeFieldMode, false)
```

- [ ] **Step 2: Verify RED**

Run: `pnpm --dir frontend test`

Expected: the no-parameter assertion fails because `nodeFieldMode` is currently false.

- [ ] **Step 3: Change only the default rule and user-facing wording**

Set `nodeFieldMode` to `spatialMode && query.get('graphSpace') !== 'legacy'`. Keep explicit `node-field-v1` working. Replace “候选” wording with default-space wording while retaining the legacy fallback link.

- [ ] **Step 4: Verify GREEN**

Run: `pnpm --dir frontend test`

Run: `pnpm --dir frontend run build`

Expected: tests pass, typecheck passes, and Vite build exits 0.

- [ ] **Step 5: Commit the independent graph change**

```powershell
git add frontend/src/components/GraphPanorama.vue frontend/tests/galaxyFieldLifecycle.test.ts docs/PRODUCT_DECISIONS.md docs/superpowers/资产与状态.md
git commit -m "feat(graph): default career nebula to node field"
```

### Task 2: Define and secure the local browser bridge

**Files:**
- Create: `backend/app/collect/bridge_schema.py`
- Create: `backend/app/collect/bridge_access.py`
- Create: `backend/tests/test_collection_bridge_schema.py`
- Create: `backend/tests/test_collection_bridge_access.py`
- Modify: `backend/app/main.py`
- Create: `frontend/bridge-extension/manifest.json`

**Interfaces:**
- Produces: `BridgeCapture`, `BridgeSessionCreate`, `validate_capture(payload: dict) -> BridgeCapture`.
- Produces: `require_bridge_access(request: Request) -> None`, `get_bridge_token() -> str`.
- Produces: stable extension origin `chrome-extension://<derived-id>` from committed public manifest key.

- [ ] **Step 1: Write failing schema tests**

Test valid BOSS list/detail shapes, five-item limit, unknown fields, foreign domains, credentials, HTML, overlarge body, and missing required fields.

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge_schema.py -q`

Expected: FAIL because the bridge schema module does not exist.

- [ ] **Step 3: Implement strict bounded models**

Use `extra='forbid'`, explicit BOSS host allowlists, `schema_version='m1-browser-bridge-v1'`, list length ≤ 5, page URL equality checks, and credential/HTML key rejection.

- [ ] **Step 4: Write failing access tests and verify RED**

Cover missing/wrong token, non-loopback client, ordinary web origin, unknown extension origin, valid extension origin, and management-origin pairing.

- [ ] **Step 5: Implement token and CORS**

Persist a 32-byte URL-safe token under `data/local/collection/bridge.token` with owner-only defaults where supported. Use constant-time comparison. Add only the fixed extension origin to the existing CORS list.

- [ ] **Step 6: Verify GREEN**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge_schema.py backend/tests/test_collection_bridge_access.py -q`

- [ ] **Step 7: Commit**

```powershell
git add backend/app/collect/bridge_schema.py backend/app/collect/bridge_access.py backend/app/main.py backend/tests/test_collection_bridge_schema.py backend/tests/test_collection_bridge_access.py frontend/bridge-extension/manifest.json
git commit -m "feat(m1): secure browser bridge contract"
```

### Task 3: Persist bridge sessions and expose their results

**Files:**
- Create: `backend/app/collect/bridge.py`
- Create: `backend/app/routers/collection_bridge.py`
- Create: `backend/tests/test_collection_bridge.py`
- Modify: `backend/app/collect/control.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `create_session(payload) -> dict`, `append_capture(session_id, capture) -> dict`, `finish_session(session_id) -> dict`, `get_session(session_id) -> dict`.
- Consumes: `control.get_results(run_id)` and existing collection status/history shape.
- Produces routes under `/api/collection/bridge`.

- [ ] **Step 1: Write failing lifecycle tests**

Create a session, append list/detail/rejection events, finish it, reload from disk, and assert stable counts, history visibility, and results retrieval. Assert missing and finished sessions reject later captures.

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge.py -q`

Expected: FAIL because the bridge module and routes are absent.

- [ ] **Step 3: Implement atomic private storage**

Store session JSON and the existing `<run_id>.events.jsonl` under `data/local/collection`. Use temporary-file replace, UUID run IDs, canonical JSON, and atomic append under a process lock. Add history entries through a narrowly scoped `control` helper without starting a subprocess.

- [ ] **Step 4: Implement lifecycle routes and pairing data**

Include `bridge.token` only in the loopback management endpoint. Capture endpoints require the token header and extension origin; management status/creation endpoints require the local management origin.

- [ ] **Step 5: Verify GREEN and restart compatibility**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge.py backend/tests/test_collection_product.py -q`

Expected: all selected tests pass and reload after module reconstruction preserves the session.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/collect/bridge.py backend/app/routers/collection_bridge.py backend/app/collect/control.py backend/app/main.py backend/tests/test_collection_bridge.py
git commit -m "feat(m1): persist manual browser bridge sessions"
```

### Task 4: Ingest BOSS detail through the existing M1 pipeline

**Files:**
- Modify: `backend/app/collect/bridge.py`
- Modify: `backend/tests/test_collection_bridge.py`

**Interfaces:**
- Consumes: `normalize_boss_job`, `clean`, `is_valid_jd`, `run_pipeline`, and `save_incremental_jd_rows`.
- Produces: `listed`, `detail`, `persisted`, `rejected`, `failed`, and `finished` events compatible with `control.get_results`.

- [ ] **Step 1: Write failing ingestion tests**

Use an injected saver double for branching and an isolated SQLAlchemy database for the pipeline contract. Assert list capture inserts zero; valid detail inserts one; repeat detail inserts zero and emits `skipped`; challenge, truncated, empty, title-mismatched, and foreign-URL captures emit explicit rejections and insert zero.

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge.py -q`

Expected: ingestion cases fail because captures are only persisted as lifecycle records.

- [ ] **Step 3: Implement serialized detail ingestion**

Require same-origin BOSS detail URL and matching title. Reuse existing cleaner/validity and repository logic. Do not set new identity columns for the legacy-schema BOSS verified path; emit identity `verified` in the event while leaving the database row compatible with the old schema until migration is approved.

- [ ] **Step 4: Enforce bounded/idempotent behavior**

Cap five distinct list URLs and five detail attempts per session. Reject further details with `bridge_session_limit_reached`. Duplicate capture digests return the prior result without a second write.

- [ ] **Step 5: Verify GREEN**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_bridge.py backend/tests/test_boss_fetcher.py backend/tests/test_pipeline.py -q`

- [ ] **Step 6: Commit**

```powershell
git add backend/app/collect/bridge.py backend/tests/test_collection_bridge.py
git commit -m "feat(m1): ingest manual BOSS detail captures"
```

### Task 5: Add the explicit-click Edge extension

**Files:**
- Create: `frontend/bridge-extension/background.js`
- Create: `frontend/bridge-extension/extractor.js`
- Create: `frontend/bridge-extension/popup.html`
- Create: `frontend/bridge-extension/popup.js`
- Create: `frontend/bridge-extension/README.md`
- Create: `frontend/tests/bridgeExtractor.test.ts`

**Interfaces:**
- Consumes: bridge routes and token pairing.
- Produces: one request per explicit `capture-list` or `capture-detail` click.

- [ ] **Step 1: Write failing extractor tests**

Use a small fake document contract to assert exact list metadata, five-item truncation, full detail text with newlines, truncation detection, challenge-page rejection, unrelated-domain rejection, and absence of HTML or credential fields.

- [ ] **Step 2: Verify RED**

Run: `node --experimental-strip-types --test frontend/tests/bridgeExtractor.test.ts`

Expected: FAIL because the extractor is absent.

- [ ] **Step 3: Implement the extractor and popup**

Use only `activeTab`, `scripting`, `storage`, and the narrow loopback host permission. Register no persistent content script. Store token, session ID, and last server response locally. Never retry automatically.

- [ ] **Step 4: Verify extractor and manifest safety**

Run: `node --experimental-strip-types --test frontend/tests/bridgeExtractor.test.ts`

Expected: PASS; manifest has no `<all_urls>` and no cookie permission.

- [ ] **Step 5: Commit**

```powershell
git add frontend/bridge-extension frontend/tests/bridgeExtractor.test.ts
git commit -m "feat(m1): add explicit BOSS browser extension"
```

### Task 6: Integrate the bridge into the TalentMind collection page

**Files:**
- Modify: `frontend/src/views/Collection.vue`
- Modify: `frontend/src/api/collection.ts`
- Create: `frontend/src/components/CollectionBridge.vue`
- Create: `frontend/tests/collectionBridge.test.ts`
- Modify: `frontend/tests/collectionConsole.test.ts`

**Interfaces:**
- Consumes: `/api/collection/bridge` lifecycle endpoints.
- Produces: workspace mode `bridge`; list/details/inserted/updated/skipped/rejected/failed counts and per-event evidence.

- [ ] **Step 1: Write failing UI tests**

Assert bridge session creation does not call prepare/start/CDP; pairing instructions expose the token only for loopback; finishing is explicit; refresh reads existing session; duplicate/rejection results do not mutate final counts.

- [ ] **Step 2: Verify RED**

Run: `node --experimental-strip-types --test frontend/tests/collectionBridge.test.ts frontend/tests/collectionConsole.test.ts`

Expected: FAIL because the component and API functions are absent.

- [ ] **Step 3: Implement the bridge panel**

Present BOSS as “普通浏览器人工采集”, retain CDP as diagnostics, show extension load instructions, session ID/token copy, refresh/finish/stop controls, exact counters, event table, and raw-detail link through the existing authorized local reader.

- [ ] **Step 4: Verify GREEN**

Run: `pnpm --dir frontend test`

Run: `pnpm --dir frontend run build`

Expected: all tests pass and build exits 0.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/Collection.vue frontend/src/api/collection.ts frontend/src/components/CollectionBridge.vue frontend/tests/collectionBridge.test.ts frontend/tests/collectionConsole.test.ts
git commit -m "feat(m1): expose browser bridge in collection console"
```

### Task 7: Verify Zhaopin and Liepin against the real sites

**Files:**
- Modify only if a proven real blocker requires a bounded fix:
  - `backend/app/collect/fetch_cn_jobs.py`
  - `backend/app/collect/fetchers/job_sites.py`
  - `backend/app/collect/identity.py`
  - corresponding tests under `backend/tests/`
- Create private evidence under ignored `data/local/phase1-acceptance-20261022/`.
- Create public-safe report under `docs/review/`.

**Interfaces:**
- Consumes: existing management prepare/start/stop/results/history APIs.
- Produces: one real run per platform with list, detail attempt/obtained, content eligibility, identity, persistence/rejection, and stop reason.

- [ ] **Step 1: Verify interface unchanged on focused tests**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_cn_detail_gate.py backend/tests/test_cn_job_fetchers.py backend/tests/test_collection_identity.py backend/tests/test_collection_product.py -q`

- [ ] **Step 2: Run explicit one-platform Zhaopin preparation**

Use the normal UI. If accessible, start one bounded run. Inspect the private event log for panel-change, stable-sample, title, content eligibility, and identity evidence. Do not relax gates.

- [ ] **Step 3: Run explicit one-platform Liepin preparation**

Use the normal UI. Prefer a real detail URL if the existing adapter yields one. If only DOM content is available, require the same binding/body gates. Stop on login, challenge, or truncated guest content.

- [ ] **Step 4: Verify persistence and migration boundary**

Trace inserted/skipped/rejected events to exact `jd_pool` rows. If the live path requires the three identity columns, record the explicit `identity_schema_migration_required` failure, target, backup status, and do not execute DDL.

- [ ] **Step 5: Add a failing regression test only if a real adapter bug is found**

Name the production change that would make the test fail, watch it fail, implement the smallest fix, and rerun the focused suite.

### Task 8: Prepare the identity-schema migration gate without applying it

**Files:**
- Create: `backend/app/collect/migration_preflight.py`
- Create: `backend/tests/test_collection_migration_preflight.py`
- Create: `scripts/check-identity-migration.ps1`
- Modify: `backend/app/collect/README.md`

**Interfaces:**
- Produces: read-only target/schema/count/digest report; explicit `migration_required` or `migration_ready` result.
- Produces: no DDL execution without a separate explicit apply mode authorized after review.

- [ ] **Step 1: Write failing tests**

Cover old schema, fully migrated schema, partial columns, missing table, and no password leakage in the report.

- [ ] **Step 2: Verify RED**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_migration_preflight.py -q`

- [ ] **Step 3: Implement read-only preflight**

Report sanitized host/port/database, schema hash, row counts, stable content digest, and migration status. Do not contain an implicit DDL path.

- [ ] **Step 4: Verify GREEN**

Run: `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_collection_migration_preflight.py -q`

- [ ] **Step 5: Commit**

```powershell
git add backend/app/collect/migration_preflight.py backend/tests/test_collection_migration_preflight.py scripts/check-identity-migration.ps1 backend/app/collect/README.md
git commit -m "feat(m1): add identity migration preflight"
```

### Task 9: Real acceptance, documentation, and PR

**Files:**
- Create: `docs/review/Phase1-M1-nebula-2026-10-22.md`
- Modify: `docs/superpowers/资产与状态.md`
- Modify: `docs/README.md` if a navigation entry is needed
- Create ignored private evidence under `data/local/phase1-acceptance-20261022/`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: public-safe screenshots/log summaries and a reviewable PR against `master`.

- [ ] **Step 1: Run full affected verification**

Run:

```powershell
backend/.venv/Scripts/python.exe -m pytest -q
pnpm --dir frontend test
pnpm --dir frontend run build
```

Record every failure, including the two known B3 documentation-source failures.

- [ ] **Step 2: Verify the graph in a real browser**

Open ordinary `/#/graph` and confirm `node-field-v1`; open `?graphSpace=legacy#/graph`; check history and M2 candidate graph loading, search, filter, pick, rotate, zoom, and source/detail behavior.

- [ ] **Step 3: Verify the three platform runs**

For each platform record: platform, keyword/city, run ID, list count, detail attempts/obtained/eligible, identity counts, inserted/updated/skipped/rejected/failed, exact `jd_pool` row IDs or rejection reasons, stop behavior, and history/log visibility. A blocked site is recorded as blocked, not success.

- [ ] **Step 4: Verify no duplicate or unintended data**

Repeat the BOSS valid detail capture and assert no second insert. Compare pre/post row counts and exact row identities. Do not delete data without separate authorization.

- [ ] **Step 5: Update product and asset records**

Record the confirmed default graph decision, browser bridge assets, migration status, test evidence dates, and any unresolved login/challenge/DDL blockers.

- [ ] **Step 6: Inspect the final diff and commit only explicit files**

Run: `git status --short`, `git diff --check`, and `git diff --stat`.

Do not use `git add -A`.

- [ ] **Step 7: Push and create a PR to `master`**

The PR body must distinguish completed code, real successes, site blockers, migration-required work, known B3 failures, and evidence paths. Do not merge.
