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
