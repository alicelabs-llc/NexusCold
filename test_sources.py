"""Test script for enrichment sources"""
import asyncio
import aiohttp
import sys
import re
from urllib.parse import quote_plus

sys.path.insert(0, '.')

async def test_source(name, url):
    try:
        connector = aiohttp.TCPConnector(limit=5, ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url, 
                                   headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                                   timeout=aiohttp.ClientTimeout(total=10),
                                   allow_redirects=True) as r:
                print(f"[{name}] Status: {r.status}")
                text = await r.text(errors='ignore')
                print(f"[{name}] Length: {len(text)}")
                print(f"[{name}] First 400 chars: {text[:400]}")
                print()
    except Exception as e:
        print(f"[{name}] ERROR: {e}\n")

async def main():
    q = quote_plus('"Microsoft Corporation" Redmond WA official website')
    
    await test_source("DDG", f"https://html.duckduckgo.com/html/?q={q}")
    await test_source("Bing", f"https://www.bing.com/search?q={q}&count=10")
    await test_source("Google", f"https://www.google.com/search?q={q}")

if __name__ == "__main__":
    asyncio.run(main())
