# Keep-Alive Status Check

## How to Verify Keep-Alive is Working

### 1. Check Environment Variable

On Render Dashboard:
1. Go to "Environment" tab
2. Look for: `RENDER_SERVICE_URL = https://buscador-pisos.onrender.com`
3. If missing → **ADD IT NOW**

### 2. Check Render Logs for Keep-Alive Messages

After adding the variable and redeploying, you should see in logs:

```
🌐 Servidor HTTP iniciado correctamente
   Keep-alive: habilitado
💗 Keep-alive iniciado (ping cada 10 minutos)
   URL: https://buscador-pisos.onrender.com
```

Then every 10 minutes:
```
💗 Keep-alive ping exitoso - HH:MM:SS
```

### 3. Monitor Service Uptime

Check that the service stays "active" (green) in Render Dashboard instead of going to "sleeping" (gray).

### 4. Verify Scheduled Runs Happen

Check `/status` endpoint before and after scheduled time (every 6 hours):

**Before 14:06:**
```json
"next_scheduled_run": "2026-01-27T14:06:50"
```

**After 14:06:**
```json
"last_run": "2026-01-27T14:06:XX",
"next_scheduled_run": "2026-01-27T20:06:XX"
```

If `last_run` doesn't update → service spun down → keep-alive not working

---

## What Should Happen

With keep-alive working properly:

**Every 10 minutes:** Keep-alive pings `/health`
```
08:06 → Service starts
08:16 → Keep-alive ping #1
08:26 → Keep-alive ping #2
08:36 → Keep-alive ping #3
... (continues forever)
14:06 → Scheduled bot run #2 (6 hours later)
14:16 → Keep-alive ping
20:06 → Scheduled bot run #3 (6 hours later)
```

**Every 6 hours:** Scheduler runs bot automatically
- Finds new properties
- Sends Telegram notification
- No manual intervention needed

---

## Current Issue

**Without RENDER_SERVICE_URL set:**
```
08:06 → Service starts, bot runs
08:21 → Render spins down service (15 min inactivity)
14:06 → Scheduled run doesn't happen (service asleep)
```

**Service only wakes when:**
- Manual request to `/run`
- External traffic to any endpoint
- Manual redeploy

---

## Quick Test After Setting Variable

1. Add `RENDER_SERVICE_URL` to Render
2. Wait for redeploy (~2 minutes)
3. Check logs for "Keep-alive iniciado"
4. Wait 10 minutes
5. Check logs for "Keep-alive ping exitoso"
6. Wait 6 hours
7. Check `/status` - `last_run` should update
8. Check Telegram for notification

---

## Troubleshooting

### Keep-alive not starting?
Check logs for:
```
Keep-alive: deshabilitado
```

**Fix:**
1. Verify `RENDER_SERVICE_URL` is set in Environment
2. Verify `keep_alive.enabled: true` in config.yaml (it is)
3. Redeploy service

### Keep-alive pings failing?
Check logs for:
```
⚠️ Keep-alive ping falló (status XXX)
```

**This is OK!** Even failed pings keep the service alive. The HTTP request itself prevents spin-down, regardless of response.

### Scheduled runs still not happening?
1. Check service is "active" not "sleeping" in Dashboard
2. Verify logs show keep-alive pings every 10 minutes
3. Check for errors in logs around scheduled time
4. Try manual `/run` to verify bot still works

---

## Expected Timeline

```
Day 1:
00:00 → Deploy with RENDER_SERVICE_URL
00:00 → Keep-alive starts
00:00 → Bot runs immediately
00:10 → Keep-alive ping ✓
00:20 → Keep-alive ping ✓
06:00 → Bot runs automatically ✓ (notification sent)
12:00 → Bot runs automatically ✓ (notification sent)
18:00 → Bot runs automatically ✓ (notification sent)

Day 2:
00:00 → Bot runs automatically ✓ (notification sent)
... continues 24/7
```

No more manual intervention needed!
