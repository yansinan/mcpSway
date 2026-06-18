---
name: apple-icloud-linux
source: https://rclone.org/iclouddrive/
description: "Access Apple iCloud Drive and iCloud Photos from Linux via rclone. Covers global and China-Mainland Apple IDs, 2FA flow, rclone web UI, and troubleshooting."
tags: [icloud, rclone, linux, apple, storage]
---

# iCloud on Linux (via rclone)

Trigger: user wants to access iCloud Drive or iCloud Photos from Linux, configure rclone to connect to Apple iCloud, or debug iCloud authentication failures.

## Overview

rclone's `iclouddrive` backend supports **two Apple services**:

| Service | Config value | Description |
|---------|-------------|-------------|
| iCloud Drive | `drive` (default) | File storage, read/write API |
| iCloud Photos | `photos` | Photo library, read-only API |

Authentication uses SRP (Secure Remote Password) — your password is derived locally into a key, never sent in plaintext. After SRP handshake, 2FA is required (push to trusted device or SMS).

## Setup: Standard (non-China Apple ID)

### Prerequisites

- **rclone ≥ v1.65** (iCloud backend introduced; v1.74 is current as of 2026-06)
- **Apple ID** registered outside mainland China (routes to `iCloud.com`)
- **Trusted device** (iPhone/iPad/Mac) logged into the same Apple ID for 2FA push
- **Apple ID password** (main password — app-specific passwords are **NOT accepted** per rclone docs)

### One-liner (non-interactive creation, then 2FA via reconnect)

```bash
# Create remote (password obscured by rclone's SRP)
rclone config create icloud iclouddrive \
  apple_id=user@example.com password=$(rclone obscure "your_apple_id_password") \
  service=drive

# Complete 2FA (triggers push to trusted device)
# ⚠ Run this interactively in a PTY, not piped — it needs your 2FA code
rclone config reconnect icloud:
```

### Interactive flow (recommended for first-time setup)

```bash
rclone config
```

Steps in the interactive menu:
1. `n` — New remote
2. Name: `icloud` (or your preference)
3. Storage: type `iclouddrive` to search, select the result
4. `service`: `drive` (iCloud Drive) or `photos` (iCloud Photos)
5. `apple_id`: your Apple ID email
6. `password`: choose `y` (type your own), enter your main Apple ID password
7. `config_2fa`: get 6-digit code from trusted device after it gets a push notification → enter it
8. `Edit advanced config?`: `n`
9. Save: `y`

### Verification

```bash
# List root of iCloud Drive
rclone lsd icloud:

# List root of iCloud Photos (if service=photos)
rclone lsd icloud:PrimarySync/
rclone lsd icloud:Shared/            # shared photo albums
```

### Re-authentication (trust token expired)

Trust tokens last ~30 days. Run this to refresh:

```bash
rclone config reconnect icloud:
```

## China-Mainland Apple ID (iCloud.com.cn)

**Known limitation**: rclone upstream v1.74.3 **does NOT support** mainland China Apple IDs. Apple routes China-registered accounts to `iCloud.com.cn` (云上贵州). The SRP/2FA handshake succeeds, but the trust-token issuance step returns HTTP 302 with body `{"domainToUse":"iCloud.com.cn"}` — rclone's hardcoded `iCloud.com` endpoints don't handle this redirect.

### Identification

The error looks like:
```
HTTP error 302 (302 Found) returned body:
  "{\"domainToUse\":\"iCloud.com.cn\"}"
```

### Fixes

Ordered from easiest to most permanent:

1. **Use a non-China Apple ID** — fastest workaround. Create a new Apple ID with a non-163/non-qq/non-21cn email (Gmail, Outlook, iCloud.com, etc.). Follow the standard setup flow above. iCloud Drive works immediately; iCloud Photos needs initialization on a device first (log in to icloud.com → click Photos → accept terms).

2. **Compile rclone from PR #9399** (region option) — adds `region = global | china` config option. Not merged upstream as of 2026-06:
   ```bash
   git clone https://github.com/rclone/rclone
   cd rclone
   git fetch origin pull/9399/head:add-region
   git checkout add-region
   make
   # Use the compiled binary:
   ./rclone config create ... --icloud-region china
   ```
   Requires Go toolchain (`sudo apt install golang-go`).

3. **Use the Kbstsn beta build** (v1.70.0 beta with hardcoded .cn URLs) — available at `https://beta.rclone.org/branch/fix-8257-iclouddrive-cn/`. Note: hardcoded to .cn only — can't switch between global and China regions with this build.

### Status tracking

| Source | Status |
|--------|--------|
| GitHub issue #8257 | Submitted 2024-12, still open as of 2026-06 |
| PR #8818 | Region option, superseded |
| PR #9399 | Clean `region` option, not merged |
| ncw (upstream maintainer) | OK'd the approach in 2025-07-06 comment |

## iCloud Photos Structure

When `service = photos`, the rclone filesystem mirrors Apple's Photos library structure:

```
remote:
├── PrimarySync/               ← your personal photo library
│   ├── All Photos/            ← all photos & videos (chronological)
│   ├── Favorites/             ← marked as favorite
│   └── Recently Deleted/
└── Shared/                    ← shared photo albums
    ├── AlbumName1/            ← each shared album is a subdirectory
    └── AlbumName2/
```

**Metadata** (read-only for photos service):
- `added-time`: time item was added to the library
- `favorite`: bool, whether marked as favorite
- `height` / `width`: image dimensions
- `hidden`: bool, whether hidden from the library

