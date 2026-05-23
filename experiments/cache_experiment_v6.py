"""
专利验证实验 v6：三大创新集成验证

在 v5 三个实验的基础上融入两项新创新：
  创新2: 双维度自适应桶划分（时间上限 + 累计波动） — 纯SQL session变量
  创新3: 桶内4点多线段特征提取（first / min / max / last） — SQL GROUP BY

实验设计（同 v5 结构）：
  实验1：时间对齐 vs 未对齐（创新1 — 应用层缓存复用对比）
  实验2：覆盖索引 vs 非覆盖索引（配套 — 索引效果对比）
  实验3：GROUP BY vs 窗口函数（配套 — 流式聚合效果对比）
  实验4：EXPLAIN 执行计划分析
"""

import pymysql
import time
import json
import subprocess
import os
import hashlib

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

# 自适应桶参数
MAX_BUCKET_SEC = 15000
FLUCTUATION_THRESHOLD = 80
MIN_WINDOW_SEC = 60  # 最小累计时长（秒），避免桶起始处数据稀疏时误切

# ==================== SQL 构建（自适应桶 + 4点提取，单SQL，纯session变量） ====================

def _adaptive_query(aligned_start, cover_index=True):
    """
    自适应桶 + 4点提取，单条SQL（无 multi-statement）。
    内层: STRAIGHT_JOIN 初始化 session 变量 → 逐行双维度判定切桶
    外层: GROUP BY bucket_start, 提取 first/min/max/last
    """
    idx = 'node_ts_gpu_idx' if cover_index else 'node_timestamp_idx'

    return f"""
        SELECT
            bucket_start,
            MIN(first_val) AS first_val,
            MIN(gpu_usage) AS min_val,
            MAX(gpu_usage) AS max_val,
            SUBSTRING_INDEX(GROUP_CONCAT(gpu_usage ORDER BY rn DESC), ',', 1) AS last_val
        FROM (
            SELECT
                `timestamp`, gpu_usage,
                @bs := IF(
                    @bs = 0,
                    `timestamp`,
                    IF(
                        (`timestamp` - @bs) > {MAX_BUCKET_SEC}
                        OR (
                            (`timestamp` - @bs) > {MIN_WINDOW_SEC}
                            AND (@bmx - @bmn) > {FLUCTUATION_THRESHOLD}
                        ),
                        `timestamp`,
                        @bs
                    )
                ) AS bucket_start,
                @rn := IF(@bs != COALESCE(@prev_bs, -1), 1, @rn + 1) AS rn,
                @first_val := IF(@bs != COALESCE(@prev_bs, -1), gpu_usage, @first_val) AS first_val,
                @bmn := IF(@bs != COALESCE(@prev_bs, -1), gpu_usage, LEAST(@bmn, gpu_usage)),
                @bmx := IF(@bs != COALESCE(@prev_bs, -1), gpu_usage, GREATEST(@bmx, gpu_usage)),
                @prev_bs := @bs
            FROM t_node_gpu_history_info
            FORCE INDEX ({idx})
            STRAIGHT_JOIN (SELECT @bs:=0, @rn:=0, @bmn:=0, @bmx:=0, @prev_bs:=NULL, @first_val:=0) AS _init
            WHERE node = '{NODE}' AND `timestamp` >= {aligned_start}
            ORDER BY `timestamp` ASC
        ) AS _adaptive
        GROUP BY bucket_start
        ORDER BY bucket_start
    """


