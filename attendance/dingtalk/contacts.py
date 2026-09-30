"""钉钉通讯录 — 只记录有工号的学生，附带部门名"""

import logging
import httpx

logger = logging.getLogger("attendance.dingtalk.contacts")

CONTACTS_URLS = [
    ("POST", "https://oapi.dingtalk.com/topapi/v2/user/list"),
    ("GET",  "https://api.dingtalk.com/v1.0/contacts/users"),
]


def _is_api_error(data: dict) -> bool:
    if "errcode" in data:
        return data["errcode"] != 0
    if "code" in data:
        return True
    return False


def fetch_students_by_dept(access_token: str, dept_id: int,
                           dept_name: str = "") -> list[dict]:
    """获取部门学生，只保留有工号(job_number)的，附带部门名"""
    for method, url in CONTACTS_URLS:
        try:
            is_oapi = "oapi.dingtalk.com" in url
            headers = {} if is_oapi else {"x-acs-dingtalk-access-token": access_token}
            params = {"access_token": access_token} if is_oapi else {}

            logger.info(f"📡 通讯录: {dept_name}({dept_id})")

            if method == "GET":
                resp = httpx.get(url, params={**params, "deptId": dept_id, "size": 100, "cursor": 0},
                                 headers=headers, timeout=15.0)
            else:
                resp = httpx.post(url, params=params,
                                  json={"dept_id": dept_id, "cursor": 0, "size": 100},
                                  headers=headers, timeout=15.0)

            data = resp.json() if resp.text else {}
            logger.info(f"   HTTP {resp.status_code}")

            if resp.status_code == 200 and not _is_api_error(data):
                user_list = (data.get("result", {}).get("list") or data.get("list") or
                            data.get("data") or [])

                all_count = len(user_list)
                students = []
                for u in user_list:
                    uid = u.get("userid") or u.get("userId") or u.get("user_id", "")
                    name = u.get("name") or u.get("userName", "")
                    job_number = u.get("job_number") or u.get("jobnumber", "")
                    if uid and job_number and job_number.isdigit() and job_number.startswith("27"):
                        students.append({
                            "user_id": uid, "name": name,
                            "job_number": job_number,
                            "dept_name": dept_name,
                        })

                logger.info(f"   {all_count}人 → 有工号{len(students)}人")
                return students

        except httpx.RequestError as e:
            logger.warning(f"   ⚠️ 网络: {e}")
        except Exception as e:
            logger.warning(f"   ⚠️ 异常: {e}")

    logger.info(f"   🔄 降级 Mock")
    return _mock_students(dept_id, dept_name)


def _mock_students(dept_id: int, dept_name: str) -> list[dict]:
    mock = {
        1085232152: [("stu_01","张三","001"),("stu_02","李四","002")],
        1084993589: [("stu_03","王五","003")],
        1084993590: [("stu_04","赵六","004")],
        1085996186: [("stu_05","钱七","005"),("stu_06","孙八","006")],
    }
    raw = mock.get(dept_id, [])
    return [{"user_id": uid, "name": name, "job_number": jn, "dept_name": dept_name}
            for uid, name, jn in raw]
