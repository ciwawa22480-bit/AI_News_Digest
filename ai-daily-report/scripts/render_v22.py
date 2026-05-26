#!/usr/bin/env python3
"""V2.2 render script template with G0.6/G0.7/G0.8 hardened gates.

Usage:
    REPORT_DATE=YYYY-MM-DD python3 render_v22.py

Reads from /data/userdata/daily-report/data/{00-newsletter,01-chinese,02-english}.json
Writes to /data/userdata/daily-report/output/daily-report.{md,csv}
"""
import json, csv, os, sys, re, random
from concurrent.futures import ThreadPoolExecutor
import urllib.request, ssl
from collections import defaultdict, Counter

REPORT_DATE = os.environ.get('REPORT_DATE') or sys.exit('Set REPORT_DATE env var')
DATA = '/data/userdata/daily-report/data'
OUT  = '/data/userdata/daily-report/output'
QUARANTINE = '/data/userdata/daily-report/quarantine'
os.makedirs(OUT, exist_ok=True)
os.makedirs(QUARANTINE, exist_ok=True)

# A class only - B class requires gate-passing
A_SOURCES = ['00-newsletter.json', '01-chinese.json', '02-english.json']

items = []
for fn in A_SOURCES:
    p = f'{DATA}/{fn}'
    if not os.path.exists(p): continue
    d = json.load(open(p))
    for it in (d if isinstance(d, list) else d.get('items', [])):
        it['_src'] = fn
        items.append(it)

# ===== G0.7 时效闸门 =====
violations = [it for it in items if it.get('date') != REPORT_DATE]
if violations:
    print(f'❌ G0.7 ABORT: {len(violations)} items not dated {REPORT_DATE}')
    for v in violations[:10]:
        print(f'  [{v.get("date","NO_DATE")}] {v.get("_src")} | {v.get("title","")[:60]}')
    sys.exit(1)
print(f'✅ G0.7 PASS: {len(items)} items dated {REPORT_DATE}')

# ===== G0.8 版本号真实性抽检 =====
VERSION_BLACKLIST = ['豆包 1.7', '豆包1.7', 'Claude Sonnet 4.5 Turbo', 'DeepSeek-V3.5',
                     'Mixtral 4.0', 'Gemini 3.5 Pro', '通义万相 2.5', '文心 5.0',
                     'GLM-5.2', '混元 3D 2.0', 'Runway Gen-5', 'Perplexity Comet 2.0']
removed = []
for it in list(items):
    title = it.get('title','') + ' ' + it.get('summary','')
    for bad in VERSION_BLACKLIST:
        if bad in title:
            items.remove(it)
            removed.append((bad, it.get('title','')[:60]))
            break
if removed:
    print(f'⚠️ G0.8 removed {len(removed)} hallucinated-version items:')
    for b,t in removed: print(f'  [{b}] {t}')
else:
    print(f'✅ G0.8 PASS: no blacklisted version numbers')

# ===== G0.6 URL 实拨 =====
SYNTHETIC = [r'xinzhiyuan\.com', r'qbitai\.com/2026/', r'jiqizhixin\.com/articles/2026-',
             r'geekpark\.net/news/3465\d{2}', r'36kr\.com/p/321\d{4}',
             r'caixin\.com/2026-', r'xinhuanet\.com/tech/2026',
             r'latepost\.com/news/dj_detail\?id=27\d{2}',
             r'x\.com/.+/status/19268\d{8}', r'x\.com/.+/status/19269\d{8}']
PAYWALL = ['wsj.com','bloomberg.com','nytimes.com','ft.com','theinformation.com','producthunt.com']
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

def check(url):
    if not url or not url.startswith('http'): return 'no_url'
    for p in SYNTHETIC:
        if re.search(p, url): return 'synthetic'
    for d in PAYWALL:
        if d in url: return 'paywall'
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'}, method='GET')
        with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
            return 'ok' if 200<=r.status<400 else 'http_err'
    except Exception as e:
        if hasattr(e,'code') and e.code in (401,403): return 'paywall'
        return 'unreachable'

with ThreadPoolExecutor(max_workers=12) as ex:
    cats = list(ex.map(check, [it.get('url','') for it in items]))
for it, cat in zip(items, cats):
    it['_url_cat'] = cat
    if cat in ('synthetic','unreachable','http_err'):
        it['url'] = ''
        it['_fact'] = 'URL已替换'
    elif cat == 'paywall':
        it['_fact'] = '付费墙'
    else:
        it['_fact'] = '一手信源'

url_counts = Counter(it['_url_cat'] for it in items)
print(f'✅ G0.6 URL: {dict(url_counts)}')

# Validation report
json.dump({'date':REPORT_DATE,'total':len(items),'counts':dict(url_counts)},
          open(f'{DATA}/09-url-validation.json','w'), ensure_ascii=False, indent=2)

# ===== Render (delegate to existing render logic) =====
print(f'✅ Gates passed. {len(items)} items ready for render.')
print(f'   Next: invoke render_md.py / render_csv.py with these gated items.')
