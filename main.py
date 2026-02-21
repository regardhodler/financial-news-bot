"""
Personal AI Financial News Bot
Scrapes X (Twitter) → Groq LLaMA → Telegram/Discord alerts
Runs on GitHub Actions every 15 minutes, 100% free, zero infra.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta

import httpx
from groq import Groq
from twscrape import API

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG BLOCK — Edit these constants to customize the bot's behavior
# ─────────────────────────────────────────────────────────────────────────────

# X search query: financial/trading keywords with engagement filter
# Adjust min_faves to raise/lower the engagement bar (default: 300 likes)
SEARCH_QUERY = (
    '(earnings OR "rate cut" OR "Federal Reserve" OR "hedge fund" OR "short squeeze" '
    'OR $NVDA OR $TSLA OR $SPY OR $BTC OR $ETH OR "market crash" OR "all-time high" '
    'OR "IPO" OR "bank failure" OR "CPI" OR "inflation") '
    "min_faves:300 lang:en -filter:replies -filter:retweets"
)

# Groq model to use for scoring and summarization
# Options: llama-3.3-70b-versatile, llama-3.1-8b-instant (faster/cheaper)
MODEL_ID = "llama-3.3-70b-versatile"

# Minimum Groq impact score (1-10) required to send an alert
# Raise to 9 for only truly major events; lower to 7 for more frequent alerts
MIN_IMPACT_SCORE = 8

# Maximum alerts to send per bot run (prevents Telegram spam on busy news days)
MAX_ALERTS = 5

# How many minutes back to search for tweets (5-min buffer over 15-min cron)
# This small overlap ensures no tweets fall through the gap between runs
LOOKBACK_MINUTES = 20

# Seconds to pause between Groq API calls (free tier: 30 req/min = 2s min gap)
GROQ_RATE_LIMIT_SLEEP = 2

# Seconds to pause between Telegram sends (flood control: max 1 msg/sec)
TELEGRAM_RATE_LIMIT_SLEEP = 1

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP — structured output for readable GitHub Actions logs
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# X ACCOUNT SETUP — re-login each run (GitHub Actions has no persistent fs)
# ─────────────────────────────────────────────────────────────────────────────

async def login_accounts(api: API) -> int:
    """
    Add up to 3 X accounts to the twscrape pool and log them in.
    Returns the number of accounts successfully added.
    Returns 0 if no credentials are configured.
    """
    accounts_added = 0

    for i in range(1, 4):
        username = os.getenv(f"X_ACCOUNT_{i}_USER", "").strip()
        password = os.getenv(f"X_ACCOUNT_{i}_PASS", "").strip()
        email = os.getenv(f"X_ACCOUNT_{i}_EMAIL", "").strip()

        if not (username and password and email):
            continue  # Skip unconfigured slots

        try:
            await api.pool.add_account(username, password, email, email)
            log.info(f"[X Auth] Added account slot {i}: @{username}")
            accounts_added += 1
        except Exception as e:
            log.warning(f"[X Auth] Failed to add account {i} (@{username}): {e}")

    if accounts_added == 0:
        log.error("[X Auth] No valid X accounts configured. Set X_ACCOUNT_1_* secrets.")
        return 0

    try:
        await api.pool.login_all()
        log.info(f"[X Auth] Logged in {accounts_added} account(s) successfully.")
    except Exception as e:
        log.error(f"[X Auth] Login failed: {e}")
        return 0

    return accounts_added


# ─────────────────────────────────────────────────────────────────────────────
# TWEET SCRAPING — search X and filter to the lookback window
# ─────────────────────────────────────────────────────────────────────────────

async def scrape_tweets(api: API) -> list[dict]:
    """
    Search X using SEARCH_QUERY and return tweets from the last LOOKBACK_MINUTES.
    Each returned dict has: id, text, url, created_at, author, likes.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOOKBACK_MINUTES)
    log.info(f"[Scrape] Searching tweets since {cutoff.strftime('%H:%M:%S')} UTC")

    tweets = []
    try:
        async for tweet in api.search(SEARCH_QUERY, limit=50):
            # Filter to the lookback window
            tweet_time = tweet.date  # twscrape returns tz-aware datetime
            if tweet_time < cutoff:
                continue

            tweet_data = {
                "id": tweet.id,
                "text": tweet.rawContent,
                "url": f"https://x.com/{tweet.user.username}/status/{tweet.id}",
                "created_at": tweet_time,
                "author": tweet.user.username,
                "likes": tweet.likeCount,
            }
            tweets.append(tweet_data)
            log.info(
                f"[Scrape] Found: @{tweet.user.username} | "
                f"{tweet.likeCount} likes | {tweet_time.strftime('%H:%M')} UTC"
            )
    except Exception as e:
        log.error(f"[Scrape] Search failed: {e}")

    log.info(f"[Scrape] {len(tweets)} tweet(s) in lookback window.")
    return tweets


