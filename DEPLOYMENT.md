# Deployment Guide - Buscador de Pisos

## Changes Made to Fix Render Deployment

### Issues Fixed
1. ✅ Application was exiting after one run (no periodic execution)
2. ✅ Scrapers finding 0 listings without proper debugging
3. ✅ Selenium/Chromium not configured for Render environment
4. ✅ Missing health check endpoint
5. ✅ No visibility into scraper failures

---

## Deployment Checklist

### 1. Pre-Deployment Configuration

#### Set Environment Variables in Render Dashboard

**Required:**
- `RENDER_SERVICE_URL` - Your Render service URL (e.g., `https://your-app.onrender.com`)

**Optional (for notifications):**
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_IDS` - Comma-separated chat IDs
- `SMTP_USERNAME` - Email for notifications
- `SMTP_PASSWORD` - Email password/app password

**Optional (configuration):**
- `SCRAPE_INTERVAL_HOURS` - How often to run (default: 6 hours)
- `ENABLE_SCHEDULER` - Enable/disable automatic runs (default: true)
- `CHROMIUM_PATH` - Path to Chromium (default: /usr/bin/chromium)

#### Enable Notifications (Optional)

Edit `config/config.yaml`:

```yaml
# For Telegram notifications
telegram:
  enabled: true  # Change to true

# For email notifications
email:
  enabled: true  # Change to true
```

#### Enable Debug Logging (Recommended for first deployment)

Edit `config/config.yaml`:

```yaml
logging:
  level: "DEBUG"  # Change from INFO to DEBUG
```

---

### 2. Deploy to Render

#### Option A: Automatic Deployment (Recommended)

1. **Commit changes:**
   ```bash
   git add .
   git commit -m "Fix Render deployment: add scheduled execution and debug logging"
   git push origin main
   ```

2. **Render will automatically deploy** when it detects the push

#### Option B: Manual Deployment

1. Go to Render Dashboard
2. Select your service
3. Click "Manual Deploy" → "Deploy latest commit"

---

### 3. Post-Deployment Testing

#### Immediate Checks (within 2 minutes)

1. **Verify service is running:**
   ```
   https://your-app.onrender.com/health
   ```
   Expected: `OK`

2. **Check server started:**
   In Render logs, you should see:
   ```
   🌐 Servidor iniciado en puerto 8080
   ⏰ Ejecutor periódico iniciado (cada 6h)
   🤖 Ejecutando bot programado - [timestamp]
   ```

#### After 5-10 Minutes

3. **Check bot status:**
   ```
   https://your-app.onrender.com/status
   ```
   Expected JSON response:
   ```json
   {
     "status": "completed",
     "last_run": "2026-01-21T...",
     "last_run_stats": {
       "total_found": 123,
       "new_listings": 5,
       "errors": 0,
       "duration": "0:01:23"
     },
     "start_time": "2026-01-21T...",
     "next_scheduled_run": "2026-01-21T..."
   }
   ```

4. **Review Render logs** for detailed scraping output:
   - Look for "Encontrados X items con selector: [selector]"
   - Check for any "⚠️ No se encontraron anuncios"
   - Verify "✅ Bot completado - X nuevos anuncios"

#### Troubleshooting

If you see `"status": "error"`:
1. Check Render logs for the error message
2. Look for HTTP errors (403, 404, 500)
3. Check if selectors are failing
4. Verify environment variables are set correctly

---

### 4. Monitor First 24 Hours

#### Expected Behavior

- Bot runs immediately on startup
- Then runs every 6 hours (or your configured interval)
- Service stays alive between runs
- Render keeps service active via `/health` checks

#### What to Monitor

1. **Check `/status` endpoint every few hours**
2. **Review logs for patterns:**
   - Are listings being found?
   - Are scrapers completing successfully?
   - Any recurring errors?

3. **Database check:**
   - Listings should accumulate in `data/listings.db`
   - Check for duplicate prevention working

4. **Notifications (if enabled):**
   - Verify you receive Telegram/email when new listings found

---

### 5. Optimization After Initial Testing

#### Once Working

1. **Reduce logging verbosity:**
   ```yaml
   logging:
     level: "INFO"  # Change back from DEBUG
   ```

2. **Adjust scraping interval if needed:**
   - More frequent: `SCRAPE_INTERVAL_HOURS=3`
   - Less frequent: `SCRAPE_INTERVAL_HOURS=12`

3. **Disable failing portals** in `config/config.yaml`:
   ```yaml
   portals:
     portal_name:
       enabled: false  # Disable if consistently failing
   ```

#### If Still Finding 0 Listings

The debug logs will show why. Common causes:

1. **Website blocking:** Status code 403 or 429
   - Solution: Add proxy support or increase delays

2. **Selectors not matching:** "✗ No items con selector: [selector]"
   - Solution: Update CSS selectors in scraper code
   - The logs will show the page structure to help identify correct selectors

3. **Selenium failing:** "No se pudo inicializar Selenium"
   - Solution: Chromium install failed, check build logs

4. **Filters too restrictive:** "X encontrados, 0 nuevos"
   - Solution: Relax filters in `config/filters.yaml`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────┐
│  Render Service (Always Running)                │
│  └─> python server.py                           │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  HTTP Server (Port 8080)                        │
│  ├─ GET /health      → Health check             │
│  ├─ GET /status      → Bot status & stats       │
│  └─ GET /run         → Manual trigger           │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  ScheduledRunner (Background Thread)            │
│  ├─ Runs immediately on startup                 │
│  ├─ Runs every 6 hours (configurable)           │
│  └─ Updates bot_status for /status endpoint     │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  RealEstateBot                                  │
│  ├─ Loads config & filters                      │
│  ├─ For each profile:                           │
│  │   └─ For each portal:                        │
│  │       ├─ Build search URL                    │
│  │       ├─ Scrape listings                     │
│  │       ├─ Filter & save to database           │
│  │       └─ Send notifications if new           │
│  └─ Save stats & cleanup old listings           │
└─────────────────────────────────────────────────┘
```

