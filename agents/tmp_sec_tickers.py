import json
import urllib.request

url = 'https://www.sec.gov/files/company_tickers.json'
req = urllib.request.Request(url, headers={'User-Agent': 'OpenClaw research zsj@example.com'})
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.load(r)

want = {'PRVA', 'AGL', 'LFST', 'TALK', 'ADUS', 'OPCH', 'PNTG', 'ASTH', 'PACS', 'EHC', 'ACHC', 'PIII', 'EHAB', 'AAPL'}
private_screen_names = {'ALEDADE', 'CITYBLOCK', 'DISPATCHHEALTH', 'LYRA'}
for rec in data.values():
    ticker = rec['ticker'].upper()
    title = rec['title'].upper()
    if ticker in want or any(name in title for name in private_screen_names):
        print(rec['ticker'], rec['cik_str'], rec['title'])
