
import random
from datetime import datetime, timedelta

# Mock Data Service

def get_partitions():
    return [
        {"id": "defq", "name": "Default Partition", "totalCpu": 1000, "totalMem": 4000, "totalGpu": 0},
        {"id": "gpu_v100", "name": "GPU V100", "totalCpu": 200, "totalMem": 1000, "totalGpu": 50},
        {"id": "gpu_a800", "name": "GPU A800", "totalCpu": 100, "totalMem": 2000, "totalGpu": 20},
        {"id": "cpu_large", "name": "Large Memory", "totalCpu": 500, "totalMem": 8000, "totalGpu": 0},
    ]

def get_jobs(filter_status=None, limit=100):
    jobs = []
    statuses = ["RUNNING", "PENDING", "COMPLETED", "FAILED"]
    for i in range(limit):
        status = random.choice(statuses)
        if filter_status and status != filter_status:
            continue
            
        jobs.append({
            "id": f"{10000+i}",
            "status": status,
            "resources": f"{random.randint(1, 32)}/{random.randint(4, 128)}G/{random.randint(0, 4)}",
            "start": (datetime.now() - timedelta(minutes=random.randint(0, 1000))).strftime("%Y-%m-%d %H:%M"),
            "end": (datetime.now() + timedelta(minutes=random.randint(10, 100))).strftime("%Y-%m-%d %H:%M") if status == "RUNNING" else "-",
            "user": f"user{random.randint(1, 50)}",
            "node": f"node-{random.randint(1, 100):03d}",
            "partition": random.choice(["defq", "gpu_v100", "gpu_a800"])
        })
    return jobs

def get_nodes(partition=None):
    nodes = []
    for i in range(50):
        nodes.append({
            "id": f"node-{i+1:03d}",
            "status": random.choice(["idle", "alloc", "mix", "down", "drain"]),
            "cpu_util": random.randint(0, 100),
            "mem_util": random.randint(0, 100),
            "gpu_util": random.randint(0, 100) if i % 2 == 0 else None,
            "jobs_count": random.randint(0, 10)
        })
    return nodes

def get_daily_stats(date_str):
    # Mock daily stats
    return {
        "resource_stats": [],
        "user_stats": {"total": 100, "online": 20},
        "abnormal_nodes": [],
        "queued_jobs": []
    }
