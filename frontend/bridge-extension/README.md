# TalentMind Manual Capture Extension

This unpacked Manifest V3 extension is for sites where ordinary browser access works but remote-debug/CDP access triggers a security check.

## Safety boundary

- No persistent content script, background navigation, polling, retry, cookie permission, or `<all_urls>` access.
- The extractor runs only after an explicit popup button click on the active BOSS tab.
- It sends visible text and source URLs to the local TalentMind bridge; it does not send HTML, cookies, passwords, or authorization headers.
- List capture records metadata only. A same-URL, non-truncated valid detail is required before `jd_pool` can be written.

## Load locally

1. Start TalentMind with `pwsh -File scripts/start-local.ps1`.
2. In the collection page create a “普通浏览器人工采集” session and copy its token and task ID.
3. Open `edge://extensions`, enable developer mode, choose “Load unpacked”, and select this directory.
4. Open a normal BOSS search page in the same browser profile, finish login or verification yourself, then use the extension popup.

The committed public key fixes the unpacked extension ID so the loopback API can enforce one stable Origin. It is not a private key or credential.
