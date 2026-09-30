"""简道云校内请假核实（凭据来自环境变量，模板见 .env.example）"""
import httpx, json, os
key = os.environ.get("JDY_API_KEY", "")
h = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
url = f"https://api.jiandaoyun.com/api/v2/app/{os.environ.get('JDY_APP_ID', '')}/entry/{os.environ.get('JDY_ENTRY_ID', '')}/data"

all_items=[]
skip=0
while True:
    r=httpx.post(url,headers=h,json={'limit':200,'skip':skip,'filter':{'rel':'and','cond':[
        {'field':'xuejie','type':'text','method':'eq','value':['27']}
    ]}},timeout=15)
    batch=r.json().get('data',[])
    if not batch: break
    all_items.extend(batch)
    skip+=len(batch)
print(f'27届总{len(all_items)}条')

today='2026/07/29'
valid=[]
no_bzr=[]; no_fdy=[]; no_am=[]
for i in all_items:
    xnrq=str(i.get('xnrq','') or '')
    xnsd=str(i.get('xnsd','') or '')
    bzr=str(i.get('userbzr','') or '')
    fdy=str(i.get('userfdy','') or '')
    if xnrq!=today: continue
    if '上午' not in xnsd: no_am.append(i); continue
    if bzr!='同意': no_bzr.append(i); continue
    if fdy!='同意': no_fdy.append(i); continue
    valid.append(i)

print(f'\n校内请假 上午: {len(valid)}人(符合条件)')
print(f'  xnrq={today}总数: {len(valid)+len(no_am)+len(no_bzr)+len(no_fdy)}')
print(f'  非上午: {len(no_am)}, bzr≠同意: {len(no_bzr)}, fdy≠同意: {len(no_fdy)}')

for i in valid:
    print(f'  [{i.get("xuehao")}] {i.get("name")}')

if no_bzr:
    print(f'\nbzr≠同意:')
    for i in no_bzr: print(f'  [{i.get("xuehao")}] {i.get("name")} bzr={i.get("userbzr")}')
if no_fdy:
    print(f'\nfdy≠同意:')
    for i in no_fdy: print(f'  [{i.get("xuehao")}] {i.get("name")} fdy={i.get("userfdy")}')