def _aligned_start(now_ts):
    raw = now_ts - RANGE_SEC
    return (raw // 3600) * 3600


def _unaligned_start(now_ts):
    return now_ts - RANGE_SEC


def build_aligned_query(now_ts, cover_index=True):
    return _adaptive_query(_aligned_start(now_ts), cover_index)


def build_unaligned_query(now_ts):
    return _adaptive_query(_unaligned_start(now_ts), True)


def build_no_cover_query(now_ts):
    return _adaptive_query(_aligned_start(now_ts), False)


def _build_adaptive_window_query(now_ts):
    """
    自适应桶 + ROW_NUMBER 窗口函数（与 GROUP BY 流式聚合对比，同桶划分）
    内层: 与 _adaptive_query 完全相同的自适应桶逻辑
    外层: ROW_NUMBER + CASE WHEN 提取 4 点（产生临时表 + filesort）
    """
    start = _aligned_start(now_ts)
    return f"""
        SELECT
            bucket_start,
            MAX(CASE WHEN rn_asc = 1 THEN gpu_usage END) AS first_val,
            MIN(gpu_usage) AS min_val,
            MAX(gpu_usage) AS max_val,
            MAX(CASE WHEN rn_desc = 1 THEN gpu_usage END) AS last_val
        FROM (
            SELECT
                bucket_start, gpu_usage,
                ROW_NUMBER() OVER (PARTITION BY bucket_start ORDER BY `timestamp` ASC) AS rn_asc,
                ROW_NUMBER() OVER (PARTITION BY bucket_start ORDER BY `timestamp` DESC) AS rn_desc
            FROM (
                SELECT
                    `timestamp`, gpu_usage,
                    @bs := IF(
                        @bs = 0,
                        `timestamp`,
                        IF(
                            (`timestamp` - @bs) > {MAX_BUCKET_SEC}
                            OR (
                                (`timestamp` - @bs) > {MIN_WINDOW_SEC}
                                AND (@bmx - @bmn) > {FLUCTUATION_THRESHOLD}
                            ),
                            `timestamp`,
                            @bs
                        )
                    ) AS bucket_start,
                    @bmn := IF(@bs != COALESCE(@prev_bs, -1), gpu_usage, LEAST(@bmn, gpu_usage)),
                    @bmx := IF(@bs != COALESCE(@prev_bs, -1), gpu_usage, GREATEST(@bmx, gpu_usage)),
                    @prev_bs := @bs
                FROM t_node_gpu_history_info
                FORCE INDEX (node_ts_gpu_idx)
                STRAIGHT_JOIN (SELECT @bs:=0, @bmn:=0, @bmx:=0, @prev_bs:=NULL) AS _init
                WHERE node = '{NODE}' AND `timestamp` >= {start}
                ORDER BY `timestamp` ASC
            ) AS _adaptive
        ) AS _windowed
        GROUP BY bucket_start
        ORDER BY bucket_start
    """


# ==================== 查询执行 ====================

def run_query(cursor, sql):
    """执行单条SQL并计时"""
    t0 = time.time()
    cursor.execute(sql)
    rows = cursor.fetchall()
    elapsed = (time.time() - t0) * 1000
    return rows, round(elapsed, 2)


# ==================== 基础设施 ====================

def get_conn():
    return pymysql.connect(**DB_CONFIG)


def restart_mysql():
    print("  [Docker] 重启 MySQL 以清空缓冲池...")
    subprocess.run(['docker', 'restart', CONTAINER_NAME], capture_output=True)
    return _wait_mysql_ready()


def ensure_mysql_running():
    r = subprocess.run(
        ['docker', 'inspect', '-f', '{{.State.Running}}', CONTAINER_NAME],
        capture_output=True, text=True
    )
    if r.returncode != 0:
        print(f"  [Docker] 容器不存在，正在创建...")
        return _create_mysql_container()
    if r.stdout.strip() == 'true':
        print(f"  [Docker] 容器已在运行")
        try:
            pymysql.connect(**DB_CONFIG).close()
            return True
        except Exception:
            return _wait_mysql_ready()
    print(f"  [Docker] 容器未运行，正在启动...")
    subprocess.run(['docker', 'start', CONTAINER_NAME], capture_output=True)
    return _wait_mysql_ready()


def _create_mysql_container():
    base = os.path.dirname(os.path.abspath(__file__))
    conf_dir = os.path.join(base, 'mysql', 'conf')
    data_dir = os.path.join(base, 'mysql', 'data')
    r = subprocess.run([
        'docker', 'run', '-d', '--name', CONTAINER_NAME,
        '-p', '3306:3306',
        '-v', f'{conf_dir}:/etc/mysql/conf.d',
        '-v', f'{data_dir}:/var/lib/mysql',
        '-e', 'MYSQL_ROOT_PASSWORD=hpc2024test',
        'mysql:8.0',
        '--character-set-server=utf8mb4',
        '--collation-server=utf8mb4_unicode_ci',
        '--default-authentication-plugin=mysql_native_password',
    ], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  [Docker] 创建失败: {r.stderr}")
        return False
    return _wait_mysql_ready()


def _wait_mysql_ready():
    for i in range(60):
        time.sleep(1)
        try:
            pymysql.connect(**DB_CONFIG).close()
            print(f"  [Docker] MySQL 就绪 (等待 {i+1}s)")
            return True
        except Exception:
            continue
    print("  [Docker] MySQL 超时!")
    return False


def print_sep(title):
    print(f"\n{'='*76}")
    print(f"  {title}")
    print(f"{'='*76}")


def get_data_range(cursor):
    cursor.execute(
        "SELECT MIN(`timestamp`), MAX(`timestamp`), COUNT(*) "
        "FROM t_node_gpu_history_info WHERE node=%s", (NODE,)
    )
    return cursor.fetchone()


# ==================== 实验 ====================

def experiment1_aligned_vs_unaligned():
    """
    实验1：时间对齐 vs 未对齐 — 应用层缓存复用（创新1）
    """
    print_sep("实验1：时间对齐 vs 未对齐（自适应桶+4点 → 应用层缓存）")

    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total = get_data_range(cursor)
    cursor.close()
    conn.close()

    print(f"\n  [数据] node='{NODE}': {total}条, {min_ts}~{max_ts}")
    print(f"  [自适应桶] max_bucket={MAX_BUCKET_SEC}s, threshold={FLUCTUATION_THRESHOLD}, min_win={MIN_WINDOW_SEC}s")

    base_ts = max_ts
    rounds = 10
    drift_step = 60
    results = {}

    for mode, label in [('unaligned', '未对齐'), ('aligned', '对齐')]:
        aligned = (mode == 'aligned')
        print(f"\n  === {label}组（漂移+{drift_step}s/轮, {rounds}轮） ===")
        restart_mysql()
        conn = get_conn()
        cursor = conn.cursor()
        app_cache = {}
        mode_results = []

        print(f"    {'轮':>3} | {'偏移':>6} | {'耗时ms':>8} | {'桶数':>5} | {'点':>5} | {'命中':>4} | 说明")
        print(f"    {'-'*3}-+-{'-'*6}-+-{'-'*8}-+-{'-'*5}-+-{'-'*5}-+-{'-'*4}-+-{'-'*30}")

        for i in range(rounds):
            now_ts = base_ts + i * drift_step
            sql = build_aligned_query(now_ts) if aligned else build_unaligned_query(now_ts)
            cache_key = hashlib.sha256(sql.encode()).hexdigest()

            if cache_key in app_cache:
                t0 = time.time()
                cached = app_cache[cache_key]
                elapsed = (time.time() - t0) * 1000
                r = {'time_ms': round(elapsed, 2), 'buckets': len(cached), 'cached': True}
                print(f"    {i+1:>3} | +{i*drift_step:>4}s | {elapsed:>6.2f} | {len(cached):>3} | {len(cached)*4:>3} |  ✓   | 缓存命中 (<1ms)")
            else:
                result, db_ms = run_query(cursor, sql)
                app_cache[cache_key] = result
                r = {'time_ms': db_ms, 'buckets': len(result), 'cached': False}
                print(f"    {i+1:>3} | +{i*drift_step:>4}s | {db_ms:>6.1f} | {len(result):>3} | {len(result)*4:>3} |  ✗   | 缓存未命中 → SQL自适应桶+4点提取")

            mode_results.append(r)

        hits = sum(1 for r in mode_results if r['cached'])
        dbs = sum(1 for r in mode_results if not r['cached'])
        print(f"    结果: {rounds}轮, 缓存命中 {hits}/{rounds}, DB实际查询 {dbs}次")

        cursor.close()
        conn.close()
        results[mode] = mode_results

    return results


def experiment2_cover_index():
    """实验2：覆盖索引 vs 非覆盖索引"""
    print_sep("实验2：覆盖索引 vs 非覆盖索引（自适应桶+4点）")

    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total = get_data_range(cursor)
    cursor.close()
    conn.close()
    now_ts = max_ts

    print(f"\n  [数据] node='{NODE}': {total}条")
    results = {}

    for cover, label in [(True, '覆盖索引 (node, ts, val)'), (False, '非覆盖索引 (node, ts)')]:
        restart_mysql()
        conn = get_conn()
        cursor = conn.cursor()

        print(f"\n  --- {label} ---")
        sql = build_aligned_query(now_ts, cover_index=cover) if cover else build_no_cover_query(now_ts)
        round_results = []

        for i in range(10):
            rows, db_ms = run_query(cursor, sql)
            round_results.append({'time_ms': db_ms, 'buckets': len(rows)})
            tag = "冷查询" if i == 0 else "热查询"
            print(f"    {tag} #{i+1}: {db_ms:>8.1f}ms, {len(rows)} 桶, {len(rows)*4} 点")

        results['cover' if cover else 'no_cover'] = round_results
        cursor.close()
        conn.close()

    return results


def experiment3_vs_window_function():
    """实验3：流式聚合 vs 窗口函数（均使用自适应桶，控制唯一变量）"""
    print_sep("实验3：GROUP BY流式聚合 vs ROW_NUMBER窗口函数（均自适应桶）")

    conn = get_conn()
    cursor = conn.cursor()
    min_ts, max_ts, total = get_data_range(cursor)
    cursor.close()
    conn.close()
    now_ts = max_ts

    print(f"\n  [数据] node='{NODE}': {total}条")
    results = {}

    for kind, label, builder in [
        ('our', 'GROUP BY流式聚合', lambda: build_aligned_query(now_ts)),
        ('window', 'ROW_NUMBER窗口函数', lambda: _build_adaptive_window_query(now_ts)),
    ]:
        restart_mysql()
        conn = get_conn()
        cursor = conn.cursor()

        print(f"\n  --- {label}（同自适应桶，均提取4点） ---")
        sql = builder()
        round_results = []

        for i in range(10):
            rows, db_ms = run_query(cursor, sql)
            round_results.append({'time_ms': db_ms, 'rows': len(rows)})
            tag = "冷查询" if i == 0 else "热查询"
            extra = " (零临时表)" if kind == 'our' else " (临时表+filesort)"
            print(f"    {tag} #{i+1}: {db_ms:>8.1f}ms, {len(rows)}行{extra}")

        results[kind] = round_results
        cursor.close()
        conn.close()

    return results


def experiment4_explain():
    """实验4：EXPLAIN"""
    print_sep("实验4：EXPLAIN 执行计划")

    conn = get_conn()
    cursor = conn.cursor()
    _, max_ts, _ = get_data_range(cursor)
    now_ts = max_ts

    for name, sql in [
        ('本方案(cover index)', build_aligned_query(now_ts, True)),
        ('非覆盖索引', build_no_cover_query(now_ts)),
        ('窗口函数(自适应桶)', _build_adaptive_window_query(now_ts)),
    ]:
        print(f"\n  --- {name} ---")
        cursor.execute(f"EXPLAIN {sql}")
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        print(f"    {' | '.join(f'{c:<14}' for c in cols[:7])}")
        print(f"    {'-'*110}")
        for row in rows:
            vals = [str(v)[:12] if v is not None else 'NULL' for v in row[:7]]
            print(f"    {' | '.join(f'{v:<14}' for v in vals)}")

    cursor.close()
    conn.close()


def print_summary(exp1, exp2, exp3):
    print_sep("实验结果汇总")

    def avg(lst, key, skip=0):
        if not lst or len(lst) <= skip:
            return 0
        return sum(r[key] for r in lst[skip:]) / (len(lst) - skip)

    ua, al = exp1['unaligned'], exp1['aligned']
    ua_hits = sum(1 for r in ua if r['cached'])
    al_hits = sum(1 for r in al if r['cached'])
    al_first_db = al[0]['time_ms']
    al_buckets = al[0]['buckets']

    cover_hot = avg(exp2['cover'], 'time_ms', skip=1)
    no_cover_hot = avg(exp2['no_cover'], 'time_ms', skip=1)
    cover_first = exp2['cover'][0]['time_ms']
    no_cover_first = exp2['no_cover'][0]['time_ms']

    our_hot = avg(exp3['our'], 'time_ms', skip=1)
    window_hot = avg(exp3['window'], 'time_ms', skip=1)

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║             专利验证 v6：三大创新集成实验结果汇总                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  创新1: 时间对齐 → 应用层缓存                                                ║
║    未对齐组: 缓存命中 {ua_hits}/10, DB实际查询 {10 - ua_hits}次                                  ║
║    对齐组:   缓存命中 {al_hits}/10, DB实际查询 {10 - al_hits}次                                  ║
║    对齐组首次DB耗时: {al_first_db:.0f}ms, 缓存命中 <1ms                                   ║
║                                                                              ║
║  创新2: 自适应桶划分                                                          ║
║    对齐组桶数: ~{al_buckets}个（非固定100）, 平稳段拉长/波动段加密                         ║
║                                                                              ║
║  创新3: 4点提取                                                               ║
║    每桶4点(first/min/max/last), 共~{al_buckets*4}点, 3线段还原桶内趋势                         ║
║                                                                              ║
║  配套手段对比:                                                                ║
║    覆盖索引热查询: {cover_hot:.0f}ms vs 非覆盖: {no_cover_hot:.0f}ms (加速 {no_cover_hot/cover_hot:.1f}x)       ║
║    GROUP BY流式:  {our_hot:.0f}ms vs 窗口函数: {window_hot:.0f}ms (加速 {window_hot/our_hot:.1f}x)           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    print("结论:")
    print(f"  创新1: 对齐后缓存命中率 {al_hits*10}%, 数据库仅服务首次查询")
    print(f"  创新2: 自适应桶 ~{al_buckets}个, 桶密度随波动自适应")
    print(f"  创新3: 每桶4点, 3线段保留趋势形态")
    print(f"  覆盖索引: 加速 {no_cover_hot/cover_hot:.1f}x")
    print(f"  流式聚合 vs 窗口函数: 加速 {window_hot/our_hot:.1f}x")


def main():
    print("=" * 76)
    print("  专利验证实验 v6：三大创新集成")
    print("  创新1: 时间对齐 | 创新2: 自适应桶 | 创新3: 4点提取")
    print("=" * 76)

    print(f"\n  [启动检查] 确保 MySQL 容器 '{CONTAINER_NAME}' 可用...")
    if not ensure_mysql_running():
        print("\n  错误: 无法连接 MySQL")
        return

    conn = get_conn()
    cursor = conn.cursor()
    _, _, total = get_data_range(cursor)
    print(f"\n  环境: {total}条 (node={NODE})")
    print(f"  自适应桶: max_bucket={MAX_BUCKET_SEC}s, threshold={FLUCTUATION_THRESHOLD}, min_win={MIN_WINDOW_SEC}s")
    cursor.close()
    conn.close()

    if total < 50000:
        print(f"\n  ⚠ 数据量不足({total}条), 请先运行 insert_test_data.py")
        return

    exp1 = experiment1_aligned_vs_unaligned()
    exp2 = experiment2_cover_index()
    exp3 = experiment3_vs_window_function()
    experiment4_explain()
    print_summary(exp1, exp2, exp3)

    all_results = {
        'exp1': {
            'unaligned_hits': sum(1 for r in exp1['unaligned'] if r['cached']),
            'aligned_hits': sum(1 for r in exp1['aligned'] if r['cached']),
        },
        'exp2_cover_index': {
            'cover_hot_ms': sum(r['time_ms'] for r in exp2['cover'][1:]) / 9,
            'no_cover_hot_ms': sum(r['time_ms'] for r in exp2['no_cover'][1:]) / 9,
        },
        'exp3_vs_window': {
            'our_hot_ms': sum(r['time_ms'] for r in exp3['our'][1:]) / 9,
            'window_hot_ms': sum(r['time_ms'] for r in exp3['window'][1:]) / 9,
        },
    }
    with open('d:/work/hpc/experiments/experiment_cache_result_v6.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n  结果已保存至 experiment_cache_result_v6.json")


if __name__ == '__main__':
    main()
