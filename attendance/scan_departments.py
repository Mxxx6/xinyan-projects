#!/usr/bin/env python3
"""自动扫描钉钉组织架构，更新config.yaml中的部门列表"""

import yaml
import httpx
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.yaml"
XUEJIE = 27  # 当前学届
STUDENT_ROOT = 846878424  # 27届学生根部门ID

def get_token():
    with open(CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    d = cfg['dingtalk']
    r = httpx.post('https://api.dingtalk.com/v1.0/oauth2/accessToken',
        json={'appKey': d['app_key'], 'appSecret': d['app_secret']}, timeout=15)
    return r.json()['accessToken']

def scan_depts(token, parent_id, prefix=""):
    """递归扫描部门树，返回 {dept_id: name} 的部门（有工号学生的）"""
    result = {}
    r = httpx.post('https://oapi.dingtalk.com/topapi/v2/department/listsub',
        params={'access_token': token},
        json={'dept_id': parent_id}, timeout=15)

    for d in r.json().get('result', []):
        did = d['dept_id']
        name = d['name']

        # 查学生
        all_users = []
        cursor = 0
        while True:
            r2 = httpx.post('https://oapi.dingtalk.com/topapi/v2/user/list',
                params={'access_token': token},
                json={'dept_id': did, 'cursor': cursor, 'size': 100}, timeout=15)
            res = r2.json().get('result', {})
            batch = res.get('list', [])
            all_users.extend(batch)
            if not res.get('has_more') or not batch:
                break
            cursor += len(batch)

        has_job = any(u.get('job_number', '').startswith(str(XUEJIE)) for u in all_users)

        if has_job:
            result[did] = name.replace(f'_{XUEJIE}届师生群', '').replace(f'_{XUEJIE}届师生', '').replace(f'_{XUEJIE}届', '')

        # 递归子部门
        result.update(scan_depts(token, did))

    return result

def main():
    print(f'🔍 扫描{XUEJIE}届部门...')
    token = get_token()
    depts = scan_depts(token, STUDENT_ROOT)
    depts = dict(sorted(depts.items(), key=lambda x: x[1]))

    print(f'找到 {len(depts)} 个部门')

    # 读现有config
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)

    old_depts = config.get('dept_labels', {})
    old_ids = config['schedule'][0]['dept_ids']

    new_depts = {k: v for k, v in depts.items() if k not in old_depts}
    removed = [k for k in old_depts if k not in depts]

    if new_depts:
        print(f'\n新增 {len(new_depts)} 个部门:')
        for did, name in new_depts.items():
            print(f'  {did}: {name}')
    else:
        print('无新增部门')

    if removed:
        print(f'\n已移除 {len(removed)} 个部门:')
        for did in removed:
            print(f'  {did}: {old_depts[did]}')

    if new_depts or removed:
        # 更新 config
        config['dept_labels'] = depts
        dept_ids = sorted(depts.keys())
        for slot in config['schedule']:
            slot['dept_ids'] = dept_ids

        with open(CONFIG_PATH, 'w') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f'\n✅ config.yaml 已更新 ({len(depts)}个部门)')
    else:
        print(f'\n✅ 无需更新')

if __name__ == '__main__':
    main()
