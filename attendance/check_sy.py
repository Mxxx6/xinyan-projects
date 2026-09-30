import httpx, os
key = os.environ.get("JDY_API_KEY", "")
h = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
url = f"https://api.jiandaoyun.com/api/v2/app/{os.environ.get('JDY_APP_ID', '')}/entry/{os.environ.get('JDY_ENTRY_ID', '')}/data"
r=httpx.post(url,headers=h,json={'limit':10,'filter':{'rel':'and','cond':[
    {'field':'xuejie','type':'text','method':'eq','value':['27']},
    {'field':'xuehao','type':'text','method':'eq','value':['271664']},
]}},timeout=10)
items=r.json().get('data',[])
for i in items:
    xj=i.get('timexiaojia')
    lx=i.get('lxrq','')[:16] if i.get('lxrq') else '-'
    fx=i.get('fxrq','')[:16] if i.get('fxrq') else '-'
    print(f'[{i.get("xuehao")}] {i.get("name")} fl={i.get("userfenlei")}')
    print(f'lxrq={lx} fxrq={fx} 销假={xj if xj else "空"}')
    print(f'xnrq={i.get("xnrq")} xnsd={i.get("xnsd")} bzr={i.get("userbzr")} fdy={i.get("userfdy")}')
