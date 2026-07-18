# VPN / AnyConnect — DPD timeout (sample handbook)

## Symptoms

- Cisco AnyConnect disconnects after about 30 seconds
- Error mentions DPD timeout
- Internal tools unreachable while VPN drops

## Step 1 — Restart the VPN client

1. Quit Cisco AnyConnect completely (menu bar → Quit).
2. Wait 10 seconds.
3. Reopen AnyConnect and connect again.

Tell the assistant whether the disconnects stopped.

## Step 2 — Clear local VPN cache

1. Disconnect and quit AnyConnect.
2. Remove cached profiles under the client support folder for your OS.
3. Reconnect with your corporate profile.

Tell the assistant the result.

## Step 3 — Create a ticket

If Steps 1–2 fail, ask the assistant to create a support ticket. Include the exact error text and when the issue started.
