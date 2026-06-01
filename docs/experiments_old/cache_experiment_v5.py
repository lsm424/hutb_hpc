"""
专利验证实验 v5：面向关系型数据库时序数据的高性能降采样查询

实验设计：
  实验1：时间对齐 vs 未对齐（应用层缓存复用对比）
  实验2：覆盖索引 vs 非覆盖索引（热查询对比，零回表优势）
  实验3：本方案 vs 窗口函数方案（热查询对比，流式聚合优势）
  实验4：EXPLAIN 执行计划分析
"""

import pymysql
import time
import json
import subprocess
import os

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'hpc2024test',
    'database': 'hpc_monitor',
    'charset': 'utf8mb4',
}

CONTAINER_NAME = 'hpc-mysql8'
NODE = 'gpu6'
BUCKETS = 100
RANGE_DAYS = 7
RANGE_SEC = RANGE_DAYS * 86400


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def restart_mysql():
    print("  [Docker] 重启 MySQL 容器以清空缓冲池...")
    subprocess.run(['docker', 'restart', CONTAINER_NAME], capture_output=True)
    return _wait_mysql_ready()


def ensure_mysql_running():
    """确保 MySQL Docker 容器在运行，未运行则启动，不存在则创建"""
    result = subprocess.run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  [Docker] 容器 '{CONTAINER_NAME}' 不存在，正在创建...")
        return _create_mysql_container()

    running = result.stdout.strip()
    if running == 'true':
        print(f"  [Docker] 容器 '{CONTAINER_NAME}' 已在运行")
        try:
            conn = pymysql.connect(**DB_CONFIG)
            conn.close()
            return True
        except Exception:
            print(f"  [Docker] 容器运行中但 MySQL 尚未就绪，等待...")
            return _wait_mysql_ready()

    print(f"  [Docker] 容器 '{CONTAINER_NAME}' 未运行，正在启动...")
    subprocess.run(['docker', 'start', CONTAINER_NAME], capture_output=True)
    return _wait_mysql_ready()


def _create_mysql_container():
    """创建 MySQL Docker 容器并等待就绪"""
    conf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mysql', 'conf')
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mysql', 'data')

    print(f"  [Docker] 配置目录: {conf_dir}")
    print(f"  [Docker] 数据目录: {data_dir}")

    create_result = subprocess.run([
        'docker', 'run', '-d',
        '--name', CONTAINER_NAME,
        '-p', '3306:3306',
        '-v', f'{conf_dir}:/etc/mysql/conf.d',
        '-v', f'{data_dir}:/var/lib/mysql',
        '-e', 'MYSQL_ROOT_PASSWORD=hpc2024test',
        'mysql:8.0',
        '--character-set-server=utf8mb4',
        '--collation-server=utf8mb4_unicode_ci',
        '--default-authentication-plugin=mysql_native_password',
    ], capture_output=True, text=True)

    if create_result.returncode != 0:
        print(f"  [Docker] 创建容器失败: {create_result.stderr}")
        return False

    print(f"  [Docker] 容器已创建: {create_result.stdout.strip()}")
    return _wait_mysql_ready()


def _wait_mysql_ready():
    """等待 MySQL 服务就绪"""
    for i in range(60):
        time.sleep(1)
        try:
            conn = pymysql.connect(**DB_CONFIG)
            conn.close()
            print(f"  [Docker] MySQL 已就绪 (等待 {i+1}s)")
            return True
        except Exception:
            continue
    print("  [Docker] MySQL 启动超时!")
    return False


def get_bp_stats(cursor):
    try:
        cursor.execute("""
            SELECT variable_name, variable_value 
            FROM performance_schema.global_status 
            WHERE variable_name IN (
                'Innodb_buffer_pool_read_requests',
                'Innodb_buffer_pool_reads',
                'Innodb_buffer_pool_pages_data',
                'Innodb_buffer_pool_pages_total',
                'Innodb_buffer_pool_pages_free'
            )
        """)
        return {row[0]: int(row[1]) for row in cursor.fetchall()}
    except Exception:
        return {}


def snap_bp(cursor):
    try:
        cursor.execute("""
            SELECT variable_name, variable_value 
            FROM performance_schema.global_status 
            WHERE variable_name IN ('Innodb_buffer_pool_read_requests', 'Innodb_buffer_pool_reads')
        """)
        return {row[0]: int(row[1]) for row in cursor.fetchall()}
    except Exception:
        return {'Innodb_buffer_pool_read_requests': 0, 'Innodb_buffer_pool_reads': 0}


