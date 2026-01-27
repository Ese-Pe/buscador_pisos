# Telegram Notification Troubleshooting Guide

## Current Status

✅ **Bot IS running successfully**
- Last execution: 2026-01-27 at 08:06 AM
- Found: 40 listings (11 new)
- Next scheduled run: 14:06 (2:06 PM)
- Errors: 0

✅ **Telegram API was called**
- Notification sent to chat ID: `7013249915`
- Message sent at: 08:07:25

❌ **You didn't receive the notification** (Need to fix)

---

## Why You Might Not Have Received Notifications

### 1. Wrong Chat ID
The bot is sending to chat ID `7013249915`. This might not be YOUR chat ID.

**How to find YOUR chat ID:**

1. Open Telegram and find your bot
2. Send `/start` to your bot
3. Visit this URL in your browser (replace `<TOKEN>` with your actual bot token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
4. Look for: `"chat":{"id":XXXXXXX}`
5. That number is your chat ID

### 2. Bot Not Started
You need to send `/start` to your bot in Telegram before it can message you.

**Steps:**
1. Open Telegram
2. Search for your bot by username
3. Click on the bot
4. Send: `/start`
5. You should see a welcome message

### 3. Wrong Bot Token
The `TELEGRAM_BOT_TOKEN` in Render might be incorrect or expired.

**How to verify:**
1. Go to Telegram and find `@BotFather`
2. Send: `/mybots`
3. Select your bot
4. Click "API Token"
5. Copy the token
6. Compare with the one in Render Dashboard → Environment

---

## Quick Test

### Option A: Test from Render Dashboard

1. Go to https://dashboard.render.com/
2. Select your "buscador-pisos" service
3. Go to "Shell" tab
4. Run:
   ```bash
   python test_telegram.py
   ```
5. Check your Telegram app for a test message

### Option B: Trigger a Manual Test

Visit this URL in your browser:
```
https://buscador-pisos.onrender.com/run
```

Then check the logs in Render Dashboard to see if notification was sent.

---

## Fix Steps

### Step 1: Verify Environment Variables on Render

1. Go to https://dashboard.render.com/
2. Select "buscador-pisos" service
3. Click "Environment" tab
4. Verify these variables exist and are correct:

   ```
   TELEGRAM_BOT_TOKEN = <your-bot-token-from-BotFather>
   TELEGRAM_CHAT_IDS = <your-chat-id-from-getUpdates>
   ```

   ⚠️ **ALSO ADD THIS NEW VARIABLE (for keep-alive):**
   ```
   RENDER_SERVICE_URL = https://buscador-pisos.onrender.com
   ```

5. Click "Save Changes" (this will trigger a redeploy)

### Step 2: Get Your Correct Chat ID

**Method 1 - Using Browser:**
1. Send a message to your bot in Telegram (any message)
2. Open browser and go to:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
3. Look for `"chat":{"id":XXXXXXX}` in the JSON response
4. Copy that number - that's your chat ID

**Method 2 - Using Shell on Render:**
1. Go to Render Dashboard → Shell
2. Run:
   ```bash
   curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates
   ```
3. Look for your chat ID in the response

### Step 3: Update Chat ID on Render

1. In Render Dashboard → Environment
2. Edit `TELEGRAM_CHAT_IDS` variable
3. Set it to your correct chat ID (e.g., `123456789`)
4. Save changes

### Step 4: Test Again

After redeployment completes:
1. Go to: https://buscador-pisos.onrender.com/run
2. Wait 30 seconds
3. Check your Telegram app for notification

---

## Verification Checklist

After fixing, verify:

- [ ] Bot token is correct (from @BotFather)
- [ ] Chat ID is YOUR ID (from /getUpdates)
- [ ] You sent `/start` to the bot
- [ ] `RENDER_SERVICE_URL` is set (for keep-alive)
- [ ] Test message received in Telegram
- [ ] Bot shows "next_scheduled_run" in /status endpoint

---

## Expected Result

Once configured correctly, you should receive Telegram messages like this every time new properties are found:

```
🏠 11 Nuevos Pisos Encontrados

📍 Oliver-Valdefierro
💰 220.000€
📐 90 m² | 🛏️ 3 hab | 🚿 1 baño
🔗 [Ver detalles](...)

📍 Centro
💰 315.000€
📐 120 m² | 🛏️ 3 hab | 🚿 2 baños
🔗 [Ver detalles](...)

...
```

---

## Still Not Working?

If you've followed all steps and still not receiving notifications:

1. Check Render logs:
   - Dashboard → Logs
   - Look for "Notificación enviada" or errors

2. Run the test script:
   ```bash
   python test_telegram.py
   ```

3. Check bot permissions:
   - Make sure bot isn't blocked in Telegram
   - Try creating a new bot with @BotFather

4. Report the exact error message from logs
