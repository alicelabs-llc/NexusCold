"""Debug: check actual HTML structure of search results"""
import asyncio
import aiohttp
import re
from urllib.parse import quote_plus, unquote

async def main():
    q = quote_plus('Microsoft Corporation Redmond WA official website')
    
    async with aiohttp.ClientSession() as session:
        # BING
        url = f"https://www.bing.com/search?q={q}&count=10"
        async with session.get(url, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"Bing Status: {r.status}")
            text = await r.text(errors='ignore')
            with open("bing_response.html", "w", encoding="utf-8") as f:
                f.write(text)
            
            # Find all <cite>
            cite_matches = re.findall(r'<cite[^>]*>([^<]+)</cite>', text)
            print(f"Bing <cite> matches: {len(cite_matches)}")
            for u in cite_matches[:5]:
                print(f"  CITE: {u}")

            # Find all <a> in h2
            h2_matches = re.findall(r'<h2><a[^>]+href="([^"]+)"', text)
            print(f"Bing <h2><a> matches: {len(h2_matches)}")
            for u in h2_matches[:5]:
                print(f"  HREF: {u}")

        # GOOGLE
        url = f"https://www.google.com/search?q={q}"
        async with session.get(url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"},
            timeout=aiohttp.ClientTimeout(total=10)) as r:
            print(f"\nGoogle Status: {r.status}")
            text = await r.text(errors='ignore')
            with open("google_response.html", "w", encoding="utf-8") as f:
                f.write(text)
            
            # Find all /url?q=
            url_matches = re.findall(r'href="/url\?q=([^&]+)', text)
            print(f"Google /url?q= matches: {len(url_matches)}")
            for u in url_matches[:5]:
                print(f"  URL: {unquote(u)}")

if __name__ == "__main__":
    asyncio.run(main())
