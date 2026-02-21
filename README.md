# Personal AI Financial News Bot

A fully automated, 100% free financial news agent that:
1. **Scrapes X (Twitter)** every 15 minutes for high-engagement financial posts
2. **Filters with Groq LLaMA 3.3** — only truly market-moving events (impact ≥ 8/10)
3. **Delivers clean alerts** to Telegram (and optionally Discord)
4. **Runs on GitHub Actions** — no servers, no costs, forever

**Example alert:**
```
🚨 [IMPACT 9/10] Federal Reserve surprises markets with emergency 50bps rate cut.

🔗 https://x.com/user/status/123456
🕒 2026-02-20 14:32 UTC
📊 $SPY $QQQ #Fed #ratecut
```

---

## Prerequisites

- GitHub account (free)
- Telegram account + app
- Groq account (free at [console.groq.com](https://console.groq.com))
- 1–3 X (Twitter) accounts (burner accounts recommended)

---

## Step 1: Push the Code to GitHub

```bash
cd financial-news-bot
git init
git add .
git commit -m "Initial commit: X financial news bot"
git branch -M main
git remote add origin https://github.com/regardhodler/financial-news-bot.git
git push -u origin main
```

Then verify it's live at: **https://github.com/regardhodler/financial-news-bot**

---

## Step 2: Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts:
   - Choose a name: e.g. `My Finance Bot`
   - Choose a username: e.g. `myfinance_alerts_bot`
3. BotFather sends you a **Bot Token** — save it (looks like `7123456789:AAFxxx...`)

**Get your Chat ID:**
1. Create a new Telegram channel (or use an existing group)
2. Add your bot as an **Administrator** of the channel
3. Send a message to the channel, then visit:
   ```
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. Find `"chat":{"id":` in the JSON — copy that number (may be negative for channels, e.g. `-1001234567890`)

---

## Step 3: Get a Groq API Key

1. Go to [console.groq.com](https://console.groq.com) and sign up (free)
2. Navigate to **API Keys** → **Create API Key**
3. Copy the key (starts with `gsk_...`)

The free tier allows ~30 requests/minute and is more than sufficient for this bot.

---

## Step 4: Set Up X Accounts

**Why you need X accounts:** `twscrape` authenticates as a real user to bypass rate limits.

**Recommended:** Create 1–3 dedicated "burner" X accounts for the bot.

For each account, note:
- **Username** (without @)
- **Password**
- **Email address** used to register

> **Tip:** Use email aliases (e.g., Gmail's `+` trick: `yourname+bot1@gmail.com`) so you don't need multiple email accounts.

---

## Step 5: Add GitHub Secrets

Go to your repo on GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add each of the following:

| Secret Name | Description | Required |
|-------------|-------------|----------|
| `X_ACCOUNT_1_USER` | X username (no @) | Yes |
| `X_ACCOUNT_1_PASS` | X password | Yes |
| `X_ACCOUNT_1_EMAIL` | X account email | Yes |
| `X_ACCOUNT_2_USER` | Second X username | No |
| `X_ACCOUNT_2_PASS` | Second X password | No |
| `X_ACCOUNT_2_EMAIL` | Second X email | No |
| `X_ACCOUNT_3_USER` | Third X username | No |
| `X_ACCOUNT_3_PASS` | Third X password | No |
| `X_ACCOUNT_3_EMAIL` | Third X email | No |
| `GROQ_API_KEY` | From console.groq.com | Yes |
| `TELEGRAM_BOT_TOKEN` | From @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your channel/group ID | Yes |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL | No |

---

## Step 6: Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. If prompted, click **"I understand my workflows, go ahead and enable them"**
3. The workflow will automatically run every 15 minutes via cron

---

## Step 7: Test Manually

1. Go to **Actions** tab → select **"X Financial News Bot"** workflow
2. Click **"Run workflow"** → **"Run workflow"** (green button)
3. Watch the live logs — you should see:
   - `[X Auth] Logged in X account(s) successfully.`
   - `[Scrape] Found: @username | 500 likes | 14:32 UTC`
   - `[Groq] Score: 9/10 | Federal Reserve surprises...`
   - `[Telegram] Alert sent successfully.`
4. Check your Telegram channel for the formatted alert

---

## Customization

### Change the search query

Edit `SEARCH_QUERY` in `main.py`:
```python
SEARCH_QUERY = (
    '($AAPL OR $MSFT OR earnings) '
    'min_faves:500 lang:en -filter:replies -filter:retweets'
)
```

### Adjust alert frequency / sensitivity

```python
MIN_IMPACT_SCORE = 8  # Lower to 7 for more alerts, raise to 9 for only major events
MAX_ALERTS = 5        # Max alerts per 15-min run
LOOKBACK_MINUTES = 20 # How far back to look (keep slightly above cron interval)
```

### Change the AI model

```python
MODEL_ID = "llama-3.3-70b-versatile"  # Best quality
# MODEL_ID = "llama-3.1-8b-instant"   # Faster, slightly less accurate
```

### Run more or less frequently

Edit `.github/workflows/x-financial-news-bot.yml`:
```yaml
schedule:
  - cron: '*/30 * * * *'  # Every 30 minutes
  # - cron: '*/5 * * * *'  # Every 5 minutes (aggressive, may hit rate limits)
```

### Add Discord alerts

Set the `DISCORD_WEBHOOK_URL` secret:
1. Go to your Discord server → channel settings → **Integrations** → **Webhooks**
2. Create a webhook and copy the URL
3. Add it as a GitHub Secret

The bot sends to **both** Telegram and Discord simultaneously if both are configured.

---

## Troubleshooting

**"No valid X accounts configured"**
- Verify all three `X_ACCOUNT_1_*` secrets are set in GitHub
- Check for typos in username/password/email

**"No tweets found in lookback window"**
- The search query may be too restrictive right now — try during market hours (9am–4pm ET)
- Lower `min_faves` in the query from 300 to 100 for testing

**"No qualifying alerts" even with tweets found**
- Markets may genuinely be quiet
- Temporarily lower `MIN_IMPACT_SCORE` to 6 to verify Groq scoring is working

**Groq API errors**
- Check your API key is valid at console.groq.com
- The free tier may briefly throttle during heavy load — the bot will retry next run

**Telegram "Forbidden" or "Chat not found"**
- Ensure the bot is an Administrator in the channel
- Re-verify `TELEGRAM_CHAT_ID` (channels use negative IDs like `-1001234567890`)

**X login failing**
- X occasionally updates auth — check [twscrape releases](https://github.com/vladkens/twscrape) for updates
- Try a fresh burner account if existing accounts get flagged

---

## Cost Breakdown

| Component | Cost |
|-----------|------|
| GitHub Actions | Free (2,000 min/month; bot uses ~3 min/run × 96 runs/day = 288 min/day — within free tier for public repos; unlimited for public) |
| Groq API | Free tier: 30 req/min, 14,400 req/day |
| Telegram Bot API | Free, unlimited |
| Discord Webhooks | Free, unlimited |
| X / twscrape | Free (uses your own account credentials) |
| **Total** | **$0/month** |

> **Public repos** get unlimited GitHub Actions minutes. Keep this repo private if you want (uses 2,000 min/month free allowance).

---

## Architecture

```
GitHub Actions (cron every 15 min)
  └─> main.py
       ├─ twscrape (async) → X search API (last 20 min window)
       │    └─ Filters by timestamp, returns tweet text + metadata
       ├─ Groq API (llama-3.3-70b-versatile)
       │    └─ Scores market impact 1-10, generates one-sentence summary
       │    └─ Only proceeds if impact ≥ MIN_IMPACT_SCORE (default: 8)
       └─ Telegram Bot API + Discord Webhook
            └─ Sends formatted alert with impact score, summary, link, tags
```

**Design decisions:**
- **No database** — timestamp-based 20-min lookback window makes each run idempotent
- **Re-login every run** — GitHub Actions has no persistent filesystem
- **asyncio.sleep** for rate limiting — respects Groq free tier (30 req/min)
- **Forced JSON mode** in Groq — reliable structured output, no regex parsing
