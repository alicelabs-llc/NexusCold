"""Debug: check actual HTML structure of search results"""
import asyncio
import aiohttp
import re
from urllib.parse import quote_plus

async def main():
    q = quote_plus('Microsoft Corporation Redmond WA')
    
    async with aiohttp.ClientSession() as session:
        url = f"https://html.duckduckgo.com/html/?q={q}"
        async with session.get(url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            text = await r.text(errors='ignore')
            
            # Find all result__url occurrences
            url_matches = re.findall(r'class="result__url"[^>]*>([^<]+)<', text)
            print(f"DDG result__url matches: {len(url_matches)}")
            for u in url_matches[:5]:
                print(f"  URL: {u.strip()}")
            
            # Find all <a> with href
            all_links = re.findall(r'<a[^>]+href="(https?://[^"]+)"', text)
            print(f"\nAll <a href> matches: {len(all_links)}")
            for a in all_links[:10]:
                print(f"  HREF: {a}")

if __name__ == "__main__":
    asyncio.run(main())
