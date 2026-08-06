import os
import sys
import requests
import json
import time
from datetime import datetime

# 动态类型友好名称映射
type_map = {
    "DYNAMIC_TYPE_DRAW": "图文动态",
    "DYNAMIC_TYPE_AV": "视频投稿",
    "DYNAMIC_TYPE_WORD": "纯文字动态",
    "DYNAMIC_TYPE_ARTICLE": "专栏文章",
    "DYNAMIC_TYPE_FORWARD": "转发动态"
}

def get_dynamic_title(item):
    """
    从单个动态数据中提取标题/描述文本
    优先级：视频标题 > 转发动态的原文标题 > 图文/纯文字的描述 > 空字符串
    """
    major = item.get("modules", {}).get("module_dynamic", {}).get("major")
    if not major:
        return ""

    major_type = major.get("type")
    if major_type == "MAJOR_TYPE_ARCHIVE":      # 视频投稿
        archive = major.get("archive", {})
        return archive.get("title", "")
    elif major_type == "MAJOR_TYPE_DRAW":       # 图文动态
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc")
        return desc if desc else ""
    elif major_type == "MAJOR_TYPE_WORD":       # 纯文字动态
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc")
        return desc if desc else ""
    elif major_type == "MAJOR_TYPE_ARTICLE":    # 专栏文章
        article = major.get("article", {})
        return article.get("title", "")
    elif major_type == "MAJOR_TYPE_FORWARD":    # 转发动态
        orig = item.get("orig")
        if orig:
            return get_dynamic_title(orig)
        else:
            return "转发动态"
    else:
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc")
        return desc if desc else ""

def fetch_up_dynamics(uid, offset="", page=1):
    """
    请求 B 站空间动态接口，返回 items 列表
    """
    api_url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    params = {
        "host_mid": uid,
        "offset": offset,
        "page": page
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
        "Cookie": "buvid3=C6DEDC59-A104-6CAD-4F49-C41C09C9BAA582493infoc; b_nut=1785990882; bsource=search_bing; _uuid=397B37CB-B661-7C7B-CE9A-FDC53A229BD282897infoc; home_feed_column=5; browser_resolution=1912-956; buvid_fp=b82f79aa513cecab443b4c4678de719f; buvid4=64EB2EE4-818D-0DA2-337E-01A4B1C7F8E383292-026080612-FqX1wJk3Owyr3Y2swErK30YYo/pTwFiGOlOxHUDHrGK0BcL4M2puJNHwVTdZN0JV; SESSDATA=f2e15889%2C1801542903%2C3a557%2A82CjD6LzxqQuh-rl290KllUJx7jPQi252g5tkkhwaIQ2pRfpWCeWMUCPojyXcioBF95JMSVlFfOVVJQVZMZUFUUmVpNTFldHVNbTlVMFdad1Y3SzlhbmJTcUpDenZnNkxra2E2V3J5dURmNGZPTUdoRkFzMUw0UVRYM1VHMVgtS21CYnBjbV91ZVVBIIEC; bili_jct=47b8926038b49c94f063d1b69cd0af9f; DedeUserID=22147950; DedeUserID__ckMd5=48c2f79059d862da; theme-tip-show=SHOWED; sid=8kpbv31u; CURRENT_QUALITY=0; rpdid=0zbfAHVLXw|WOxNsBV3|4Ck|3w1WRPP5; theme-avatar-tip-show=SHOWED; bp_t_offset_22147950=1233375025269047296; CURRENT_FNVAL=2000; hit-dyn-v2=1; bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODYyNzI5NTIsImlhdCI6MTc4NjAxMzY5MiwicGx0IjotMX0.i3poYnbHpKf6rHS2sUH_ANyKPjwulMmeQyML2Bu_XRc; bili_ticket_expires=1786272892; b_lsid=2DD5F256_19FD6BBE967",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    }
    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            print(f"API 返回错误：{data.get('message')}")
            return []
        items = data.get("data", {}).get("items", [])
        return items
    except Exception as e:
        print(f"请求动态失败：{e}")
        return []

def build_push_content(items):
    """
    将动态列表整理为推送内容字符串
    """
    if not items:
        return "未获取到动态"

    lines = []
    for idx, item in enumerate(items[:10], 1):  # 最多取前10条
        dyn_id = item.get("id_str", "")
        dyn_type = item.get("type", "")
        type_name = type_map.get(dyn_type, dyn_type)
        pub_time = item.get("modules", {}).get("module_author", {}).get("pub_time", "")
        author = item.get("modules", {}).get("module_author", {}).get("name", "")
        title = get_dynamic_title(item)
        link = f"https://t.bilibili.com/{dyn_id}" if dyn_id else ""

        line = f"{idx}. {type_name}"
        if title:
            line += f" - {title}"
        if author:
            line += f" (by {author})"
        if pub_time:
            line += f" {pub_time}"
        if link:
            line += f" 链接：{link}"
        lines.append(line)

    return "\n".join(lines)

def bark_push(bark_key, title, content):
    if not bark_key:
        return False
    url = "https://api.day.app/push"
    payload = {
        "device_key": bark_key,   # 根据错误提示尝试修改字段名
        "title": title,
        "body": content,
        "sound": "default"
    }
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            return True
        else:
            print(f"Bark 推送失败，状态码：{resp.status_code}，响应：{resp.text}")
            return False
    except Exception as e:
        print(f"Bark 推送异常：{e}")
        return False
if __name__ == '__main__':
    # 1. 获取 Bark 密钥（支持多个，用 & 分隔）
    bark_keys_env = os.environ.get("BARK_KEY", "")
    # 如果环境变量未设置，则使用硬编码测试密钥（请替换为您自己的）
    if not bark_keys_env:
        bark_keys_env = "UuYcY5XvAJD2tVkavzeeTd"   # 请替换为真实密钥
    bark_keys = bark_keys_env.split("&")
    if not bark_keys or bark_keys[0] == "":
        print('未获取到 BARK_KEY 变量，请在环境变量中配置')
        sys.exit(0)

    # 2. 获取 B 站 UID
    bili_uid = os.environ.get("BILI_UID", "194084427")

    # 3. 获取动态
    print(f"正在获取 UID {bili_uid} 的动态...")
    items = fetch_up_dynamics(bili_uid)
    if not items:
        print("没有获取到动态数据")
        sys.exit(0)

    # 4. 构建推送内容
    content = build_push_content(items)
    title = "B站动态更新提醒"

    # 5. 遍历所有 bark_key 推送
    success_count = 0
    fail_count = 0
    for key in bark_keys:
        key = key.strip()
        if not key:
            continue
        if bark_push(key, title, content):
            success_count += 1
        else:
            fail_count += 1

    print(f"推送完成，成功：{success_count}，失败：{fail_count}")
