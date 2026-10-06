"""
HPC算力平台2025年任务统计脚本
计算：节点总时长(去重叠)、任务总时长、卡时
"""

import re
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict

# ============ 配置 ============
API_URL = "https://hpc.hutb.edu.cn/hpc-backend/task/pageList"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3OTA4NDI0NTAsInVzZXJuYW1lIjoiYzMwNTUifQ.erFsfx-q_cjt5ZJpu6H8JzZnrbn78UVtglBMZbMVBT8",
    "X-Access-Token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3OTA4NDI0NTAsInVzZXJuYW1lIjoiYzMwNTUifQ.erFsfx-q_cjt5ZJpu6H8JzZnrbn78UVtglBMZbMVBT8",
    "X-Sign": "443C29013660A0101330711C00E06D29",
    "X-TIMESTAMP": "1790824506917",
    "X-Tenant-Id": "0",
    "X-Version": "v3",
    "Referer": "https://hpc.hutb.edu.cn/job/jobList",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
PARAMS = {
    "column": "startTime",
    "order": "desc",
    "pageNo": 1,
    "pageSize": 1000,
    "status": "",
    "startTime": "2025-01-01 00:00:00",
    "endTime": "2025-12-31 23:59:59",
    "all": "true",
    "timeColumn": "startTime",
}
EXCLUDED_GPU_KEYS = {"cpu", "mem", "computingResource"}  # resourceUsed中排除的key


# ============ 工具函数 ============
def parse_time(s):
    """解析时间字符串 '2025-12-31 15:04:13'"""
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")


def parse_duration_to_seconds(duration_str):
    """解析 '23小时59分33秒' 为秒"""
    if not duration_str:
        return 0
    total = 0
    for num, unit in re.findall(r"(\d+)(小时|分钟|分|秒)", duration_str):
        num = int(num)
        if unit == "小时":
            total += num * 3600
        elif unit in ("分钟", "分"):
            total += num * 60
        elif unit == "秒":
            total += num
    return total


def get_gpu_count(resource_used):
    """
    从resourceUsed中提取GPU卡数。
    排除cpu、mem、computingResource后，剩下key的value之和即为GPU卡数。
    例: {"mem": "4 GiB", "cpu": 2, "metax_gpu:C500": 8} -> 8
    """
    if not resource_used:
        return 0
    gpu_total = 0
    for k, v in resource_used.items():
        if k in EXCLUDED_GPU_KEYS:
            continue
        # 可能的value格式: 数字、字符串数字、"8卡" 等
        if isinstance(v, (int, float)):
            gpu_total += int(v)
        elif isinstance(v, str):
            m = re.search(r"(\d+)", v)
            if m:
                gpu_total += int(m.group(1))
    return gpu_total


def split_nodes(nodes_str, node_count=1):
    """
    拆分nodes字段为节点列表。
    可能格式: "tgpu1", "tgpu1,tgpu2", "tgpu[1-5]" 等
    简单处理: 按逗号/空格分拆；若无分隔符且有nodeCount个节点，则复制nodeCount次
    """
    if not nodes_str:
        return []
    # 尝试常见分隔符
    for sep in [",", ";", " ", "\n"]:
        if sep in nodes_str:
            parts = [p.strip() for p in nodes_str.split(sep) if p.strip()]
            if parts:
                return parts
    # 无分隔符，按nodeCount复制
    return [nodes_str] * max(node_count, 1)


