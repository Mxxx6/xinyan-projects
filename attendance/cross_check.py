"""Cross-reference 简道云 vs 钉钉 students（工具脚本，凭据来自 config.yaml 与环境变量）"""
import os
import httpx
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))

# DingTalk 凭据来自 config.yaml（模板见 config.example.yaml）
with open(os.path.join(_HERE, "config.yaml")) as f:
    _cfg = yaml.safe_load(f)
_dt = _cfg.get("dingtalk", {})

resp = httpx.post(
    "https://api.dingtalk.com/v1.0/oauth2/accessToken",
    json={"appKey": _dt.get("app_key", ""), "appSecret": _dt.get("app_secret", "")},
)
token = resp.json()["accessToken"]

# 简道云凭据来自环境变量（模板见 .env.example）
JDY_API_KEY = os.environ.get("JDY_API_KEY", "")
JDY_APP_ID = os.environ.get("JDY_APP_ID", "")
JDY_ENTRY_ID = os.environ.get("JDY_ENTRY_ID", "")
h = {"Authorization": "Bearer " + JDY_API_KEY, "Content-Type": "application/json"}

all_jdy = set()
skip = 0
while True:
    r = httpx.post(
        f"https://api.jiandaoyun.com/api/v2/app/{JDY_APP_ID}/entry/{JDY_ENTRY_ID}/data",
        headers=h,
        json={"limit": 200, "skip": skip, "filter": {"rel": "and", "cond": [{"field": "xuejie", "type": "text", "method": "eq", "value": ["27"]}]}},
        timeout=15,
    )
    batch = r.json().get("data", [])
    if not batch:
        break
    for i in batch:
        xh = str(i.get("xuehao", "")).strip()
        if xh:
            all_jdy.add(xh)
    skip += len(batch)

print(f"简道云27届: {len(all_jdy)}个学号")

# DingTalk — 部门来自 config.yaml 课表
dids = _cfg["schedule"][0]["dept_ids"]

dds = set()
for did in dids:
    try:
        r = httpx.post(
            "https://oapi.dingtalk.com/topapi/v2/user/list",
            params={"access_token": token},
            json={"dept_id": did, "cursor": 0, "size": 100},
        )
        for u in r.json()["result"]["list"]:
            jn = u.get("job_number", "").strip()
            if jn and jn.startswith("27") and jn.isdigit():
                dds.add(jn)
    except Exception as e:
        print(f"  dept {did} error: {e}")

print(f"钉钉27届: {len(dds)}个工号")

only_jdy = all_jdy - dds
only_dd = dds - all_jdy
both = all_jdy & dds

print(f"\n交集: {len(both)} | 仅简道云: {len(only_jdy)} | 仅钉钉: {len(only_dd)}")

if only_jdy:
    print(f"仅简道云({len(only_jdy)}):")
    for x in sorted(only_jdy)[:30]:
        print(f"  {x}")
if only_dd:
    print(f"仅钉钉({len(only_dd)}):")
    for x in sorted(only_dd)[:30]:
        print(f"  {x}")