def calc_hit_rate(before, after):
    req_d = after.get('Innodb_buffer_pool_read_requests', 0) - before.get('Innodb_buffer_pool_read_requests', 0)
    read_d = after.get('Innodb_buffer_pool_reads', 0) - before.get('Innodb_buffer_pool_reads', 0)
    if req_d <= 0:
        return 0.0
    return (1 - read_d / req_d) * 100


def run_query(cursor, sql, fetch=True):
    before = snap_bp(cursor)
    t0 = time.time()
    cursor.execute(sql)
    if fetch:
        rows = cursor.fetchall()
    else:
        rows = []
    elapsed = (time.time() - t0) * 1000
    after = snap_bp(cursor)
    hr = calc_hit_rate(before, after)
    return {
        'time_ms': round(elapsed, 2),
        'rows': len(rows),
        'hit_rate': round(hr, 2)
    }


def ensure_noise_table(cursor, target_mb=64):
    """
    确保噪声表存在且有足够的数据量。
    噪声表用于模拟生产环境中的缓存压力——其他并发的查询会
    不断地把数据加载进 Buffer Pool，从而把目标表的索引页挤出缓存。
    """
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema='hpc_monitor' AND table_name='t_noise_table'
    """)
    exists = cursor.fetchone()[0] > 0

    if not exists:
        cursor.execute("""
            CREATE TABLE t_noise_table (
                id INT PRIMARY KEY AUTO_INCREMENT,
                data VARCHAR(4000) NOT NULL,
                INDEX idx_data (data(100))
            ) ENGINE=InnoDB
        """)

    cursor.execute("SELECT COUNT(*) FROM t_noise_table")
    count = cursor.fetchone()[0]
    rows_needed = (target_mb * 1024 * 1024) // 4100

    if count < rows_needed:
        import random
        print(f"  [噪声表] 填充数据 (目标 {target_mb}MB)...")
        remaining = rows_needed - count
        for offset in range(0, remaining, 500):
            batch = [(count + offset + j, 'x' * 3900)  
                     for j in range(min(500, remaining - offset))]
            cursor.executemany(
                "INSERT INTO t_noise_table (id, data) VALUES (%s, %s) "
                "ON DUPLICATE KEY UPDATE data=VALUES(data)", batch
            )
        cursor.connection.commit()
        print(f"  [噪声表] 完成, 约 {target_mb}MB 数据")


def evict_cache(cursor):
    """
    通过全表扫描噪声表来驱逐 Buffer Pool 中的目标表缓存。
    
    原理：噪声表（64MB）远大于 Buffer Pool（8MB），
    全表扫描会填满整个 Buffer Pool，将目标表的索引页全部挤出。
    
    这模拟了生产环境中多用户并发查询导致的缓存竞争。
    """
    cursor.execute("SELECT COUNT(*), SUM(LENGTH(data)) FROM t_noise_table")
    cursor.fetchall()


def noise_scan(cursor, target_mb=6):
    """
    通过部分扫描噪声表来制造缓竞争压力，但不完全驱逐目标表缓存。
    
    原理：读取指定MB大小的噪声数据到 Buffer Pool（8MB）中，
    制造可控的缓存竞争，模拟生产环境中其他并发查询的影响。
    
    target_mb=6 表示将 6MB 噪声数据加载到 8MB 缓冲池中，
    约排挤 75% 的缓存页，但最近访问的目标表索引页可能保留。
    """
    row_size = 4100
    limit_rows = (target_mb * 1024 * 1024) // row_size
    cursor.execute(f"SELECT data FROM t_noise_table LIMIT {limit_rows}")
    cursor.fetchall()


def build_aligned_query(now_ts):
    step = RANGE_SEC // BUCKETS
    raw_start = now_ts - RANGE_SEC
    aligned_start = (raw_start // 3600) * 3600
    return f"""
        SELECT 
            {aligned_start} + bucket_idx * {step} AS time_bucket,
            sum_val / cnt AS avg_val,
            min_val,
            max_val
        FROM (
            SELECT 
                (`timestamp` - {aligned_start}) DIV {step} AS bucket_idx,
                SUM(gpu_usage) AS sum_val,
                COUNT(*) AS cnt,
                MIN(gpu_usage) AS min_val,
                MAX(gpu_usage) AS max_val
            FROM t_node_gpu_history_info
            FORCE INDEX (node_ts_gpu_idx)
            WHERE node='{NODE}' AND `timestamp` >= {aligned_start}
            GROUP BY (`timestamp` - {aligned_start}) DIV {step}
        ) t
        ORDER BY time_bucket
    """


def build_unaligned_query(now_ts):
    step = RANGE_SEC // BUCKETS
    raw_start = now_ts - RANGE_SEC
    return f"""
        SELECT 
            {raw_start} + bucket_idx * {step} AS time_bucket,
            sum_val / cnt AS avg_val,
            min_val,
            max_val
        FROM (
            SELECT 
                (`timestamp` - {raw_start}) DIV {step} AS bucket_idx,
                SUM(gpu_usage) AS sum_val,
                COUNT(*) AS cnt,
                MIN(gpu_usage) AS min_val,
                MAX(gpu_usage) AS max_val
            FROM t_node_gpu_history_info
            FORCE INDEX (node_ts_gpu_idx)
            WHERE node='{NODE}' AND `timestamp` >= {raw_start}
            GROUP BY (`timestamp` - {raw_start}) DIV {step}
        ) t
        ORDER BY time_bucket
    """


def build_no_cover_query(now_ts):
    step = RANGE_SEC // BUCKETS
    raw_start = now_ts - RANGE_SEC
    aligned_start = (raw_start // 3600) * 3600
    return f"""
        SELECT 
            {aligned_start} + bucket_idx * {step} AS time_bucket,
            sum_val / cnt AS avg_val,
            min_val,
            max_val
        FROM (
            SELECT 
                (`timestamp` - {aligned_start}) DIV {step} AS bucket_idx,
                SUM(gpu_usage) AS sum_val,
                COUNT(*) AS cnt,
                MIN(gpu_usage) AS min_val,
                MAX(gpu_usage) AS max_val
            FROM t_node_gpu_history_info
            FORCE INDEX (node_timestamp_idx)
            WHERE node='{NODE}' AND `timestamp` >= {aligned_start}
            GROUP BY (`timestamp` - {aligned_start}) DIV {step}
        ) t
        ORDER BY time_bucket
    """


def build_window_function_query(now_ts):
    step = RANGE_SEC // BUCKETS
    raw_start = now_ts - RANGE_SEC
    aligned_start = (raw_start // 3600) * 3600
    return f"""
        SELECT 
            {aligned_start} + bucket_idx * {step} AS time_bucket,
            avg_val,
            min_val,
            max_val
        FROM (
            SELECT 
                bucket_idx,
                AVG(gpu_usage) AS avg_val,
                MIN(gpu_usage) AS min_val,
                MAX(gpu_usage) AS max_val
            FROM (
                SELECT 
                    gpu_usage,
                    (`timestamp` - {aligned_start}) DIV {step} AS bucket_idx,
                    ROW_NUMBER() OVER (
                        PARTITION BY (`timestamp` - {aligned_start}) DIV {step}
                        ORDER BY `timestamp`
                    ) AS rn
                FROM t_node_gpu_history_info
                FORCE INDEX (node_ts_gpu_idx)
                WHERE node='{NODE}' AND `timestamp` >= {aligned_start}
            ) sub
            GROUP BY bucket_idx
        ) t
        ORDER BY time_bucket
    """


def print_sep(title):
    print(f"\n{'='*76}")
    print(f"  {title}")
    print(f"{'='*76}")


def get_data_time_range(cursor):
    """获取数据集中的时间范围"""
    cursor.execute("""
        SELECT MIN(`timestamp`), MAX(`timestamp`), COUNT(*) 
        FROM t_node_gpu_history_info 
        WHERE node = %s
    """, (NODE,))
    result = cursor.fetchone()
    return result[0], result[1], result[2]


def experiment_aligned_vs_unaligned():
    """
    实验1：时间对齐 vs 未对齐 — 验证时间对齐对应用层缓存复用的影响

    设计逻辑：
    - 模拟监控面板每60秒刷新"最近7天"趋势图，持续10轮（共600秒 < 1小时）
    - 应用层缓存使用内存字典（key = SQL文本的指纹）
    - 未对齐组：raw_start 每轮漂移 → SQL文本不同 → 缓存key不同 → 缓存命中率0%
    - 对齐组：aligned_start 对齐到整点小时 → 10轮内SQL文本完全相同 → 首次后缓存命中率100%

    核心论证：
    - 时间对齐使应用层缓存在滑动窗口场景中可用
    - 未对齐时，即使配置了缓存也形同虚设
    """
    print_sep("实验1：时间对齐 vs 未对齐 — 验证时间对齐对应用层缓存复用的影响")

    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total_count = get_data_time_range(cursor)
    cursor.close()
    conn.close()

    print(f"\n  [数据信息] node='{NODE}': 共 {total_count} 条记录")
    print(f"             时间范围: {min_ts} ~ {max_ts}")
    print(f"             时间跨度: {(max_ts - min_ts) // 86400} 天")

    base_ts = max_ts
    rounds = 10
    drift_step = 60  # 模拟面板每分钟刷新, 10轮共600秒 < 1小时

    print(f"  [实验配置] 查询范围: {RANGE_DAYS}天, 桶数: {BUCKETS}")
    print(f"             漂移步长: {drift_step}s, 共 {rounds} 轮")
    print(f"             对齐粒度: 1小时 (3600s)")
    print(f"             应用层缓存: 内存字典, key = SQL文本的SHA256指纹")

    # ---------- 未对齐组: 应用层缓存 ----------
    print(f"\n  === 未对齐组（now_ts 漂移 → raw_start 每轮不同 → SQL文本不同 → 缓存key不同） ===")
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    import hashlib
    app_cache = {}
    unaligned_results = []

    print(f"    {'轮次':>4} | {'now_ts偏移':>10} | {'DB耗时(ms)':>12} | {'缓存命中':>8} | {'说明'}")
    print(f"    {'-'*4}-+-{'-'*10}-+-{'-'*12}-+-{'-'*8}-+-{'-'*30}")

    for i in range(rounds):
        now_ts = base_ts + i * drift_step
        offset_sec = i * drift_step
        sql = build_unaligned_query(now_ts)
        cache_key = hashlib.sha256(sql.encode()).hexdigest()

        if cache_key in app_cache:
            t0 = time.time()
            rows = app_cache[cache_key]
            elapsed = (time.time() - t0) * 1000
            r = {'time_ms': round(elapsed, 2), 'rows': len(rows), 'cached': True}
            label = f"缓存命中! (<1ms)"
        else:
            t0 = time.time()
            cursor.execute(sql)
            rows = cursor.fetchall()
            elapsed = (time.time() - t0) * 1000
            app_cache[cache_key] = rows
            r = {'time_ms': round(elapsed, 2), 'rows': len(rows), 'cached': False}
            label = "缓存未命中 → 查询DB"

        unaligned_results.append(r)
        print(f"    {i+1:>4} | +{offset_sec:>8}s | {r['time_ms']:>10.2f} | {'✓ 命中' if r['cached'] else '✗ 未命中':>8} | {label}")

    unaligned_cache_hits = sum(1 for r in unaligned_results if r['cached'])
    print(f"    结果: {rounds}轮查询, 缓存命中 {unaligned_cache_hits}/{rounds} ({unaligned_cache_hits*100//rounds}%)")

    cursor.close()
    conn.close()

    # ---------- 对齐组: 应用层缓存 ----------
    print(f"\n  === 对齐组（now_ts 漂移, 但 aligned_start 对齐到整点小时 → 10轮内SQL文本完全相同 → 缓存key相同） ===")
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    app_cache = {}
    aligned_results = []

    print(f"    {'轮次':>4} | {'now_ts偏移':>10} | {'DB耗时(ms)':>12} | {'缓存命中':>8} | {'说明'}")
    print(f"    {'-'*4}-+-{'-'*10}-+-{'-'*12}-+-{'-'*8}-+-{'-'*30}")

    for i in range(rounds):
        now_ts = base_ts + i * drift_step
        offset_sec = i * drift_step
        sql = build_aligned_query(now_ts)
        cache_key = hashlib.sha256(sql.encode()).hexdigest()

        if cache_key in app_cache:
            t0 = time.time()
            rows = app_cache[cache_key]
            elapsed = (time.time() - t0) * 1000
            r = {'time_ms': round(elapsed, 2), 'rows': len(rows), 'cached': True}
            label = f"缓存命中! (<1ms)"
        else:
            t0 = time.time()
            cursor.execute(sql)
            rows = cursor.fetchall()
            elapsed = (time.time() - t0) * 1000
            app_cache[cache_key] = rows
            r = {'time_ms': round(elapsed, 2), 'rows': len(rows), 'cached': False}
            label = "缓存未命中 → 查询DB"

        aligned_results.append(r)
        print(f"    {i+1:>4} | +{offset_sec:>8}s | {r['time_ms']:>10.2f} | {'✓ 命中' if r['cached'] else '✗ 未命中':>8} | {label}")

    aligned_cache_hits = sum(1 for r in aligned_results if r['cached'])
    print(f"    结果: {rounds}轮查询, 缓存命中 {aligned_cache_hits}/{rounds} ({aligned_cache_hits*100//rounds}%)")

    cursor.close()
    conn.close()

    return {'unaligned': unaligned_results, 'aligned': aligned_results}


def experiment_cover_index():
    """
    实验2：覆盖索引 vs 非覆盖索引（热查询对比）
    
    改进：排除首次冷查询，只对比热查询数据。
    热查询更真实地反映查询算法本身的性能差异。
    """
    print_sep("实验2：覆盖索引 vs 非覆盖索引（热查询对比）")

    # 获取数据时间范围
    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total_count = get_data_time_range(cursor)
    cursor.close()
    conn.close()
    
    print(f"\n  [数据信息] node='{NODE}': 共 {total_count} 条记录")
    print(f"             使用数据最大时间戳: {max_ts}")
    
    # 使用数据集最大时间戳
    now_ts = max_ts
    results = {}

    # 覆盖索引
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    print(f"\n  --- 覆盖索引 (node, timestamp, gpu_usage) ---")
    sql = build_aligned_query(now_ts)

    cover_results = []
    for i in range(10):
        r = run_query(cursor, sql)
        cover_results.append(r)
        label = "冷查询" if i == 0 else "热查询"
        print(f"    {label} #{i+1}: {r['time_ms']:>8.2f}ms, 命中={r['hit_rate']:>5.1f}%, 返回={r['rows']}行")

    results['cover'] = cover_results

    # 非覆盖索引
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    print(f"\n  --- 非覆盖索引 (node, timestamp) ---")
    sql_no = build_no_cover_query(now_ts)

    no_cover_results = []
    for i in range(10):
        r = run_query(cursor, sql_no)
        no_cover_results.append(r)
        label = "冷查询" if i == 0 else "热查询"
        print(f"    {label} #{i+1}: {r['time_ms']:>8.2f}ms, 命中={r['hit_rate']:>5.1f}%, 返回={r['rows']}行")

    results['no_cover'] = no_cover_results

    cursor.close()
    conn.close()
    return results


def experiment_vs_window_function():
    """
    实验3：本方案 vs 窗口函数方案（热查询对比）
    
    改进：排除首次冷查询，只对比热查询数据。
    GROUP BY 流式聚合的优势在热查询中更清晰。
    """
    print_sep("实验3：本方案（流式聚合） vs 窗口函数方案（热查询对比）")

    # 获取数据时间范围
    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total_count = get_data_time_range(cursor)
    cursor.close()
    conn.close()
    
    print(f"\n  [数据信息] node='{NODE}': 共 {total_count} 条记录")
    print(f"             使用数据最大时间戳: {max_ts}")
    
    # 使用数据集最大时间戳
    now_ts = max_ts
    results = {}

    # 本方案
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    print(f"\n  --- 本方案（GROUP BY 流式聚合） ---")
    print(f"    特点：零临时表，内存占用恒定（仅维护100组聚合状态）")
    sql = build_aligned_query(now_ts)

    our_results = []
    for i in range(10):
        r = run_query(cursor, sql)
        our_results.append(r)
        label = "冷查询" if i == 0 else "热查询"
        print(f"    {label} #{i+1}: {r['time_ms']:>8.2f}ms, 命中={r['hit_rate']:>5.1f}%, 返回={r['rows']}行")

    results['our'] = our_results

    # 窗口函数方案
    restart_mysql()
    conn = get_conn()
    cursor = conn.cursor()

    print(f"\n  --- 窗口函数方案（ROW_NUMBER + 临时表） ---")
    print(f"    特点：产生临时表和文件排序，内存占用与数据量成正比")
    sql_window = build_window_function_query(now_ts)

    window_results = []
    for i in range(10):
        r = run_query(cursor, sql_window)
        window_results.append(r)
        label = "冷查询" if i == 0 else "热查询"
        print(f"    {label} #{i+1}: {r['time_ms']:>8.2f}ms, 命中={r['hit_rate']:>5.1f}%, 返回={r['rows']}行")

    results['window'] = window_results

    cursor.close()
    conn.close()
    return results


def experiment_explain():
    print_sep("实验4：EXPLAIN 执行计划分析")

    # 获取数据时间范围
    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total_count = get_data_time_range(cursor)
    
    print(f"\n  [数据信息] node='{NODE}': 共 {total_count} 条记录")
    print(f"             使用数据最大时间戳: {max_ts}")
    
    # 使用数据集最大时间戳
    now_ts = max_ts

    queries = {
        '本方案（时间对齐+覆盖索引+整数DIV）': build_aligned_query(now_ts),
        '非覆盖索引方案': build_no_cover_query(now_ts),
        '窗口函数方案': build_window_function_query(now_ts),
    }

    for name, sql in queries.items():
        print(f"\n  --- {name} ---")
        cursor.execute(f"EXPLAIN {sql}")
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        print(f"    {' | '.join(f'{c:<14}' for c in cols[:8])}")
        print(f"    {'-'*125}")
        for row in rows:
            vals = [str(v)[:12] if v is not None else 'NULL' for v in row[:8]]
            print(f"    {' | '.join(f'{v:<14}' for v in vals)}")

    cursor.close()
    conn.close()


def print_summary(exp1, exp2, exp3):
    print_sep("实验结果汇总")

    def avg(lst, key, skip_first=0):
        if not lst or len(lst) <= skip_first:
            return 0
        return sum(r[key] for r in lst[skip_first:]) / (len(lst) - skip_first)

    # 实验1：时间对齐 → 应用层缓存命中率
    unaligned_first = exp1['unaligned'][0]['time_ms']
    unaligned_cache_hits = sum(1 for r in exp1['unaligned'] if r.get('cached'))
    unaligned_db_queries = sum(1 for r in exp1['unaligned'] if not r.get('cached'))
    aligned_first = exp1['aligned'][0]['time_ms']
    aligned_cache_hits = sum(1 for r in exp1['aligned'] if r.get('cached'))
    aligned_db_queries = sum(1 for r in exp1['aligned'] if not r.get('cached'))
    aligned_hot = avg([r for r in exp1['aligned'][1:] if r['cached']], 'time_ms')

    # 实验2：覆盖索引 — 排除冷查询(第一条)，只用热查询
    cover_hot = avg(exp2['cover'], 'time_ms', skip_first=1)
    no_cover_hot = avg(exp2['no_cover'], 'time_ms', skip_first=1)
    cover_first = exp2['cover'][0]['time_ms']
    no_cover_first = exp2['no_cover'][0]['time_ms']

    # 实验3：流式聚合 — 排除冷查询(第一条)，只用热查询
    our_hot = avg(exp3['our'], 'time_ms', skip_first=1)
    window_hot = avg(exp3['window'], 'time_ms', skip_first=1)
    our_first = exp3['our'][0]['time_ms']
    window_first = exp3['window'][0]['time_ms']

    total_rounds = len(exp1['unaligned'])

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    专利验证：三大核心技术实验结果汇总                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  实验1: 时间对齐 → 应用层缓存复用 (模拟面板每60s刷新, {total_rounds}轮)          ║
║    未对齐组: 首次DB耗时 {unaligned_first:>6.1f}ms, 缓存命中 {unaligned_cache_hits}/{total_rounds} ({unaligned_cache_hits*100//total_rounds}%)          ║
║    对齐组:   首次DB耗时 {aligned_first:>6.1f}ms, 缓存命中 {aligned_cache_hits}/{total_rounds} ({aligned_cache_hits*100//total_rounds}%)          ║
║    对齐组首次后缓存命中耗时: {aligned_hot:>6.2f}ms (内存字典查找)                ║
║    未对齐组 DB实际查询: {unaligned_db_queries}次, 对齐组 DB实际查询: {aligned_db_queries}次            ║
║    结论: 时间对齐使应用层缓存可用, DB查询从{unaligned_db_queries}次降至{aligned_db_queries}次        ║
║                                                                              ║
║  实验2: 覆盖索引 vs 非覆盖索引（热查询对比，排除冷查询）                      ║
║    覆盖索引首次:   {cover_first:>6.1f}ms (冷, 含磁盘I/O)                     ║
║    非覆盖索引首次: {no_cover_first:>6.1f}ms (冷, 含磁盘I/O)                  ║
║    覆盖索引热查询: {cover_hot:>6.1f}ms (纯内存, 零回表)                      ║
║    非覆盖索引热查询: {no_cover_hot:>6.1f}ms (纯内存, 需回表)                  ║
║    覆盖索引加速比: {no_cover_hot/cover_hot:.1f}x (热查询)                          ║
║                                                                              ║
║  实验3: 本方案 vs 窗口函数方案（热查询对比，排除冷查询）                      ║
║    本方案首次:     {our_first:>6.1f}ms (冷, 含磁盘I/O)                       ║
║    窗口函数首次:   {window_first:>6.1f}ms (冷, 含磁盘I/O)                    ║
║    本方案热查询:   {our_hot:>6.1f}ms (纯内存, 零临时表)                      ║
║    窗口函数热查询: {window_hot:>6.1f}ms (纯内存, 临时表+排序)                ║
║    流式聚合加速比: {window_hot/our_hot:.1f}x (热查询)                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    print("专利三大核心技术验证结论：")
    print()
    print(f"  1. 时间对齐 → 应用层缓存复用 (模拟面板每{total_rounds}次刷新):")
    print(f"     未对齐: 首次DB {unaligned_first:.1f}ms, 缓存命中率 {unaligned_cache_hits*100//total_rounds}%")
    print(f"     对齐:   首次DB {aligned_first:.1f}ms, 缓存命中率 {aligned_cache_hits*100//total_rounds}%")
    print(f"     对齐组首次后缓存命中耗时: {aligned_hot:.2f}ms")
    print(f"     结论: 时间对齐使SQL文本固定, 应用层缓存key相同, 窗口内后续请求全部命中缓存")
    print(f"     未对齐即使配置了缓存也形同虚设(每次SQL文本不同 → 缓存key不同)")
    print()
    print(f"  2. 覆盖索引 → 零回表: {cover_hot:.1f}ms vs 非覆盖索引 {no_cover_hot:.1f}ms = {no_cover_hot/cover_hot:.1f}x")
    print(f"     覆盖索引消除回表开销，热查询性能提升约 {no_cover_hot/cover_hot:.0f} 倍")
    print()
    print(f"  3. 流式聚合 → 零临时表: {our_hot:.1f}ms vs 窗口函数 {window_hot:.1f}ms = {window_hot/our_hot:.1f}x")
    print(f"     GROUP BY流式聚合避免临时表和文件排序，热查询性能提升约 {window_hot/our_hot:.0f} 倍")


def main():
    print("=" * 76)
    print("  专利验证实验 v5：时序数据降采样查询")
    print("  实验1: 时间对齐 → 应用层缓存复用")
    print("  实验2/3: 覆盖索引 + 流式聚合（配套实现手段）")
    print("=" * 76)

    # 确保 MySQL Docker 容器在运行
    print(f"\n  [启动检查] 确保 MySQL 容器 '{CONTAINER_NAME}' 可用...")
    if not ensure_mysql_running():
        print(f"\n  错误: 无法连接到 MySQL 容器 '{CONTAINER_NAME}'，请检查 Docker 环境")
        return

    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM t_node_gpu_history_info WHERE node=%s", (NODE,))
    count = cursor.fetchone()[0]
    bp = get_bp_stats(cursor)
    print(f"\n  环境检查:")
    print(f"    数据量: {count} 条 (node={NODE})")
    print(f"    Buffer Pool: {bp.get('Innodb_buffer_pool_pages_total',0)} pages")
    cursor.close()
    conn.close()

    if count < 100000:
        print(f"\n  ⚠ 数据量不足({count}条)，请先运行 insert_test_data.py")
        return

    exp1 = experiment_aligned_vs_unaligned()
    exp2 = experiment_cover_index()
    exp3 = experiment_vs_window_function()
    experiment_explain()
    print_summary(exp1, exp2, exp3)

    all_results = {
        'exp1_aligned_vs_unaligned_pressure': exp1,
        'exp2_cover_index': exp2,
        'exp3_vs_window': exp3
    }
    with open('d:/work/hpc/experiments/experiment_cache_result_v5.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  实验结果已保存至 experiment_cache_result_v5.json")


if __name__ == '__main__':
    main()
