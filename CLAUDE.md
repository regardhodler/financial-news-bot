# Financial News Bot — Claude Code Context

## Project Overview

A GitHub Actions-based bot that scrapes X (Twitter) for high-engagement financial tweets,
scores them with Groq LLaMA, and sends market-moving alerts to Telegram and/or Discord.
Runs every 15 minutes, zero infrastructure, zero cost.

## File Structure

```
financial-news-bot/
├── main.py                              # All bot logic
├── requirements.txt                     # Python dependencies
├── README.md                            # Setup guide for end users
├── CLAUDE.md                            # This file
└── .github/
    └── workflows/
        └── x-financial-news-bot.yml    # GitHub Actions cron workflow
```

## Key Modules & Functions (main.py)

| Function | Purpose |
|----------|---------|
| `login_accounts(api)` | Re-authenticates twscrape pool each run (stateless Actions env) |
| `scrape_tweets(api)` | Runs X search, filters by LOOKBACK_MINUTES window |
| `score_and_summarize(text, url, client)` | Groq LLaMA call → JSON `{impact, summary}` |
| `build_alert_message(tweet, score)` | Formats the final alert string |
| `send_telegram(message)` | POSTs to Telegram Bot API |
| `send_discord(message)` | POSTs to Discord webhook |
| `main()` | Orchestrates: login → scrape → score → alert |

## Config Constants (top of main.py)

| Constant | Default | Purpose |
|----------|---------|---------|
| `SEARCH_QUERY` | Financial keywords + min_faves:300 | X search string |
| `MODEL_ID` | `llama-3.3-70b-versatile` | Groq model |
| `MIN_IMPACT_SCORE` | `8` | Minimum score (1-10) to send alert |
| `MAX_ALERTS` | `5` | Max alerts per bot run |
| `LOOKBACK_MINUTES` | `20` | Tweet age filter (5-min buffer over 15-min cron) |
| `GROQ_RATE_LIMIT_SLEEP` | `2` | Seconds between Groq calls |
| `TELEGRAM_RATE_LIMIT_SLEEP` | `1` | Seconds between Telegram sends |

## Required GitHub Secrets

```
X_ACCOUNT_1_USER, X_ACCOUNT_1_PASS, X_ACCOUNT_1_EMAIL  ← Required
X_ACCOUNT_1_COOKIES  ← Recommended (bypasses Cloudflare; see below)
X_ACCOUNT_2_*  ← Optional (improves reliability)
X_ACCOUNT_3_*  ← Optional
GROQ_API_KEY   ← Required
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID  ← Required for Telegram
DISCORD_WEBHOOK_URL  ← Optional (sends to both if set)
```

### Cookie Auth (Cloudflare fix)

GitHub Actions runners are often blocked by Cloudflare when doing the
username/password login flow on x.com. To bypass this:

1. Log in to X in a browser (Chrome/Firefox)
2. Open DevTools → Application → Cookies → x.com
3. Copy the values of `auth_token` and `ct0`
4. Set the secret: `X_ACCOUNT_1_COOKIES=auth_token=<value>; ct0=<value>`

When `X_ACCOUNT_N_COOKIES` is set for a slot, the bot skips the login
step for that account and uses the cookie session directly.

## How to Extend

### Add more data sources
- **Reddit**: Use `praw` to scrape r/wallstreetbets, r/stocks
- **RSS feeds**: Use `feedparser` for Bloomberg/Reuters RSS
- Scrape each source in parallel with `asyncio.gather()`

### Change the LLM
- Swap `MODEL_ID` to any Groq-supported model (see console.groq.com/docs/models)
- To use OpenAI instead: replace `from groq import Groq` with `from openai import OpenAI`
  (same API interface, just change the client init and model name)

### Add more notification channels
- **Slack**: Use incoming webhooks (same pattern as Discord)
- **Email**: Use `smtplib` with a Gmail app password
- **SMS**: Use Twilio free trial

### Add persistent deduplication
- Store sent tweet IDs in a GitHub Actions cache artifact
- Use `actions/cache@v4` with a key like `tweet-ids-{date}`
- Check IDs before processing to skip already-sent tweets across runs

### Change alert frequency
- Cron expression in `x-financial-news-bot.yml`: `*/15 * * * *`
- Increase `LOOKBACK_MINUTES` proportionally if changing cron interval

## Architecture Notes

**Why no database?**
Timestamp-based lookback makes each run self-contained. A 20-min window on a 15-min cron
gives 5 minutes of overlap to handle edge cases without needing state storage.

**Why re-login every run?**
GitHub Actions runners are ephemeral — the twscrape SQLite session file doesn't persist
between workflow runs. Re-authentication adds ~3-5 seconds but ensures reliability.

**Why httpx sync (not async) for Telegram/Discord?**
Both calls are fire-and-forget with no parallelism needed. Using sync httpx avoids adding
aiohttp as a dependency (twscrape already requires httpx).

**Groq JSON mode**
Using `response_format={"type": "json_object"}` guarantees structured output. This is more
reliable than asking for JSON in the prompt and regex-parsing the response.

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| twscrape | >=0.14.0 | X/Twitter scraping with auth |
| groq | >=0.9.0 | Groq LLaMA API client |
| httpx | >=0.27.0 | HTTP client for Telegram/Discord |

All pure Python — no system dependencies, installs in ~10 seconds on ubuntu-latest.
