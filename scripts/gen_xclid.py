"""
Generate XCLID_VK_BYTES and XCLID_ANIM_KEY for GitHub Actions secrets.

Run this locally:
    python scripts/gen_xclid.py

Then copy the output values into GitHub Actions secrets (optional — the bot
now patches twscrape automatically, so these secrets are only needed if you
want to skip the x.com page fetch entirely on each run).
"""

import asyncio
import json
import re
import sys

try:
    import twscrape.xclid as _xclid
    from twscrape.xclid import XClIdGen, script_url
except ImportError:
    print("ERROR: twscrape not installed. Run: pip install twscrape==0.17.0")
    sys.exit(1)


def _apply_patch():
    """Same patch as in main.py — handles x.com's unquoted JS keys."""
    def _patched_get_scripts_list(text: str):
        try:
            chunk = text.split('e=>e+"."+')[1].split('[e]+"a.js"')[0]
        except (IndexError, Exception):
            return
        for key, val in re.findall(r'"?([^":\s{},]+)"?\s*:\s*"([a-f0-9]{5,10})"', chunk):
            yield script_url(key, f"{val}a")

    _xclid.get_scripts_list = _patched_get_scripts_list


async def main():
    _apply_patch()

    print("Fetching x.com/tesla to extract XClientTxId parameters...\n")
    try:
        gen = await XClIdGen.create()
    except Exception as e:
        print(f"ERROR: Failed to generate XClIdGen: {e}")
        sys.exit(1)

    vk_bytes_json = json.dumps(gen.vk_bytes)
    anim_key = gen.anim_key

    print("=" * 60)
    print("Add these as GitHub Actions secrets (optional):\n")
    print(f"Secret name:  XCLID_VK_BYTES")
    print(f"Secret value: {vk_bytes_json}\n")
    print(f"Secret name:  XCLID_ANIM_KEY")
    print(f"Secret value: {anim_key}")
    print("=" * 60)
    print("\nNote: the bot auto-patches twscrape and works without these secrets.")
    print("Set them only to skip the x.com page fetch on each GitHub Actions run.")


if __name__ == "__main__":
    asyncio.run(main())
