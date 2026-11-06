# TalentMind Manual Capture Extension

This unpacked Manifest V3 extension is for sites where ordinary browser access works but remote-debug/CDP access triggers a security check.

## Safety boundary

- No persistent content script, background navigation, polling, retry, cookie permission, or `<all_urls>` access.
- The extractor runs only after an explicit popup button click on the active BOSS tab.
- It sends visible text and source URLs to the local TalentMind bridge; it does not send HTML, cookies, passwords, or authorization headers.
- List capture records metadata only and must match the session keyword, city and first page. A same-URL, non-truncated valid detail from that list is required before `jd_pool` can be written.
- A verification page/widget sends one blocked event to the local session and stops it. It never solves verification or retries a platform request.
- Missing identity columns or database failure stops the session; no schema migration or silent identity downgrade is performed by the extension.

## Load locally

1. Start TalentMind with `pwsh -File scripts/start-local.ps1`.
2. In the collection page create a “普通浏览器人工采集” session and copy its token and task ID.
3. Open `edge://extensions`, enable developer mode, choose “Load unpacked”, and select this directory.
4. Open a normal BOSS search page in the same browser profile, finish login or verification yourself, then use the extension popup.
5. Capture the matching list first, open one of its details yourself, and capture that detail. Functional checks should use one page, at most two details, with 15–30 seconds between actions. On a verification gate stop; do not keep retrying.

Current validation covers synthetic pages, the actual control API and isolated SQLite. The user's extension installation and live-platform capture have not been verified in this repair. Restart the reviewed backend before using the new API, and obtain separate permission for the identity-column migration.

The committed public key fixes the unpacked extension ID so the loopback API can enforce one stable Origin. It is not a private key or credential.


## Request recovery

Only one capture may be in flight in the extension worker. Repeated clicks (including a reopened popup) are rejected while that request is running. The local POST and response-body read share a 15-second deadline. Timeouts, connection errors and invalid JSON leave the submission outcome **unknown**: check the session results in the TalentMind console before another explicit capture. Aborting a client request does not prove the server did not persist it. There is no automatic retry, and the in-memory guard is not a cross-worker-restart exactly-once guarantee.

Offline regression: from `frontend/`, run `node --experimental-strip-types --test tests/bridge*.test.ts`. These tests simulate Chrome APIs and DOM boundaries; they do not verify extension installation, live-site compatibility or database persistence.

## Mandatory module pacing

Update the backend and reload this extension together. Before any DOM extraction the worker requests a one-use capture permit from the local bridge. A denied permit means the page is not read. The backend uses the same persistent per-platform ledger as CDP collection, with the existing 15–30 second page and 6–12 minute keyword/city switch cadence. Browser-capture reservations use 30 seconds and expire after 15 seconds; the switch reservation also compensates for that 15-second window (375–720 seconds); stale, missing or consumed permits cannot process new content. Creating a new session or restarting the worker does not reset this ledger. A failed attempt does not refund its time slot.

This enforces module-controlled collection, not arbitrary manual browsing or third-party tools. Do not collect outside the module and submit it as a paced live trial. Rate limits never authorize bypassing login, verification or access restrictions.