# ─────────────────────────────────────────────────────────────────────────────
# GROQ SCORING — ask LLaMA to score market impact and summarize
# ─────────────────────────────────────────────────────────────────────────────

def score_and_summarize(tweet_text: str, tweet_url: str, groq_client: Groq) -> dict | None:
    """
    Send tweet text to Groq LLaMA for market-impact scoring.
    Returns dict with 'impact' (int 1-10) and 'summary' (str), or None on error.

    Only returns a result if impact >= MIN_IMPACT_SCORE.
    """
    prompt = f"""You are a professional financial analyst. Analyze this tweet and respond with ONLY a JSON object.

Tweet:
{tweet_text}

Rate the market-moving impact on a scale of 1-10:
- 9-10: Massive, immediate market impact (Fed rate decision, major bank failure, earnings surprise >10%)
- 7-8: Significant impact (major company news, CPI beat/miss, large fund moves)
- 5-6: Moderate relevance (sector news, analyst upgrades, minor economic data)
- 1-4: Low impact (opinion, speculation, minor news, repeats of known info)

Respond with ONLY this JSON (no markdown, no explanation):
{{"impact": <integer 1-10>, "summary": "<one crisp sentence describing the market event>"}}"""

    try:
        response = groq_client.chat.completions.create(
            model=MODEL_ID,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,  # Low temperature for consistent, factual scoring
            max_tokens=150,
        )
        raw = response.choices[0].message.content.strip()
        result = json.loads(raw)

        impact = int(result.get("impact", 0))
        summary = str(result.get("summary", "")).strip()

        log.info(f"[Groq] Score: {impact}/10 | {summary[:80]}...")
        return {"impact": impact, "summary": summary}

    except json.JSONDecodeError as e:
        log.warning(f"[Groq] JSON parse error: {e} | Raw: {raw[:200]}")
        return None
    except Exception as e:
        log.warning(f"[Groq] API error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ALERT FORMATTING — build the message sent to Telegram/Discord
# ─────────────────────────────────────────────────────────────────────────────

def build_alert_message(tweet: dict, score: dict) -> str:
    """
    Format a tweet + Groq score into a clean alert message.
    Extracts cashtags/hashtags for the tags line.
    """
    impact = score["impact"]
    summary = score["summary"]
    url = tweet["url"]
    ts = tweet["created_at"].strftime("%Y-%m-%d %H:%M UTC")

    # Extract cashtags ($NVDA) and hashtags (#CPI) from tweet text
    cashtags = re.findall(r"\$[A-Z]{1,5}", tweet["text"])
    hashtags = re.findall(r"#\w+", tweet["text"])
    tags = " ".join(dict.fromkeys(cashtags + hashtags))[:100]  # dedupe, limit length
    tags_line = f"📊 {tags}" if tags else ""

    lines = [
        f"🚨 [IMPACT {impact}/10] {summary}",
        "",
        f"🔗 {url}",
        f"🕒 {ts}",
    ]
    if tags_line:
        lines.append(tags_line)

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# TELEGRAM — send alert via Bot API
# ─────────────────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    """
    Send a message to the configured Telegram chat/channel.
    Returns True on success, False on failure.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not (token and chat_id):
        log.warning("[Telegram] Skipping — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    try:
        response = httpx.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            log.info("[Telegram] Alert sent successfully.")
            return True
        else:
            log.error(f"[Telegram] Failed ({response.status_code}): {response.text[:200]}")
            return False
    except Exception as e:
        log.error(f"[Telegram] Request error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# DISCORD — send alert via webhook (optional fallback)
# ─────────────────────────────────────────────────────────────────────────────

def send_discord(message: str) -> bool:
    """
    Send a message to the configured Discord webhook.
    Returns True on success, False on failure.
    """
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

    if not webhook_url:
        return False  # Silently skip — Discord is optional

    payload = {"content": message, "username": "Financial News Bot"}

    try:
        response = httpx.post(webhook_url, json=payload, timeout=10)
        if response.status_code in (200, 204):
            log.info("[Discord] Alert sent successfully.")
            return True
        else:
            log.error(f"[Discord] Failed ({response.status_code}): {response.text[:200]}")
            return False
    except Exception as e:
        log.error(f"[Discord] Request error: {e}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ORCHESTRATION
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    log.info("=" * 60)
    log.info("Financial News Bot starting up")
    log.info(f"Config: MIN_IMPACT={MIN_IMPACT_SCORE} | MAX_ALERTS={MAX_ALERTS} | LOOKBACK={LOOKBACK_MINUTES}min")
    log.info("=" * 60)

    # ── Step 1: Validate required secrets ─────────────────────────────────────
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        log.error("GROQ_API_KEY not set. Aborting.")
        return

    # ── Step 2: Login to X accounts ────────────────────────────────────────────
    api = API()
    accounts = await login_accounts(api)
    if accounts == 0:
        log.error("No X accounts available. Aborting.")
        return

    # ── Step 3: Scrape tweets ──────────────────────────────────────────────────
    tweets = await scrape_tweets(api)
    if not tweets:
        log.info("[Main] No tweets found in lookback window. Nothing to process.")
        log.info("=" * 60)
        return

    # ── Step 4: Score with Groq, send qualifying alerts ────────────────────────
    groq_client = Groq(api_key=groq_api_key)
    alerts_sent = 0
    seen_ids = set()

    for tweet in tweets:
        if alerts_sent >= MAX_ALERTS:
            log.info(f"[Main] Reached MAX_ALERTS ({MAX_ALERTS}). Stopping.")
            break

        # Deduplicate (shouldn't happen, but be safe)
        if tweet["id"] in seen_ids:
            continue
        seen_ids.add(tweet["id"])

        log.info(f"[Main] Processing tweet {tweet['id']} by @{tweet['author']}")

        # Rate-limit pause before Groq call
        await asyncio.sleep(GROQ_RATE_LIMIT_SLEEP)

        score = score_and_summarize(tweet["text"], tweet["url"], groq_client)

        if score is None:
            log.info(f"[Main] Skipping tweet {tweet['id']} — Groq returned no result.")
            continue

        if score["impact"] < MIN_IMPACT_SCORE:
            log.info(
                f"[Main] Skipping tweet {tweet['id']} — "
                f"impact {score['impact']}/10 < threshold {MIN_IMPACT_SCORE}."
            )
            continue

        # Build and send alert
        message = build_alert_message(tweet, score)
        log.info(f"[Main] Sending alert for tweet {tweet['id']} (impact {score['impact']}/10)...")

        tg_ok = send_telegram(message)
        dc_ok = send_discord(message)

        if tg_ok or dc_ok:
            alerts_sent += 1
            log.info(f"[Main] Alert #{alerts_sent} sent (Telegram={tg_ok}, Discord={dc_ok}).")

        # Telegram flood control
        await asyncio.sleep(TELEGRAM_RATE_LIMIT_SLEEP)

    # ── Step 5: Summary ────────────────────────────────────────────────────────
    log.info("=" * 60)
    if alerts_sent == 0:
        log.info("[Main] No qualifying alerts this run. Markets are quiet (or threshold is high).")
    else:
        log.info(f"[Main] Done. {alerts_sent} alert(s) sent this run.")
    log.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
