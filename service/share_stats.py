'''
共享机时统计服务

参考 scripts/计算机时.py 的统计口径：
- 任务总时长：所有任务 (endTime - startTime) 之和
- 节点总时长(去重叠)：按节点合并重叠时间区间后求和
- 卡时：任务时长 × GPU卡数
- 各节点卡时：任务时长 × 平均分摊到各节点的卡数（多节点任务均摊）
'''
import re
import time
from collections import defaultdict
from datetime import datetime, timedelta

from common import logger
from infra.hpc_api import api

# resourceUsed 中排除的key，剩下的即为GPU卡数
EXCLUDED_GPU_KEYS = {"cpu", "mem", "computingResource"}

# 内存缓存 TTL（秒），避免每次进入页面都拉取全量任务
CACHE_TTL = 30 * 60

_stats_cache = {}  # {(start_date, end_date): (fetched_ts, stats)}


def _parse_time(s):
    """解析时间字符串 '2025-12-31 15:04:13'"""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _parse_duration_to_seconds(duration_str):
    """解析 '23小时59分33秒' 为秒"""
    if not duration_str:
        return 0
    total = 0
    for num, unit in re.findall(r"(\d+)(小时|分钟|分|秒)", str(duration_str)):
        num = int(num)
        if unit == "小时":
            total += num * 3600
        elif unit in ("分钟", "分"):
            total += num * 60
        elif unit == "秒":
            total += num
    return total


def _gpu_count(resource_used):
    """
    从resourceUsed中提取GPU卡数。
    排除cpu、mem、computingResource后，剩下key的value之和即为GPU卡数。
    例: {"mem": "4 GiB", "cpu": 2, "metax_gpu:C500": 8} -> 8
    """
    if not isinstance(resource_used, dict):
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


def _split_nodes(nodes_str, node_count=1):
    """
    拆分nodes字段为节点列表。
    可能格式: "tgpu1", "tgpu1,tgpu2" 等
    简单处理: 按逗号/分号/空格拆分；若无分隔符且有nodeCount个节点，则复制nodeCount次
    """
    if not nodes_str:
        return []
    nodes_str = str(nodes_str)
    for sep in [",", ";", " ", "\n"]:
        if sep in nodes_str:
            parts = [p.strip() for p in nodes_str.split(sep) if p.strip()]
            if parts:
                return parts
    return [nodes_str] * max(node_count or 1, 1)


def _merge_intervals(intervals):
    """合并重叠/相邻的时间区间"""
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


def compute_share_stats(tasks, end_bound=None):
    """基于任务列表计算共享机时统计指标"""
    node_intervals = defaultdict(list)
    node_task_count = defaultdict(int)
    node_gpu_seconds = defaultdict(float)
    monthly = defaultdict(lambda: {"tasks": 0, "task_sec": 0.0, "gpu_sec": 0.0})

    total_task_seconds = 0.0
    total_gpu_seconds = 0.0
    skipped = []
    running_count = 0

    for t in tasks:
        start_str = t.get("startTime") or t.get("submitTime")
        end_str = t.get("endTime")
        nodes_str = t.get("nodes") or ""
        if not nodes_str:
            continue
        node_count = t.get("nodeCount") or 1
        resource_used = t.get("resourceUsed") or {}
        if node_count > 1:
            node_count = node_count
        start_dt = _parse_time(start_str)
        end_dt = _parse_time(end_str)

        if not start_dt:
            skipped.append(t.get("name") or t.get("slurmJobId") or t.get("id"))
            continue

        if not end_dt or end_dt < start_dt:
            if t.get("status") == "RUNNING":
                # 运行中的任务按当前时刻计入
                end_dt = end_bound or datetime.now()
                running_count += 1
            else:
                # 尝试用duration字段兜底
                dur_sec = _parse_duration_to_seconds(t.get("duration"))
                if dur_sec > 0:
                    end_dt = start_dt + timedelta(seconds=dur_sec)
                else:
                    skipped.append(t.get("name") or t.get("slurmJobId") or t.get("id"))
                    continue

        task_seconds = (end_dt - start_dt).total_seconds()
        gpu_count = _gpu_count(resource_used)

        total_task_seconds += task_seconds
        total_gpu_seconds += task_seconds * gpu_count

        month_key = start_dt.strftime("%Y-%m")
        monthly[month_key]["tasks"] += 1
        monthly[month_key]["task_sec"] += task_seconds
        monthly[month_key]["gpu_sec"] += task_seconds * gpu_count

        # 节点区间与分摊卡时
        node_list = _split_nodes(nodes_str, node_count)
        if not node_list:
            node_list = ["-"]
        per_node_gpu = gpu_count / len(node_list)
        for node in node_list:
            node_intervals[node].append((start_dt, end_dt))
            node_task_count[node] += 1
            node_gpu_seconds[node] += task_seconds * per_node_gpu

    # 合并每个节点的区间，计算节点实际占用时长与卡时
    node_rows = []
    for node, intervals in node_intervals.items():
        merged = _merge_intervals(intervals)
        node_sec = sum((e - s).total_seconds() for s, e in merged)
        gpu_sec = node_gpu_seconds.get(node, 0.0)
        node_rows.append({
            "node": node,
            "task_count": node_task_count.get(node, 0),
            "node_hours": round(node_sec / 3600, 2),
            "gpu_hours": round(gpu_sec / 3600, 2),
            "avg_cards": round(gpu_sec / node_sec, 2) if node_sec > 0 else 0,
        })
    node_rows.sort(key=lambda x: (-x["gpu_hours"], -x["node_hours"]))

    total_gpu_hours = total_gpu_seconds / 3600
    for row in node_rows:
        row["gpu_hours_pct"] = f"{row['gpu_hours'] / total_gpu_hours * 100:.1f}%" if total_gpu_hours > 0 else "-"

    monthly_rows = [
        {
            "month": month,
            "tasks": monthly[month]["tasks"],
            "task_hours": round(monthly[month]["task_sec"] / 3600, 2),
            "gpu_hours": round(monthly[month]["gpu_sec"] / 3600, 2),
        }
        for month in sorted(monthly.keys())
    ]

    return {
        "task_count": len(tasks),
        "skipped_count": len(skipped),
        "running_count": running_count,
        "total_task_hours": round(total_task_seconds / 3600, 2),
        "total_node_hours": round(sum(r["node_hours"] for r in node_rows), 2),
        "total_gpu_hours": round(total_gpu_hours, 2),
        "node_rows": node_rows,
        "monthly": monthly_rows,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_share_stats(start_date, end_date, force_refresh=False):
    """获取指定日期区间（YYYY-MM-DD）的共享机时统计，带内存缓存"""
    key = (start_date, end_date)
    now = time.time()
    cached = _stats_cache.get(key)
    if cached and not force_refresh and now - cached[0] < CACHE_TTL:
        return cached[1]

    logger.info(f"开始获取共享机时统计数据：{start_date} ~ {end_date} (force={force_refresh})")
    try:
        tasks = api.get_all_tasks(f"{start_date} 00:00:00", f"{end_date} 23:59:59")
    except Exception as e:
        logger.error(f"获取共享机时任务数据失败：{e}")
        tasks = []
    stats = compute_share_stats(tasks or [])
    _stats_cache[key] = (now, stats)
    return stats
