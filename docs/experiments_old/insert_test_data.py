import pymysql
import random
import time
import math

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'hpc2024test',
    'database': 'hpc_monitor',
    'charset': 'utf8mb4',
}

TOTAL_ROWS = 500000
BATCH_SIZE = 5000
NODE = 'gpu6'
INTERVAL = 5

def insert_data():
    now = int(time.time())
    start_ts = now - TOTAL_ROWS * INTERVAL

    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print(f"Inserting {TOTAL_ROWS} rows, node={NODE}, ts range=[{start_ts}, {now}], interval={INTERVAL}s")
    print(f"Time span: {TOTAL_ROWS * INTERVAL / 86400:.1f} days")

    batch = []
    t0 = time.time()

    for i in range(TOTAL_ROWS):
        ts = start_ts + i * INTERVAL
        gpu_usage = round(random.uniform(0, 100), 2)
        batch.append((NODE, ts, gpu_usage))

        if len(batch) >= BATCH_SIZE:
            cursor.executemany(
                "INSERT IGNORE INTO t_node_gpu_history_info (node, `timestamp`, gpu_usage) VALUES (%s, %s, %s)",
                batch
            )
            conn.commit()
            batch = []
            if (i + 1) % 50000 == 0:
                elapsed = time.time() - t0
                pct = (i + 1) / TOTAL_ROWS * 100
                print(f"  Progress: {i+1}/{TOTAL_ROWS} ({pct:.1f}%), elapsed: {elapsed:.1f}s")

    if batch:
        cursor.executemany(
            "INSERT IGNORE INTO t_node_gpu_history_info (node, `timestamp`, gpu_usage) VALUES (%s, %s, %s)",
            batch
        )
        conn.commit()

    elapsed = time.time() - t0
    print(f"Done! Total: {TOTAL_ROWS} rows, Time: {elapsed:.1f}s, Speed: {TOTAL_ROWS/elapsed:.0f} rows/s")

    cursor.execute("SELECT COUNT(*) FROM t_node_gpu_history_info WHERE node=%s", (NODE,))
    count = cursor.fetchone()[0]
    print(f"Verified row count: {count}")

    cursor.execute("SHOW TABLE STATUS LIKE 't_node_gpu_history_info'")
    status = cursor.fetchone()
    print(f"Table size (Data): {int(status[6])/1024/1024:.2f} MB, Index: {int(status[8])/1024/1024:.2f} MB")

    cursor.close()
    conn.close()

if __name__ == '__main__':
    insert_data()