def merge_intervals(intervals):
    """
    合并重叠/相邻的时间区间。
    intervals: list of (start_dt, end_dt)
    返回: list of (start_dt, end_dt) 已合并
    """
    if not intervals:
        return []
    # 过滤无效区间
    intervals = [(s, e) for s, e in intervals if s and e and e >= s]
    if not intervals:
        return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # 重叠或相邻
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def fetch_all_tasks():
    """分页获取所有任务"""
    all_records = []
    page_no = 1
    while True:
        params = {**PARAMS, "pageNo": page_no}
        print(f"正在请求第 {page_no} 页...")
        resp = requests.get(API_URL, headers=HEADERS, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            print(f"接口返回失败: {data.get('message')}")
            break
        result = data.get("result", {})
        records = result.get("records", [])
        all_records.extend(records)
        total = result.get("total", 0)
        pages = result.get("pages", 1)
        print(f"  本页 {len(records)} 条，已累计 {len(all_records)}/{total} 条")
        if page_no >= pages:
            break
        page_no += 1
    return all_records


# ============ 核心统计 ============
def compute_stats(tasks):
    # 节点 -> 时间区间列表
    node_intervals = defaultdict(list)
    # 任务总时长(秒)
    total_task_seconds = 0.0
    # 卡时(秒)：每个任务 时长×卡数
    total_gpu_seconds = 0.0

    skipped = []
    for t in tasks:
        # 取startTime或submitTime作为开始时间
        start_str = t.get("startTime") or t.get("submitTime")
        end_str = t.get("endTime")
        nodes_str = t.get("nodes", "")
        node_count = t.get("nodeCount", 1)
        resource_used = t.get("resourceUsed", {})

        start_dt = parse_time(start_str)
        end_dt = parse_time(end_str)

        if not start_dt or not end_dt or end_dt < start_dt:
            # 尝试用duration字段兜底
            dur_sec = parse_duration_to_seconds(t.get("duration"))
            if start_dt and dur_sec > 0:
                end_dt = start_dt + timedelta(seconds=dur_sec)
            else:
                skipped.append(t.get("name") or t.get("id"))
                continue

        task_seconds = (end_dt - start_dt).total_seconds()
        total_task_seconds += task_seconds

        # GPU卡数
        gpu_count = get_gpu_count(resource_used)
        total_gpu_seconds += task_seconds * gpu_count

        # 节点区间
        node_list = split_nodes(nodes_str, node_count)
        for node in node_list:
            node_intervals[node].append((start_dt, end_dt))

    if skipped:
        print(f"\n⚠ 跳过 {len(skipped)} 条无有效时间的任务")

    # 合并每个节点的区间，计算节点实际占用时长
    node_hours = {}
    for node, intervals in node_intervals.items():
        merged = merge_intervals(intervals)
        node_sec = sum((e - s).total_seconds() for s, e in merged)
        node_hours[node] = round(node_sec / 3600, 2)

    total_node_hours = round(sum(node_hours.values()), 2)
    total_task_hours = round(total_task_seconds / 3600, 2)
    total_gpu_hours = round(total_gpu_seconds / 3600, 2)

    return {
        "task_count": len(tasks),
        "skipped_count": len(skipped),
        "total_task_hours": total_task_hours,
        "total_node_hours": total_node_hours,
        "total_gpu_hours": total_gpu_hours,
        "node_hours_detail": dict(sorted(node_hours.items(), key=lambda x: -x[1])),
    }


# ============ 主流程 ============
def main():
    # 1. 获取数据
    tasks = fetch_all_tasks()
    print(f"\n✅ 共获取 {len(tasks)} 条任务记录")

    if not tasks:
        print("无数据，退出")
        return

    # 2. 保存原始数据（可选，方便复查）
    with open("tasks_2025.json", "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    print("原始数据已保存到 tasks_2025.json")

    # 3. 统计
    stats = compute_stats(tasks)

    # 4. 输出结果
    print("\n" + "=" * 50)
    print("📊 2025年HPC任务统计结果")
    print("=" * 50)
    print(f"  任务总数:            {stats['task_count']} 条")
    print(f"  任务总时长:          {stats['total_task_hours']:,.2f} 小时")
    print(f"  节点总时长(去重叠):  {stats['total_node_hours']:,.2f} 小时")
    print(f"  卡时(GPU Hours):     {stats['total_gpu_hours']:,.2f} 小时")
    print("-" * 50)
    print("各节点时长 Top 20:")
    for i, (node, hours) in enumerate(
        list(stats["node_hours_detail"].items())[:20], 1
    ):
        print(f"  {i:>2}. {node:<20} {hours:>12,.2f} h")

    # 5. 保存结果
    with open("hpc_stats_result.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 hpc_stats_result.json")


if __name__ == "__main__":
    main()
