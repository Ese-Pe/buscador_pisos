# Troubleshooting Guide - Buscador de Pisos

## Issue: "API Error: Connection error"

This error can appear in different contexts. Let's diagnose:

---

## Diagnostic Steps

### Step 1: Identify WHERE the error appears

Check where you see "API Error: Connection error":

- [ ] **In Render logs** → Bot can't connect to real estate websites
- [ ] **When testing endpoints** → Server not responding
- [ ] **In Telegram** → Telegram bot configuration issue
- [ ] **Other location** → Specify

---

### Step 2: Check if Service is Running

#### A. Check Render Dashboard
1. Go to https://dashboard.render.com
2. Click on your service
3. Look at the status indicator (top right):
   - 🟢 **Live** → Service is running
   - 🟡 **Building** → Wait for deployment to finish
   - 🔴 **Failed** → Check logs for errors

#### B. Test Health Endpoint

Open your browser or use curl:
```bash
curl https://YOUR-SERVICE.onrender.com/health
```

**Expected response:** `OK`

If you get:
- ✅ `OK` → Server is working
- ❌ `404 Not Found` → Wrong URL or service not running
- ❌ `Connection refused` → Service crashed or not started
- ❌ `Timeout` → Service taking too long to respond

---

### Step 3: Check Render Logs

1. Go to Render Dashboard → Your service → **Logs**
2. Look for these indicators:

#### ✅ GOOD - Service Running Correctly:
```
🚀 Iniciando servidor en puerto 10000
📊 Variables de entorno:
   PORT=10000
   SCRAPE_INTERVAL_HOURS=6
   ENABLE_SCHEDULER=true
🌐 Servidor HTTP iniciado correctamente
   Puerto: 10000
   Host: 0.0.0.0 (escuchando en todas las interfaces)
⏰ Ejecutor periódico iniciado (cada 6h)
🤖 Ejecutando bot programado - [timestamp]
```

#### ❌ BAD - Service Issues:
```
==> Application exited early
==> No open ports detected
```

#### ⚠️ CONNECTION ERRORS in Logs:
If you see errors like:
```
ERROR | HTTP error 404 obteniendo https://...
WARNING | No se pudo obtener la página 1
```

This means the **bot can't connect to real estate websites**. Common causes:
1. Website URL format changed
2. Website blocking bot requests (403 Forbidden)
3. Network/firewall issues on Render

---

### Step 4: Test Bot Status Endpoint

```bash
curl https://YOUR-SERVICE.onrender.com/status
```

or open in browser:
```
https://YOUR-SERVICE.onrender.com/status
```

**Good Response:**
```json
{
  "status": "completed",
  "last_run": "2026-01-21T10:30:00",
  "last_run_stats": {
    "total_found": 15,
    "new_listings": 3,
    "errors": 0,
    "duration": "0:01:23"
  },
  "start_time": "2026-01-21T10:00:00",
  "next_scheduled_run": "2026-01-21T16:30:00"
}
```

**Bad Response - Error:**
```json
{
  "status": "error",
  "last_run_stats": {
    "error": "Connection timeout"
  }
}
```

---

## Common Issues & Solutions

### Issue 1: Telegram Notifications Not Working

**Symptom:** Bot runs successfully but no Telegram messages

**Check:**
1. Is Telegram enabled in config?
   ```yaml
   telegram:
     enabled: false  # ← Should be true!
   ```

2. Are environment variables set in Render?
   - Go to Render Dashboard → Settings → Environment
   - Check for:
     - `TELEGRAM_BOT_TOKEN` (set to your bot token)
     - `TELEGRAM_CHAT_IDS` (set to your chat ID)

3. Did the bot find NEW listings?
   - Notifications only sent for NEW listings
   - Check `/status` endpoint → `new_listings` count
   - If `new_listings: 0`, no notifications sent