**Note**: Only `PrimarySync/All Photos/` and `Shared/` contain actual files at the leaf. Other subfolders are virtual groupings. To download a photo:
```bash
rclone copy remote:PrimarySync/All\ Photos/IMG_0001.HEIC ~/Downloads/
```

## 2FA Flow (Critical Timing)

rclone uses Apple's standard 2FA: a push notification to trusted devices, then a 6-digit code.

### Common timing failures

| Problem | Cause | Fix |
|---------|-------|-----|
| `Incorrect Verification Code` (-21669) | Code from OLD push submitted to NEW rclone session | Wait for the push that rclone's **current** reconnect triggers — don't pre-emptively send codes |
| Code accepted but `ZONE_NOT_FOUND` | Photos library not initialized on this Apple ID | Log in to icloud.com with this ID, click Photos to initialize |
| `validate2FACode failed` | Code expired or used for wrong session | Get a fresh code from the new push |

### Correct workflow for `rclone config reconnect`

1. Run `rclone config reconnect icloud:` (rclone does SRP, Apple sends push)
2. **Wait** for the 2FA prompt to appear: `config_2fa>`
3. Check phone — new "Apple ID Sign In" push should be visible
4. Tap Allow → 6-digit code appears on screen
5. Enter the code at the prompt
6. rclone stores new trust token

**Don't send codes before step 2** — codes are session-bound and expire when rclone exits.

### SMS alternative

At the `config_2fa>` prompt, type `sms` instead of a 6-digit code. Apple sends a text message with the code. SMS codes have looser session binding.

## rclone Web UI (rcd)

rclone's built-in web UI provides a graphical file browser for all configured remotes.

### Start

```bash
# Basic (localhost-only, no auth — ⚠ only on localhost)
rclone rcd --rc-web-gui

# With auth and custom address
rclone rcd --rc-web-gui --rc-addr 100.66.66.249:5001 \
  --rc-user=admin --rc-pass=YOUR_PASSWORD
```

### systemd integration

```ini
# ~/.config/systemd/user/rclone-webui.service
[Unit]
Description=rclone Web UI
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/rclone rcd --rc-web-gui \
  --rc-web-gui-no-open-browser \
  --rc-addr 100.66.66.249:5001 \
  --rc-user=admin --rc-pass=YOUR_PASSWORD
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now rclone-webui.service
```

### Password management

The password is set **twice**:
1. In the systemd unit's `ExecStart` line (used by rcd at startup)
2. In `~/.config/rclone/webui-password` (user reference)

**When changing the password**, both must be updated and the service must be `daemon-reload` + `restart`:

```bash
# 1. Update webui-password file (for your reference)
echo -n 'newpassword' > ~/.config/rclone/webui-password

# 2. Update systemd unit — patch the ExecStart line
#    change --rc-pass=OLD to --rc-pass=newpassword

# 3. Reload + restart
systemctl --user daemon-reload
systemctl --user restart rclone-webui.service
```

### Remotes in the web UI

The rcd loads all remotes from `~/.config/rclone/rclone.conf` at startup. New remotes added after startup require a restart of the rcd to appear.

## Editing Existing Remotes

When editing a remote via `rclone config` → `e`:

| Prompt | Default action | Notes |
|--------|---------------|-------|
| `service` | Enter = keep existing | `drive` or `photos` |
| `apple_id` | Enter = keep existing | Email |
| `password` | Enter = `n` (keep existing) | `y` to re-enter, `n` to keep encrypted |
| `Edit advanced config?` | Enter = `n` (keep default) | |
| `config_2fa` | Only appears if trust token is needed | Get code from phone |

**Pitfall**: If a 2FA prompt appears during edit, the existing trust token is expired. Completing 2FA issues a new one. If you abort (Ctrl+C or `q` at the prompt), the old expired token remains and the remote won't work until re-authenticated.

## Pitfalls

- **App-specific passwords NOT accepted** — use your main Apple ID password. rclone uses SRP to derive a key locally, so the password is never sent in plaintext.
- **2FA codes are session-bound** — don't get a code before rclone is ready to receive it. Wait for the `config_2fa>` prompt.
- **China region Apple ID** (163.com, 21cn.com, qq.com) — rclone upstream doesn't support iCloud.com.cn. Use PR #9399 or a non-China ID.
- **iCloud Photos requires initialization** — a fresh Apple ID has no Photos "zone". Log in to icloud.com → click Photos → accept terms. Then wait ~5 min before rclone can list it.
- **`ZONE_NOT_FOUND`** — the iCloud Photos library has never been set up on this Apple ID. Initialize on a device or icloud.com.
- **`rclone reconnect` vs `rclone config reconnect`** — `rclone reconnect` (direct subcommand) doesn't exist in v1.74. Use `rclone config reconnect <remote>:` instead.
- **rcd must be restarted after config changes** — the web UI loads all remotes on startup. Add a new remote? Restart the rcd service.
- **No write support for Photos** — iCloud Photos is read-only via rclone. Uploads go to iCloud Drive only.
- **Rate limiting** — Apple applies rate limits on the iCloud Drive API. Don't mount and hammer it with automated writes.
- **Trust token expiry** — tokens last ~30 days. Run `rclone config reconnect <remote>:` proactively before it expires.
- **Editing with stale 2FA** — if you enter the edit flow and a `config_2fa>` prompt appears, you NEED a fresh 2FA code. Pressing Enter sends an empty code → `Incorrect Verification Code`. Complete with a proper code or abort with `q` to keep the old (expired) token.

## References