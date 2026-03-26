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
    """Same 4-strategy patch as main.py — handles x.com's frequently-changing webpack format."""
    _HASH_PAT = re.compile(r'"?([^":\s{},\[\]]+)"?\s*:\s*"([a-f0-9]{5,10})"')

    def _extract_from_chunk(chunk_text):
        for key, val in _HASH_PAT.findall(chunk_text):
            yield script_url(key, f"{val}a")

    def _patched_get_scripts_list(text):
        # Strategy 1: webpack 4 (e=>e+"."+{...}[e]+"a.js")
        if 'e=>e+"."+' in text and '[e]+"a.js"' in text:
            try:
                chunk = text.split('e=>e+"."+')[1].split('[e]+"a.js"')[0]
                results = list(_extract_from_chunk(chunk))
                if results:
                    yield from results
                    return
            except Exception:
                pass
        # Strategy 2: webpack 5 ({map}[e]||e pattern)
        try:
            m = re.search(r'\{([^{}]{40,})\}\[e\]', text)
            if m:
                results = list(_extract_from_chunk(m.group(1)))
                if results:
                    yield from results
                    return
        except Exception:
            pass
        # Strategy 3: direct ondemand.s.* URL scan
        direct = re.findall(
            r'https://abs\.twimg\.com/responsive-web/client-web/ondemand\.s\.[a-f0-9a-z]+\.js',
            text,
        )
        if direct:
            yield from dict.fromkeys(direct)
            return
        # Strategy 4: all client-web JS chunks as fallback
        yield from dict.fromkeys(re.findall(
            r'https://abs\.twimg\.com/responsive-web/client-web/[a-zA-Z0-9._/-]+\.js',
            text,
        ))

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
