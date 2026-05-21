#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL 缓存机制深度诊断
分析为什么之前实验没有体现出明显的缓存收益
"""

import pymysql
from datetime import datetime
import time

DB_CONFIG = {
    'host': '172.30.3.7',
    'port': 3306,
    'user': 'root',
    'password': 'T0*Ae8FnLPjGNEEOsi',
    'database': 'hpc',
    'charset': 'utf8mb4'
}

NODE = 'gpu6'


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def query(conn, sql, params=None):
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ============================================================
# 一、关键 MySQL 配置
# ============================================================
def diagnose_config(conn):
    section("一、MySQL InnoDB 缓存相关配置")

    vars_to_check = [
        'innodb_buffer_pool_size',
        'innodb_buffer_pool_instances',
        'innodb_buffer_pool_chunk_size',
        'innodb_old_blocks_pct',
        'innodb_old_blocks_time',
        'innodb_flush_method',
        'innodb_io_capacity',
        'innodb_read_io_threads',
        'innodb_write_io_threads',
        'innodb_buffer_pool_dump_at_shutdown',
        'innodb_buffer_pool_load_at_startup',
        'innodb_flush_log_at_trx_commit',
        'innodb_log_file_size',
        'innodb_log_buffer_size',
        'query_cache_type',
        'query_cache_size',
        'innodb_file_per_table',
        'innodb_data_file_path',
        'innodb_page_size',
        'innodb_buffer_pool_dump_pct',
        'key_buffer_size',
        'tmp_table_size',
        'max_heap_table_size',
        'innodb_adaptive_hash_index'
    ]

    for var in vars_to_check:
        rows = query(conn, f"SHOW VARIABLES LIKE '{var}'")
        if rows:
            val = rows[0]['Value']
            print(f"  {var:40s} = {val}")


# ============================================================
# 二、Buffer Pool 当前状态
# ============================================================
def diagnose_buffer_pool(conn):
    section("二、InnoDB Buffer Pool 当前状态")

    status_vars = [
        'Innodb_buffer_pool_pages_total',
        'Innodb_buffer_pool_pages_free',
        'Innodb_buffer_pool_pages_data',
        'Innodb_buffer_pool_pages_dirty',
        'Innodb_buffer_pool_pages_misc',
        'Innodb_buffer_pool_read_requests',
        'Innodb_buffer_pool_reads',
        'Innodb_buffer_pool_read_ahead',
        'Innodb_buffer_pool_read_ahead_evicted',
        'Innodb_buffer_pool_write_requests',
        'Innodb_buffer_pool_writes',
        'Innodb_buffer_pool_wait_free',
        'Innodb_buffer_pool_pages_flushed',
        'Innodb_pages_read',
        'Innodb_pages_written',
        'Innodb_data_read',
        'Innodb_data_written',
        'Innodb_data_reads',
        'Innodb_data_writes',
        'Innodb_data_fsyncs',
    ]

    for var in status_vars:
        rows = query(conn, f"SHOW STATUS LIKE '{var}'")
        if rows:
            val = rows[0]['Value']
            print(f"  {var:45s} = {val}")

    # 计算命中率
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_read%'")
    stats = {r['Variable_name']: int(r['Value']) for r in rows}
    # 计算页面使用量
    pages_total = int(stats.get('Innodb_buffer_pool_pages_total', 0))
    pages_free = int(stats.get('Innodb_buffer_pool_pages_free', 0))
    pages_data = int(stats.get('Innodb_buffer_pool_pages_data', 0))
    print(f"\n  Buffer Pool 页面分配: 总量={pages_total}页({pages_total*16/1024:.0f}MB), "
          f"空闲={pages_free}页({pages_free*16/1024:.0f}MB), "
          f"数据={pages_data}页({pages_data*16/1024:.0f}MB)")
    requests = int(stats.get('Innodb_buffer_pool_read_requests', 0))
    reads = int(stats.get('Innodb_buffer_pool_reads', 0))
    if requests > 0:
        hit_rate = (1 - reads / requests) * 100
        print(f"\n  缓冲池读命中率: {hit_rate:.2f}%")
        print(f"  逻辑读(requests): {requests:,}")
        print(f"  物理读(reads):    {reads:,}")


# ============================================================
# 三、数据量和索引大小
# ============================================================
def diagnose_data_size(conn):
    section("三、查询涉及的数据量和索引大小")

    # 表大小
    rows = query(conn, """
        SELECT
            TABLE_NAME as table_name,
            ROUND(data_length / 1024 / 1024, 2) AS data_mb,
            ROUND(index_length / 1024 / 1024, 2) AS index_mb,
            ROUND((data_length + index_length) / 1024 / 1024, 2) AS total_mb,
            table_rows
        FROM information_schema.tables
        WHERE table_schema = 'hpc'
          AND table_name = 't_node_gpu_history_info'
    """)
    for r in rows:
        print(f"  表名: {r['table_name']}")
        print(f"  数据大小: {r['data_mb']} MB")
        print(f"  索引大小: {r['index_mb']} MB")
        print(f"  总大小:   {r['total_mb']} MB")
        print(f"  估算行数: {r['table_rows']:,}")

    # gpu6 数据量
    rows = query(conn, """
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) * (
                SELECT AVG_ROW_LENGTH FROM information_schema.tables
                WHERE table_schema = 'hpc' AND table_name = 't_node_gpu_history_info'
            ) / 1024 / 1024 AS estimated_data_mb
        FROM t_node_gpu_history_info
        WHERE node = %s
    """, (NODE,))
    for r in rows:
        print(f"\n  {NODE} 总行数: {r['total_rows']:,}")
        print(f"  {NODE} 估算数据量: {r['estimated_data_mb']:.2f} MB")

    # 7天范围内的数据量
    data_range = query(conn, """
        SELECT MAX(timestamp) as max_ts FROM t_node_gpu_history_info WHERE node = %s
    """, (NODE,))

    max_ts = data_range[0]['max_ts']
    range_sec = 7 * 24 * 3600
    aligned_start = ((max_ts - range_sec) // 3600) * 3600
    aligned_end = aligned_start + range_sec

    range_rows = query(conn, """
        SELECT
            COUNT(*) AS cnt,
            MIN(timestamp) as min_ts,
            MAX(timestamp) as max_ts,
            FROM_UNIXTIME(MIN(timestamp)) as min_time,
            FROM_UNIXTIME(MAX(timestamp)) as max_time
        FROM t_node_gpu_history_info
        WHERE node = %s AND timestamp >= %s AND timestamp < %s
    """, (NODE, aligned_start, aligned_end))

    for r in range_rows:
        print(f"\n  7天查询范围 ({r['min_time']} ~ {r['max_time']}):")
        print(f"    行数: {r['cnt']:,}")
        print(f"    大约 {r['cnt'] * 16 / 1024:.0f} KB (假设每行16字节索引数据)")

    # gpu6 索引大小
    index_rows = query(conn, """
        SELECT
            index_name,
            ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
        FROM mysql.innodb_index_stats
        WHERE database_name = 'hpc'
          AND table_name = 't_node_gpu_history_info'
          AND stat_name = 'size'
        ORDER BY index_name
    """)
    print(f"\n  gpu6 相关索引大小:")
    for r in index_rows:
        print(f"    {r['index_name']}: {r['size_mb']} MB (索引页数估算)")


# ============================================================
# 四、验证 FLUSH TABLES 是否真的清除了 Buffer Pool
# ============================================================
def diagnose_flush_effect(conn):
    section("四、验证 FLUSH TABLES 对 Buffer Pool 的影响")

    # 记录当前状态
    stats_before = {}
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_data'")
    stats_before['pages_data'] = int(rows[0]['Value'])
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_free'")
    stats_before['pages_free'] = int(rows[0]['Value'])
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_reads'")
    stats_before['reads'] = int(rows[0]['Value'])

    print(f"  FLUSH 前:")
    print(f"    数据页: {stats_before['pages_data']:,}")
    print(f"    空闲页: {stats_before['pages_free']:,}")
    print(f"    累计物理读: {stats_before['reads']:,}")

    # 执行查询，加载数据到缓冲池
    query(conn, "SELECT COUNT(*) FROM t_node_gpu_history_info WHERE node = %s", (NODE,))
    time.sleep(0.5)

    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_data'")
    pages_data_loaded = int(rows[0]['Value'])
    print(f"\n  查询 gpu6 后数据页: {pages_data_loaded:,} (增加 {pages_data_loaded - stats_before['pages_data']})")

    # 执行 FLUSH TABLES
    with conn.cursor() as cursor:
        try:
            cursor.execute("FLUSH TABLES")
            conn.commit()
        except:
            pass
    time.sleep(0.5)

    # 检查 FLUSH 后
    stats_after = {}
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_data'")
    stats_after['pages_data'] = int(rows[0]['Value'])
    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_free'")
    stats_after['pages_free'] = int(rows[0]['Value'])

    print(f"\n  FLUSH TABLES 后:")
    print(f"    数据页: {stats_after['pages_data']:,} (变化: {stats_after['pages_data'] - pages_data_loaded})")
    print(f"    空闲页: {stats_after['pages_free']:,}")

    if stats_after['pages_data'] >= pages_data_loaded:
        print(f"\n  ⚠️ 结论: FLUSH TABLES ***不会*** 清除 InnoDB Buffer Pool 中的数据页！")
        print(f"  ⚠️ 之前的实验实际上都是在热缓存上运行的！")
    else:
        print(f"\n  ✅ FLUSH TABLES 清除了部分 Buffer Pool 页")


# ============================================================
# 五、测试真正的冷查询 vs 热查询
# ============================================================
def diagnose_cold_vs_hot(conn):
    section("五、真正的冷查询 vs 热查询测试")

    # 用大表扫描驱逐缓冲池
    print("  策略: 用大表全表扫描来驱逐 Buffer Pool 中的 gpu6 数据页")

    # 先用正常查询加载 gpu6 数据
    print("\n  [步骤1] 扫描 gpu6 数据加载到缓冲池...")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*), SUM(gpu_usage) FROM t_node_gpu_history_info WHERE node = %s", (NODE,))
    cursor.fetchall()
    cursor.close()
    time.sleep(0.5)

    rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_data'")
    bp_pages_before = int(rows[0]['Value'])

    # 执行热查询
    print("  [步骤2] 执行一次查询作为基准...")
    start = time.perf_counter()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM t_node_gpu_history_info WHERE node = %s", (NODE,))
    cursor.fetchall()
    cursor.close()
    hot_time = (time.perf_counter() - start) * 1000
    print(f"    热查询耗时: {hot_time:.2f}ms")

    # 统计有哪些大表
    print("\n  [步骤3] 查找大表用于驱逐缓存...")
    large_tables = query(conn, """
        SELECT table_name, ROUND(data_length/1024/1024,0) AS mb
        FROM information_schema.tables
        WHERE table_schema = 'hcp' AND data_length > 50 * 1024 * 1024
        ORDER BY data_length DESC LIMIT 10
    """)

    if not large_tables:
        # 尝试当前库
        large_tables = query(conn, """
            SELECT table_name, ROUND(data_length/1024/1024,0) AS mb, table_rows
            FROM information_schema.tables
            WHERE table_schema = 'hpc'
            ORDER BY (data_length + index_length) DESC LIMIT 10
        """)

    print("  可用的大表:")
    for t in large_tables:
        print(f"    {t['table_name']}: {t['mb']} MB ({t.get('table_rows','?')} 行)")

    # 用大表驱逐缓冲池
    if large_tables:
        big_table = large_tables[0]['table_name']
        print(f"\n  [步骤4] 扫描 {big_table} 驱逐 Buffer Pool (需要扫描 >128MB 数据)...")

        # 先查一下这个大表有没有大字段
        cols = query(conn, f"""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM information_schema.COLUMNS
            WHERE table_schema = 'hpc' AND table_name = '{big_table}'
            ORDER BY ORDINAL_POSITION
        """)

        # 构造全表扫描
        count_col = cols[0]['COLUMN_NAME'] if cols else '*'
        try:
            cursor = conn.cursor()
            start_evict = time.perf_counter()
            cursor.execute(f"SELECT COUNT(*) FROM {big_table}")
            cursor.fetchall()
            cursor.close()
            evict_time = (time.perf_counter() - start_evict) * 1000
            print(f"    全表扫描耗时: {evict_time:.2f}ms")
        except Exception as e:
            print(f"    扫描失败: {e}")
            # 尝试另一种方法
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT 1 FROM {big_table} LIMIT 1000000")
                while cursor.fetchmany(10000):
                    pass
                cursor.close()
            except:
                pass

        time.sleep(0.5)

        rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_data'")
        bp_pages_after = int(rows[0]['Value'])
        rows = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_pages_free'")
        bp_free_after = int(rows[0]['Value'])
        print(f"    Buffer Pool 数据页: {bp_pages_before:,} → {bp_pages_after:,}")
        print(f"    Buffer Pool 空闲页: → {bp_free_after:,}")

    # 测试冷查询
    print(f"\n  [步骤5] 冷查询测试 (缓存已被驱逐)...")
    rows_before = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_reads'")
    phys_reads_before = int(rows_before[0]['Value'])

    start = time.perf_counter()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM t_node_gpu_history_info WHERE node = %s", (NODE,))
    cursor.fetchall()
    cursor.close()
    cold_time = (time.perf_counter() - start) * 1000

    rows_after = query(conn, "SHOW STATUS LIKE 'Innodb_buffer_pool_reads'")
    phys_reads_after = int(rows_after[0]['Value'])
    phys_reads_delta = phys_reads_after - phys_reads_before

    print(f"    冷查询耗时: {cold_time:.2f}ms")
    print(f"    物理读页数: {phys_reads_delta} 页 ({phys_reads_delta * 16} KB)")

    print(f"\n  {'='*50}")
    print(f"  热查询: {hot_time:.2f}ms")
    print(f"  冷查询: {cold_time:.2f}ms")
    if cold_time > hot_time:
        speedup = cold_time / hot_time
        print(f"  缓存加速: {speedup:.1f}x ({cold_time - hot_time:.2f}ms 差距)")
    else:
        print(f"  冷查询反而更快! (差异: {hot_time - cold_time:.2f}ms)")
    print(f"  {'='*50}")


# ============================================================
# 六、OS 文件系统缓存诊断
# ============================================================
def diagnose_os_cache(conn):
    section("六、操作系统文件缓存分析")

    print("  InnoDB 读取方式诊断:")
    rows = query(conn, "SHOW VARIABLES LIKE 'innodb_flush_method'")
    flush_method = rows[0]['Value'] if rows else 'unknown'
    print(f"  innodb_flush_method = {flush_method}")

    if flush_method in ('O_DIRECT', 'O_DIRECT_NO_FSYNC'):
        print("  ⚠️ 使用 O_DIRECT，绕过 OS 文件缓存，数据只在 InnoDB Buffer Pool 中")
        print("  ⚠️ 这意味着 FLUSH TABLES 无效后，数据一直在内存中!")
    else:
        print("  使用 fsync/O_DSYNC，数据可能同时在 InnoDB Buffer Pool 和 OS 文件缓存中")

    # 检查是否是 SSD
    rows = query(conn, "SHOW VARIABLES LIKE 'innodb_io_capacity'")
    io_cap = rows[0]['Value'] if rows else 'unknown'
    print(f"  innodb_io_capacity = {io_cap} (SSD 通常设为 2000+, HDD 通常 200)")

    # 检查数据目录磁盘类型（通过 MySQL 无法直接获取）
    rows = query(conn, "SHOW VARIABLES LIKE 'datadir'")
    datadir = rows[0]['Value'] if rows else 'unknown'
    print(f"  datadir = {datadir}")

    # 估算索引扫描需要的 IO
    print(f"\n  InnoDB 页面大小: 16KB (默认)")
    print(f"  Buffer Pool 总大小: 128MB = 8192 页")
    print(f"  如果 gpu6 的 7 天数据 < 128MB，则可能全部常驻内存")


def main():
    conn = get_connection()
    try:
        print("="*70)
        print("  MySQL 缓存机制深度诊断")
        print("="*70)

        diagnose_config(conn)
        diagnose_buffer_pool(conn)
        diagnose_data_size(conn)
        diagnose_flush_effect(conn)
        diagnose_os_cache(conn)
        diagnose_cold_vs_hot(conn)

        print(f"\n{'='*70}")
        print("  诊断总结")
        print(f"{'='*70}")
        print("""
  关键发现待分析:
  1. FLUSH TABLES 不会清除 InnoDB Buffer Pool → 之前实验的"冷查询"其实是热查询!
  2. 需要检查 innodb_flush_method 是否用了 O_DIRECT
  3. 如果使用了 O_DIRECT，唯一清空缓存的方法是重启 MySQL
  4. 如果 Buffer Pool 128MB 足够容纳 gpu6 的 7 天数据，那缓存策略差异确实体现不出来
        """)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
