"""Check generated local routes, assets, metadata and distributed source."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import json,zipfile
ROOT=Path(__file__).resolve().parent/'dist'/'prospect'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=[];self.h1=0;self.lang=False;self.viewport=False;self.author=False;self.canonical=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='html':self.lang=a.get('lang') in ('es','en')
  if tag=='h1':self.h1+=1
  if a.get('id'):self.ids.append(a['id'])
  if tag=='meta':self.viewport|=a.get('name')=='viewport';self.author|=a.get('name')=='author' and a.get('content')=='AliceLabs LLC'
  if tag=='link' and a.get('rel')=='canonical':self.canonical=True
  for key in ('href','src'):
   if a.get(key):self.links.append(a[key])
errors=[];pages={}
for path in ROOT.rglob('*.html'):
 page=Page();page.feed(path.read_text());pages[path]=page
 for value in ('lang','viewport','author','canonical'):
  if not getattr(page,value):errors.append(f'{path}: missing {value}')
 if page.h1!=1:errors.append(f'{path}: expected exactly one H1')
 if len(page.ids)!=len(set(page.ids)):errors.append(f'{path}: duplicate id')
 if '{{' in path.read_text():errors.append(f'{path}: unresolved template')
for path,page in pages.items():
 for link in page.links:
  url=urlsplit(link)
  if url.scheme or url.netloc:continue
  dest=(path.parent/unquote(url.path)).resolve() if url.path else path
  if dest.is_dir():dest=dest/'index.html'
  if not dest.is_file():errors.append(f'{path.relative_to(ROOT)}: missing {link}')
  if url.fragment and dest in pages and url.fragment not in pages[dest].ids:errors.append(f'{path.relative_to(ROOT)}: missing anchor {link}')
manifest=json.loads((ROOT/'agent.json').read_text())
assert manifest['publisher']['name']=='AliceLabs LLC'
assert any(c['id']=='public_enrichment' for c in manifest['capabilities'])
assert 'managed_enrichment_backend' in manifest['not_implemented']
with zipfile.ZipFile(ROOT/'downloads/TechDigital-Prospect-6.4-source.zip') as archive:
 names=archive.namelist()
 assert any(n.endswith('/product_identity.py') for n in names)
 assert not any(n.endswith(('.key','.german','/.env')) for n in names)
if errors:raise SystemExit('\n'.join(errors))
print(f'{len(pages)} HTML pages: local links, anchors, author, mobile metadata, manifest and source archive OK')