**Solution:**
```bash
# Enable Telegram in config.yaml
telegram:
  enabled: true

# Set environment variables in Render Dashboard
TELEGRAM_BOT_TOKEN=your_actual_token_here
TELEGRAM_CHAT_IDS=your_chat_id_here

# Then redeploy or manually trigger:
curl https://YOUR-SERVICE.onrender.com/run
```

---

### Issue 2: "No open ports detected"

**Symptom:** Render logs show "No open ports detected"

**Cause:** Server not binding to correct port

**Solution:**
1. Check Render Dashboard → Settings → Start Command
2. Should be: `python server.py` (NOT `python main.py`)
3. Save and redeploy

---

### Issue 3: Bot Finding 0 Listings

**Symptom:** Bot runs but finds 0 listings on all portals

**Causes:**
1. **Website HTML changed** - CSS selectors no longer match
2. **Bot detected** - Websites blocking requests
3. **Filters too strict** - No properties match criteria
4. **URL building broken** - Wrong URLs being generated

**Diagnosis:**
Check logs with DEBUG level enabled:
```yaml
logging:
  level: "DEBUG"
```

Look for:
- `✗ No items con selector: [selector]` → Selectors failing
- `HTTP error 403` → Website blocking
- `HTTP error 404` → Wrong URL format
- `⚠️ No se encontraron anuncios ni enlaces` → No results

**Solutions:**

**For 404 errors (Wrong URLs):**
The generic scrapers (bank portals) may have outdated URL formats.
Temporarily disable failing portals:
```yaml
portals:
  haya:
    enabled: false  # Disable until fixed
  servihabitat:
    enabled: false
  aliseda:
    enabled: false
```

**For 403 errors (Blocking):**
- Increase delays in config.yaml
- Add proxy support (advanced)
- Disable respect_robots_txt

**For selector issues:**
- Update CSS selectors in scraper code
- Check website HTML structure
- May require code changes

---

### Issue 4: Service Keeps Crashing

**Symptom:** Service starts then exits immediately

**Check logs for:**
- Import errors → Missing dependencies
- Configuration errors → Invalid config.yaml
- Permission errors → File access issues

**Solution:**
1. Check requirements.txt has all dependencies
2. Validate config.yaml syntax
3. Check Render logs for specific error

---

## Quick Test Script

Run this locally to test your service:

```bash
python test_service.py
```

Then enter your Render service URL when prompted.

---

## Manual Testing Commands

### Test Health
```bash
curl https://YOUR-SERVICE.onrender.com/health
```

### Test Status
```bash
curl https://YOUR-SERVICE.onrender.com/status | python -m json.tool
```

### Trigger Manual Run
```bash
curl https://YOUR-SERVICE.onrender.com/run
```

### Test Locally
```bash
# Run server locally
python server.py

# In another terminal:
curl http://localhost:8080/health
curl http://localhost:8080/status
```

---

## Get Your Telegram Chat ID

If you don't know your Telegram chat ID:

1. **Message your bot** on Telegram
2. **Get updates:**
   ```bash
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. **Look for** `"chat":{"id":123456789}`
4. **Use that ID** in `TELEGRAM_CHAT_IDS` env var

---

## Enable Telegram Notifications Checklist

- [ ] Create Telegram bot via @BotFather
- [ ] Copy bot token
- [ ] Message your bot on Telegram
- [ ] Get your chat ID (see above)
- [ ] Set `TELEGRAM_BOT_TOKEN` in Render env vars
- [ ] Set `TELEGRAM_CHAT_IDS` in Render env vars
- [ ] Enable in config.yaml: `telegram: enabled: true`
- [ ] Commit and push changes
- [ ] Wait for deployment
- [ ] Trigger manual run to test
- [ ] Check Render logs for "Telegram" messages

---

## Still Having Issues?

Provide this information:
1. Your service URL
2. Output of `/status` endpoint
3. Last 50 lines of Render logs
4. Which error message you're seeing
5. Where you're seeing the error

Then we can diagnose further!
