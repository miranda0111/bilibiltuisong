import os
import sys
import requests
import json
import time
from datetime import datetime, timedelta

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
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc", {})
        return desc.get("text", "") if desc else ""

    major_type = major.get("type")
    if major_type == "MAJOR_TYPE_ARCHIVE":      # 视频投稿
        archive = major.get("archive", {})
        return archive.get("title", "")
    elif major_type == "MAJOR_TYPE_DRAW":       # 图文动态
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc", {})
        return desc.get("text", "") if desc else ""
    elif major_type == "MAJOR_TYPE_WORD":       # 纯文字动态
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc", {})
        return desc.get("text", "") if desc else ""
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
        desc = item.get("modules", {}).get("module_dynamic", {}).get("desc", {})
        return desc.get("text", "") if desc else ""

def get_publish_datetime(item):
    """获取动态发布时间datetime对象，用于时间过滤"""
    module_author = item.get("modules", {}).get("module_author", {})
    pub_ts = module_author.get("pub_ts")
    try:
        # 时间戳转datetime
        ts = int(pub_ts)
        return datetime.fromtimestamp(ts)
    except (ValueError, TypeError):
        return None

def filter_half_hour_dynamics(item_list):
    """过滤出近30分钟内发布的动态"""
    now = datetime.now()
    limit_time = now - timedelta(minutes=30)
    valid_list = []
    for item in item_list:
        pub_dt = get_publish_datetime(item)
        # 时间解析成功 且 发布时间在30分钟内
        if pub_dt is not None and pub_dt >= limit_time:
            valid_list.append(item)
    return valid_list

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
        "Cookie": "x-bili-gaia-vtoken=27e005cf450f45f08cfef5dec54e8a88;__at_once=790639169643703281;_uuid=B341674B-8CB3-D7B9-39D1-236862F6D88994626infoc;buvid_fp=e644e7892a75616bd6abed9eeacc6290;bili_ticket=eyJhbGciOiJIUzI1NiIsImtpZCI6InMwMyIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3ODcwNjI1MTIsImlhdCI6MTc4NjgwMzI1MiwicGx0IjotMX0.NllcKaoP7df-Xyle20O2l8OxbmKHXxYEqcKReXFeMGk;bili_ticket_expires=1787062452;buvid4=7152BCBA-018F-19F5-FB41-0B9C21FF879994744-126081522-fNd9TCZgBDMEZanxa7ivfw%3D%3D;b_nut=1786803293;buvid3=713A1A26-4F5E-F548-218B-A3E696FE317E93470infoc;b_lsid=65D6C30C_1A005C71599;",
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
    将动态列表整理为推送内容字符串（保留你原有输出格式）
    """
    if not items:
        return ""

    lines = []
    for idx, item in enumerate(items, 1):
        dyn_id = item.get("id_str", "")
        dyn_type = item.get("type", "")
        type_name = type_map.get(dyn_type, dyn_type)
        # 前端显示的相对时间（刚刚/16分钟前）
        pub_time_text = item.get("modules", {}).get("module_author", {}).get("pub_time", "")
        author = item.get("modules", {}).get("module_author", {}).get("name", "")
        title = get_dynamic_title(item)
        link = f"https://t.bilibili.com/{dyn_id}" if dyn_id else ""

        line = f"{idx}. {type_name}"
        if title:
            line += f" - {title}"
        if author:
            line += f" (by {author})"
        if pub_time_text:
            line += f" {pub_time_text}"
        if link:
            line += f" 链接：{link}"
        lines.append(line)
        print(lines)

    return "\n".join(lines)

def bark_push(bark_key, title, content):
    if not bark_key or not content.strip():
        return False
    url = "https://api.day.app/push"
    payload = {
        "device_key": bark_key,
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
    if not bark_keys_env:
        bark_keys_env = ""
    bark_keys = bark_keys_env.split("&")
    bark_keys = [k.strip() for k in bark_keys if k.strip()]
    if not bark_keys:
        print('未获取到 BARK_KEY 变量，请在环境变量中配置')
        sys.exit(0)

    # 2. 获取 B 站 UID
    bili_uid = os.environ.get("BILI_UID", "194084427")

    # 3. 获取全部动态
    print(f"正在获取 UID {bili_uid} 的动态...")
    all_items = fetch_up_dynamics(bili_uid)
    if not all_items:
        print("没有获取到动态数据")
        sys.exit(0)

    # 4. 过滤仅保留30分钟内动态
    recent_items = filter_half_hour_dynamics(all_items)
    if not recent_items:
        print("近30分钟无新动态，不推送通知")
        sys.exit(0)

    # 5. 构建推送内容（和你原输出格式完全一致）
    content = build_push_content(recent_items)
    title = "B站动态更新提醒"
    full_msg = f"{title}\n\n{content}"
    print(full_msg)

    # 6. 遍历所有 bark_key 推送
    success_count = 0
    fail_count = 0
    for key in bark_keys:
        if bark_push(key, title, content):
            success_count += 1
        else:
            fail_count += 1

    print(f"\n推送完成，成功：{success_count}，失败：{fail_count}")
