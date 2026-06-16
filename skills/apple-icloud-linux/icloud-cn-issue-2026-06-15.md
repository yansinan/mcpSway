# iCloud China Region Issue — Session Reference 2026-06-15

## The China Region Problem

Apple ID `yansinan@163.com` (mainland China) routes to `iCloud.com.cn` (云上贵州). rclone v1.74.3 hardcodes `iCloud.com` endpoints. After SRP + 2FA succeed, the trust-token issuance gets redirected:

```
HTTP error 302 (302 Found) returned body: "{\"domainToUse\":\"iCloud.com.cn\"}"
```

This is **after** the 2FA code is accepted — the code itself is valid. The failure is at the post-2FA trust-token endpoint.

## Workaround Used

Used a non-China Apple ID (`yansinan@hotmail.com`) instead. This routes to standard `iCloud.com` and works with rclone v1.74.3 out of the box.

## Config Evolution

1. Initially had `[icloud]` with `apple_id = yansinan@163.com` — broken due to .cn redirect
2. Edited to `apple_id = yansinan@hotmail.com`, `service = photos` — worked after 2FA
3. Web UI was used to create two separate remotes:
   - `idrive-hotmail` (service=drive, default)
   - `iphotos-hotmail` (service=photos)
4. Old `[icloud]` section was deleted

## 2FA Code Timing

The user sent 2FA codes preemptively before rclone was ready to receive them. This caused "Incorrect Verification Code" because each `rclone config reconnect` triggers a NEW push with a NEW code. Codes from OLD pushes are invalid for NEW sessions.

**Lesson**: never accept 2FA codes before starting the rclone reconnect that would consume them.

## rclone Web UI Password Sync

The user changed the password in `~/.config/rclone/webui-password` but the rcd reads the password from the systemd unit's `ExecStart` line (`--rc-pass=...`). Both must be in sync.

When updating the password:
1. Edit `~/.config/rclone/webui-password`
2. Edit `~/.config/systemd/user/rclone-webui.service` → change `--rc-pass=`
3. `systemctl --user daemon-reload`
4. `systemctl --user restart rclone-webui.service`

## Keys

- `rclone config reconnect` is the correct command (not `rclone reconnect`)
- `rclone config reconnect` triggers a new 2FA push to all trusted devices
- After successful reconnect, the config stores:
  - `cookies = ...` (Apple session cookies)
  - `trust_token = HSARM...` (SRP-derived trust token, 200 chars)
  - `_auth_session = ` (empty — normal for v1.65+, trust_token replaces it)
- The iCloud Photos library (`service=photos`) requires a non-empty "zone" — initialize on icloud.com first
- `rclone lsd remote:` may show empty root for Photos; items are under `PrimarySync/` and `Shared/`
