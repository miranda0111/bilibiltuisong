import os
import sys
import requests
import json
import time
import random
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
    if major_type == "MAJOR_TYPE_ARCHIVE":      # 视频投稿1
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


def fetch_up_dynamics(uid, Cookies, offset="", page=1, max_retry=3):
    """
    请求 B 站空间动态接口，增加重试机制，返回 items 列表
    """
    api_url = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
    params = {
        "host_mid": uid,
        "offset": offset,
        "page": page
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0",
        "Cookie": Cookies,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
    }

    for retry in range(max_retry):
        try:
            resp = requests.get(api_url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                print(f"API 返回错误：{data.get('message')}，重试 {retry+1}/{max_retry}")
                time.sleep(2)
                continue
            items = data.get("data", {}).get("items", [])
            return items
        except Exception as e:
            print(f"请求动态失败：{e}，重试 {retry+1}/{max_retry}")
            time.sleep(2)
    print(f"UID {uid} 已达到最大重试次数，放弃获取")
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
    bark_keys = bark_keys_env.split("&")
    bark_keys = [k.strip() for k in bark_keys if k.strip()]
    if not bark_keys:
        print('未获取到 BARK_KEY 变量，请在环境变量中配置')
        sys.exit(0)

    # 2. 多个UID，环境变量用英文&分隔 BILI_UID=uid1&uid2&uid3
    bili_uid_env = os.environ.get("BILI_UID", "")
    uid_list = bili_uid_env.split("&")
    uid_list = [u.strip() for u in uid_list if u.strip()]
    if not uid_list:
        print("未配置 BILI_UID，多个UID用英文&分隔")
        sys.exit(0)

    Cookies_env = os.environ.get("COOKIES", "")

    all_recent_items = []
    for uid in uid_list:
        print(f"\n===== 正在获取 UID {uid} 的动态 =====")
        # 每个UID请求前随机等待 1.5 ~ 4秒，防止请求频率过高
        sleep_sec = random.uniform(1.5, 5.0)
        print(f"随机等待 {sleep_sec:.2f}s ...")
        time.sleep(sleep_sec)

        up_items = fetch_up_dynamics(uid, Cookies_env)
        if not up_items:
            print(f"UID {uid} 未获取到动态")
            continue
        # 过滤30分钟内动态
        recent = filter_half_hour_dynamics(up_items)
        if recent:
            print(f"UID {uid} 抓到 {len(recent)} 条近30分钟动态")
            all_recent_items.extend(recent)
        else:
            print(f"UID {uid} 近30分钟无新动态")

    if not all_recent_items:
        print("\n所有UP主近30分钟均无新动态，不推送")
        sys.exit(0)

    content = build_push_content(all_recent_items)
    title = "B站动态更新提醒"
    full_msg = f"{title}\n\n{content}"
    print(full_msg)

    # 遍历所有 bark_key 推送
    success_count = 0
    fail_count = 0
    for key in bark_keys:
        if bark_push(key, title, content):
            success_count += 1
        else:
            fail_count += 1
    print(f"\n推送完成，成功：{success_count}，失败：{fail_count}")