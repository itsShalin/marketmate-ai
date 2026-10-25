"""Run with seed, restart service, then run and inspect."""
import argparse
import json
import requests
from dotenv import load_dotenv
import os
load_dotenv()

p=argparse.ArgumentParser()
p.add_argument('action', choices=['seed','run','inspect'])
p.add_argument('--url', default='http://127.0.0.1:8001')
p.add_argument('--business', default='biz_001')
p.add_argument('--sample', action='store_true', help='Use sample backend data; model mode still follows .env')
p.add_argument('--timeout', type=float, default=None, help='Client wait in seconds; defaults to RUN_TIMEOUT_S + 60')
a=p.parse_args()
client_timeout = a.timeout if a.timeout is not None else float(os.getenv('RUN_TIMEOUT_S', '240')) + 60
if a.action=='seed':
    r=requests.post(a.url+'/memory',json={'business_id':a.business,'key':'promotion_policy','content':'Avoid discounts. Use a premium, friendly tone for marketing posts.'}, timeout=30)
elif a.action=='run':
    r=requests.post(a.url+'/run',json={'businessId':a.business,'request':'Create two promotional posts that follow our saved brand preferences.','sample_mode':a.sample},timeout=client_timeout)
else:
    r=requests.get(a.url+'/memory',params={'business_id':a.business},timeout=30)
r.raise_for_status()
print(json.dumps(r.json(),indent=2,ensure_ascii=False))