---

## Manual Testing Commands

### Test Locally Before Deploying

```bash
# Test server with scheduler disabled
ENABLE_SCHEDULER=false python server.py

# In another terminal, trigger manually
curl http://localhost:8080/run

# Check status
curl http://localhost:8080/status
```

### Test Bot Directly

```bash
# Run bot once with debug logging
python main.py --max-pages 1

# Test specific portal
python main.py --portal tucasa --max-pages 1

# Test specific profile
python main.py --profile madrid_centro --max-pages 1

# Test mode (no notifications)
python main.py --test
```

---

## Files Modified

1. **render.yaml** - Changed build and start commands, added Chromium
2. **server.py** - Added ScheduledRunner for periodic execution
3. **scrapers/base_scraper.py** - Enhanced error handling and debug logging
4. **scrapers/tucasa_scraper.py** - Added detailed parsing debug output

---

## Support & Troubleshooting

### Common Issues

**Issue:** Service keeps spinning down
- **Cause:** Render free tier spins down after 15 min inactivity
- **Solution:** Already handled - server responds to health checks

**Issue:** Bot runs but finds 0 listings
- **Cause:** Website selectors changed or blocking
- **Solution:** Check DEBUG logs to see exact failure point

**Issue:** Selenium errors
- **Cause:** Chromium install failed
- **Solution:** Check build logs, may need to disable yaencontre portal temporarily

**Issue:** Out of memory
- **Cause:** Too many scrapers running simultaneously
- **Solution:** Disable some portals or reduce max_pages

---

## Next Steps

After successful deployment:

1. ✅ Monitor first few runs via `/status` endpoint
2. ✅ Verify notifications working (if enabled)
3. ✅ Check database accumulating listings
4. ✅ Adjust filters based on results
5. ✅ Consider upgrading Render plan for more resources if needed

---

## Questions?

Check Render logs for detailed execution information. All scrapers now log:
- URLs being fetched
- HTTP response codes
- CSS selectors tried
- Number of items found
- Parsing errors with context

This makes debugging much easier than before!
