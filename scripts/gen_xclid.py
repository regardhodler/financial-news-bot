"""
Generate XCLID_VK_BYTES and XCLID_ANIM_KEY for GitHub Actions secrets.

Run this locally (NOT on GitHub Actions) — your local IP gets real x.com HTML:

    python scripts/gen_xclid.py

Then copy the output values into GitHub Actions secrets:
    Settings → Secrets and variables → Actions → New repository secret

Re-run whenever search stops working (x.com redeployed their JS bundle).
"""

import asyncio
import json
import sys

try:
    from twscrape.xclid import XClIdGen
except ImportError:
    print("ERROR: twscrape not installed. Run: pip install twscrape==0.17.0")
    sys.exit(1)


async def main():
    print("Fetching x.com/tesla to extract XClientTxId parameters...")
    print("(This requires a real residential/browser IP — run locally, not on CI)\n")

    try:
        gen = await XClIdGen.create()
    except Exception as e:
        print(f"ERROR: Failed to generate XClIdGen: {e}")
        print("\nMake sure you're running this locally and can access x.com.")
        sys.exit(1)

    vk_bytes_json = json.dumps(gen.vk_bytes)
    anim_key = gen.anim_key

    print("=" * 60)
    print("Add these as GitHub Actions secrets:\n")
    print(f"Secret name:  XCLID_VK_BYTES")
    print(f"Secret value: {vk_bytes_json}\n")
    print(f"Secret name:  XCLID_ANIM_KEY")
    print(f"Secret value: {anim_key}")
    print("=" * 60)
    print("\nThese values are valid until x.com redeploys their frontend.")
    print("Re-run this script if search stops returning results.")


if __name__ == "__main__":
    asyncio.run(main())
