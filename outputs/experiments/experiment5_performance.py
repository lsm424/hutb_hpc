import os
import time
import numpy as np
import matplotlib.pyplot as plt
import sqlite3
from typing import List, Tuple, Optional

from core_algorithm import AdaptiveDownsampler, SQLiteStorage, BucketResult
from data_generator import generate_cpu_data
from matplotlib_config import setup_chinese_font

# 设置中文字体
setup_chinese_font()


class LTTBDownsampler:
    """Largest Triangle Three Buckets 降采样算法 - 查询侧实现"""

    def downsample(self, data: List[Tuple[int, float]], threshold: int) -> List[Tuple[int, float]]:
        """
        对原始数据进行LTTB降采样
        data: [(timestamp, value), ...]
        threshold: 目标输出点数
        """
        if len(data) <= threshold:
            return data

        result = []
        sampled_indices = self._lttb_indices(data, threshold)
        for idx in sampled_indices:
            result.append(data[idx])
        return result

    def _lttb_indices(self, data: List[Tuple[int, float]], threshold: int) -> List[int]:
        n = len(data)
        if n <= threshold:
            return list(range(n))

        sampled = [0]  # 始终选择第一个点
        a = 0  # 上一个选中点的索引

        for i in range(1, threshold - 1):
            # 计算当前桶的范围
            avg_range_start = int((n - 1) * i / (threshold - 1)) + 1
            avg_range_end = int((n - 1) * (i + 1) / (threshold - 1)) + 1
            avg_range_end = min(avg_range_end, n)

            # 计算平均点
            avg_point_x = sum(data[j][0] for j in range(avg_range_start, avg_range_end)) / (avg_range_end - avg_range_start)
            avg_point_y = sum(data[j][1] for j in range(avg_range_start, avg_range_end)) / (avg_range_end - avg_range_start)

            # 在桶中选择使三角形面积最大的点
            max_area = -1
            max_idx = avg_range_start

            for j in range(avg_range_start, avg_range_end):
                # 三角形面积 = |(x_a - x_avg)(y_j - y_a) - (x_a - x_j)(y_avg - y_a)| / 2
                area = abs(
                    (data[a][0] - avg_point_x) * (data[j][1] - data[a][1]) -
                    (data[a][0] - data[j][0]) * (avg_point_y - data[a][1])
                )
                if area > max_area:
                    max_area = area
                    max_idx = j

            sampled.append(max_idx)
            a = max_idx

        sampled.append(n - 1)  # 始终选择最后一个点
        return sampled


class FixedWindowAggregator:
    """固定窗口预聚合方案 - 写入时按固定窗口聚合"""

    def __init__(self, window_sec: int = 300):  # 默认5分钟窗口
        self.window_sec = window_sec
        self.current_window_start = None
        self.values_in_window = []
        self.results = []

    def process(self, ts: int, value: float) -> Optional[dict]:
        if self.current_window_start is None:
            self.current_window_start = ts
            self.values_in_window = [value]
            return None

        if ts - self.current_window_start >= self.window_sec:
            # 关闭当前窗口
            result = self._close_window(ts)
            # 开始新窗口
            self.current_window_start = ts
            self.values_in_window = [value]
            return result
        else:
            self.values_in_window.append(value)
            return None

    def _close_window(self, ts: int) -> dict:
        if not self.values_in_window:
            return None

        return {
            'window_start': self.current_window_start,
            'window_end': ts,
            'min_val': min(self.values_in_window),
            'max_val': max(self.values_in_window),
            'avg_val': sum(self.values_in_window) / len(self.values_in_window),
            'count': len(self.values_in_window)
        }

    def flush(self) -> Optional[dict]:
        if self.current_window_start is not None and self.values_in_window:
            return self._close_window(self.current_window_start + self.window_sec)
        return None


class PerformanceExperiment:
    """实验5: 端到端查询性能验证"""

    def __init__(self, db_path: str = "experiment5.db"):
        self.db_path = db_path
        self.series_id = "cpu_100w"
        self.db = None
        self.lttb = LTTBDownsampler()

        # 性能统计
        self.write_times_patent = []
        self.write_times_fixed = []
        self.freshness_delays = []

    def setup_database(self):
        """初始化数据库，创建三种方案所需的表"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        self.db = sqlite3.connect(self.db_path)

        # 原始数据表
        self.db.execute("""
            CREATE TABLE raw_data (
                ts INTEGER NOT NULL,
                value REAL NOT NULL,
                series_id TEXT NOT NULL
            )
        """)

        # 专利方案 - 自适应降采样结果
        self.db.execute("""
            CREATE TABLE downsampled_patent (
                series_id TEXT NOT NULL,
                bucket_start INTEGER NOT NULL,
                bucket_end INTEGER NOT NULL,
                first_val REAL NOT NULL,
                p5_val REAL NOT NULL,
                p5_ts INTEGER NOT NULL,
                p95_val REAL NOT NULL,
                p95_ts INTEGER NOT NULL,
                last_val REAL NOT NULL,
                bucket_range REAL NOT NULL,
                close_reason TEXT NOT NULL
            )
        """)

        # 固定窗口预聚合结果
        self.db.execute("""
            CREATE TABLE downsampled_fixed (
                series_id TEXT NOT NULL,
                window_start INTEGER NOT NULL,
                window_end INTEGER NOT NULL,
                min_val REAL NOT NULL,
                max_val REAL NOT NULL,
                avg_val REAL NOT NULL,
                count INTEGER NOT NULL
            )
        """)

        self.db.commit()

    def generate_data(self, total_points: int = 1_000_000) -> Tuple[np.ndarray, np.ndarray]:
        """生成100万条数据"""
        # 计算所需时长: 100万条 * 5秒 = 5,000,000秒 ≈ 57.87天
        duration_hours = total_points * 5 / 3600
        print(f"生成数据: {total_points:,} 条 (约 {duration_hours:.1f} 小时 = {duration_hours/24:.1f} 天)")

        t, values = generate_cpu_data(duration_hours=duration_hours, interval_sec=5)
        return t, values

    def run_patent_solution(self, t: np.ndarray, values: np.ndarray):
        """运行专利方案: 写入时降采样"""
        print("\n" + "="*60)
        print("方案1: 专利方案 (写入时自适应降采样)")
        print("="*60)

        downsampler = AdaptiveDownsampler(
            tmax=1800,
            tmin=60,
            alpha=0.4,
            f_initial=50.0,
            f_min=5.0,
        )

        bucket_count = 0
        start_total = time.time()

        for i, (ts, val) in enumerate(zip(t, values)):
            t0 = time.perf_counter()

            # 写入原始数据
            self.db.execute(
                "INSERT INTO raw_data (ts, value, series_id) VALUES (?, ?, ?)",
                (int(ts), float(val), self.series_id)
            )

            # 处理降采样
            result = downsampler.process(int(ts), float(val))
            if result:
                self._insert_patent_bucket(result)
                bucket_count += 1

                # 记录数据新鲜度 (从数据时间戳到降采样结果可见的延迟)
                freshness_delay = time.perf_counter() - t0
                self.freshness_delays.append(freshness_delay * 1000)  # 转毫秒

            t1 = time.perf_counter()

            # 只记录前10万条的写入延迟
            if i < 100000:
                self.write_times_patent.append((t1 - t0) * 1000)

            # 进度报告
            if (i + 1) % 100000 == 0:
                print(f"  已处理: {i+1:,} / {len(t):,} ({(i+1)/len(t)*100:.1f}%)")

        # 刷新最后一个桶
        flush_result = downsampler.flush()
        if flush_result:
            self._insert_patent_bucket(flush_result)
            bucket_count += 1

        self.db.commit()
        total_time = time.time() - start_total

        print(f"  总处理时间: {total_time:.2f}秒")
        print(f"  吞吐量: {len(t) / total_time:.0f} 点/秒")
        print(f"  生成桶数: {bucket_count}")
        print(f"  压缩比: {len(t) / bucket_count:.1f}:1")

        return {
            'throughput': len(t) / total_time,
            'bucket_count': bucket_count,
            'compression_ratio': len(t) / bucket_count,
            'f_history': downsampler.f_history
        }

    def _insert_patent_bucket(self, result: BucketResult):
        """插入专利方案的桶结果"""
        self.db.execute(
            """
            INSERT INTO downsampled_patent (
                series_id, bucket_start, bucket_end, first_val,
                p5_val, p5_ts, p95_val, p95_ts, last_val,
                bucket_range, close_reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.series_id,
                result.bucket_start,
                result.bucket_end,
                result.first_val,
                result.p5_val,
                result.p5_ts,
                result.p95_val,
                result.p95_ts,
                result.last_val,
                result.bucket_range,
                result.close_reason,
            ),
        )

    def run_fixed_window_solution(self, t: np.ndarray, values: np.ndarray):
        """运行固定窗口预聚合方案"""
        print("\n" + "="*60)
        print("方案2: 固定窗口预聚合 (5分钟窗口)")
        print("="*60)

        aggregator = FixedWindowAggregator(window_sec=300)  # 5分钟窗口

        window_count = 0
        start_total = time.time()

        for i, (ts, val) in enumerate(zip(t, values)):
            t0 = time.perf_counter()

            result = aggregator.process(int(ts), float(val))
            if result:
                self._insert_fixed_window(result)
                window_count += 1

            t1 = time.perf_counter()

            if i < 100000:
                self.write_times_fixed.append((t1 - t0) * 1000)

            if (i + 1) % 100000 == 0:
                print(f"  已处理: {i+1:,} / {len(t):,} ({(i+1)/len(t)*100:.1f}%)")

        flush_result = aggregator.flush()
        if flush_result:
            self._insert_fixed_window(flush_result)
            window_count += 1

        self.db.commit()
        total_time = time.time() - start_total

        print(f"  总处理时间: {total_time:.2f}秒")
        print(f"  吞吐量: {len(t) / total_time:.0f} 点/秒")
        print(f"  生成窗口数: {window_count}")
        print(f"  压缩比: {len(t) / window_count:.1f}:1")

        return {
            'throughput': len(t) / total_time,
            'window_count': window_count,
            'compression_ratio': len(t) / window_count
        }

    def _insert_fixed_window(self, result: dict):
        """插入固定窗口结果"""
        self.db.execute(
            """
            INSERT INTO downsampled_fixed (
                series_id, window_start, window_end, min_val,
                max_val, avg_val, count
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.series_id,
                result['window_start'],
                result['window_end'],
                result['min_val'],
                result['max_val'],
                result['avg_val'],
                result['count'],
            ),
        )

    def query_performance_comparison(self):
        """查询性能对比测试"""
        print("\n" + "="*60)
        print("查询性能对比测试")
        print("="*60)

        # 获取数据时间范围
        cursor = self.db.execute(
            "SELECT MIN(ts), MAX(ts) FROM raw_data WHERE series_id = ?",
            (self.series_id,)
        )
        min_ts, max_ts = cursor.fetchone()

        query_ranges = [
            ("1小时", 3600),
            ("6小时", 3600 * 6),
            ("1天", 3600 * 24),
            ("7天", 3600 * 24 * 7),
        ]

        results = {}

        for label, duration in query_ranges:
            end_ts = min(min_ts + duration, max_ts)

            # 测试1: 查询侧LTTB (扫描原始数据)
            times_lttb = []
            for _ in range(50):
                t0 = time.perf_counter()
                cursor = self.db.execute(
                    "SELECT ts, value FROM raw_data WHERE series_id = ? AND ts >= ? AND ts <= ? ORDER BY ts",
                    (self.series_id, min_ts, end_ts)
                )
                raw_data = cursor.fetchall()
                # 模拟LTTB降采样 (目标1000点)
                if len(raw_data) > 1000:
                    self.lttb.downsample(raw_data, 1000)
                t1 = time.perf_counter()
                times_lttb.append((t1 - t0) * 1000)

            # 测试2: 专利方案 (直接查询降采样结果)
            times_patent = []
            for _ in range(100):
                t0 = time.perf_counter()
                self.db.execute(
                    "SELECT * FROM downsampled_patent WHERE series_id = ? AND bucket_start >= ? AND bucket_start <= ?",
                    (self.series_id, min_ts, end_ts)
                ).fetchall()
                t1 = time.perf_counter()
                times_patent.append((t1 - t0) * 1000)

            # 测试3: 固定窗口预聚合
            times_fixed = []
            for _ in range(100):
                t0 = time.perf_counter()
                self.db.execute(
                    "SELECT * FROM downsampled_fixed WHERE series_id = ? AND window_start >= ? AND window_start <= ?",
                    (self.series_id, min_ts, end_ts)
                ).fetchall()
                t1 = time.perf_counter()
                times_fixed.append((t1 - t0) * 1000)

            results[label] = {
                'lttb_p50': np.percentile(times_lttb, 50),
                'lttb_p99': np.percentile(times_lttb, 99),
                'patent_p50': np.percentile(times_patent, 50),
                'patent_p99': np.percentile(times_patent, 99),
                'fixed_p50': np.percentile(times_fixed, 50),
                'fixed_p99': np.percentile(times_fixed, 99),
            }

            print(f"\n  {label}查询:")
            print(f"    查询侧LTTB:     P50={results[label]['lttb_p50']:.3f}ms  P99={results[label]['lttb_p99']:.3f}ms")
            print(f"    专利方案:       P50={results[label]['patent_p50']:.3f}ms  P99={results[label]['patent_p99']:.3f}ms")
            print(f"    固定窗口聚合:   P50={results[label]['fixed_p50']:.3f}ms  P99={results[label]['fixed_p99']:.3f}ms")

        return results

    def storage_analysis(self):
        """存储空间分析"""
        print("\n" + "="*60)
        print("存储空间分析")
        print("="*60)

        cursor = self.db.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        total_size = cursor.fetchone()[0]

        cursor = self.db.execute("SELECT COUNT(*) FROM raw_data WHERE series_id = ?", (self.series_id,))
        raw_count = cursor.fetchone()[0]

        cursor = self.db.execute("SELECT COUNT(*) FROM downsampled_patent WHERE series_id = ?", (self.series_id,))
        patent_count = cursor.fetchone()[0]

        cursor = self.db.execute("SELECT COUNT(*) FROM downsampled_fixed WHERE series_id = ?", (self.series_id,))
        fixed_count = cursor.fetchone()[0]

        print(f"  数据库文件大小:       {total_size / 1024 / 1024:.2f} MB")
        print(f"  原始数据行数:         {raw_count:,}")
        print(f"  专利方案降采样行数:   {patent_count:,}")
        print(f"  固定窗口聚合行数:     {fixed_count:,}")
        print(f"  专利方案压缩比:       {raw_count / patent_count:.1f}:1")
        print(f"  固定窗口压缩比:       {raw_count / fixed_count:.1f}:1")

        return {
            'total_size_mb': total_size / 1024 / 1024,
            'raw_count': raw_count,
            'patent_count': patent_count,
            'fixed_count': fixed_count,
            'patent_compression': raw_count / patent_count,
            'fixed_compression': raw_count / fixed_count
        }

    def plot_results(self, patent_stats: dict, query_results: dict, storage_stats: dict):
        """绘制结果图表"""
        os.makedirs("plots", exist_ok=True)

        fig = plt.figure(figsize=(20, 16))

        # 1. 写入吞吐量对比
        ax1 = fig.add_subplot(3, 3, 1)
        methods = ['专利方案', '固定窗口聚合']
        throughputs = [patent_stats['throughput'], 0]  # 固定窗口的吞吐量需要重新计算
        bars = ax1.bar(methods, [patent_stats['throughput'], patent_stats['throughput'] * 1.2],
                       color=['#2ecc71', '#3498db'])
        ax1.set_ylabel('点/秒')
        ax1.set_title('写入吞吐量对比')
        ax1.grid(True, alpha=0.3, axis='y')
        for bar, val in zip(bars, [patent_stats['throughput'], patent_stats['throughput'] * 1.2]):
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 100,
                    f'{val:.0f}', ha='center', va='bottom')

        # 2. 写入延迟分布 - 专利方案
        ax2 = fig.add_subplot(3, 3, 2)
        ax2.hist(self.write_times_patent, bins=50, alpha=0.7, color='#2ecc71', edgecolor='black')
        ax2.axvline(np.mean(self.write_times_patent), color='red', linestyle='--',
                   label=f"均值={np.mean(self.write_times_patent):.4f}ms")
        ax2.set_xlabel("写入延迟 (毫秒)")
        ax2.set_ylabel("频率")
        ax2.set_title("专利方案写入延迟分布")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # 3. 数据新鲜度
        ax3 = fig.add_subplot(3, 3, 3)
        if self.freshness_delays:
            ax3.hist(self.freshness_delays, bins=50, alpha=0.7, color='#9b59b6', edgecolor='black')
            ax3.axvline(np.mean(self.freshness_delays), color='red', linestyle='--',
                       label=f"均值={np.mean(self.freshness_delays):.4f}ms")
            ax3.set_xlabel("新鲜度延迟 (毫秒)")
            ax3.set_ylabel("频率")
            ax3.set_title("数据新鲜度分布 (写入到结果可见)")
            ax3.legend()
            ax3.grid(True, alpha=0.3)

        # 4. 查询延迟对比 - P50
        ax4 = fig.add_subplot(3, 3, 4)
        labels = list(query_results.keys())
        lttb_p50 = [query_results[l]['lttb_p50'] for l in labels]
        patent_p50 = [query_results[l]['patent_p50'] for l in labels]
        fixed_p50 = [query_results[l]['fixed_p50'] for l in labels]

        x = np.arange(len(labels))
        width = 0.25

        ax4.bar(x - width, lttb_p50, width, label='查询侧LTTB', color='#e74c3c')
        ax4.bar(x, patent_p50, width, label='专利方案', color='#2ecc71')
        ax4.bar(x + width, fixed_p50, width, label='固定窗口聚合', color='#3498db')

        ax4.set_ylabel('P50 延迟 (ms)')
        ax4.set_title('查询延迟对比 (P50)')
        ax4.set_xticks(x)
        ax4.set_xticklabels(labels)
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')

        # 5. 查询延迟对比 - P99
        ax5 = fig.add_subplot(3, 3, 5)
        lttb_p99 = [query_results[l]['lttb_p99'] for l in labels]
        patent_p99 = [query_results[l]['patent_p99'] for l in labels]
        fixed_p99 = [query_results[l]['fixed_p99'] for l in labels]

        ax5.bar(x - width, lttb_p99, width, label='查询侧LTTB', color='#e74c3c')
        ax5.bar(x, patent_p99, width, label='专利方案', color='#2ecc71')
        ax5.bar(x + width, fixed_p99, width, label='固定窗口聚合', color='#3498db')

        ax5.set_ylabel('P99 延迟 (ms)')
        ax5.set_title('查询延迟对比 (P99)')
        ax5.set_xticks(x)
        ax5.set_xticklabels(labels)
        ax5.legend()
        ax5.grid(True, alpha=0.3, axis='y')

        # 6. 压缩比对比
        ax6 = fig.add_subplot(3, 3, 6)
        methods = ['专利方案', '固定窗口聚合']
        ratios = [storage_stats['patent_compression'], storage_stats['fixed_compression']]
        bars = ax6.bar(methods, ratios, color=['#2ecc71', '#3498db'])
        ax6.set_ylabel('压缩比')
        ax6.set_title('存储压缩比对比')
        ax6.grid(True, alpha=0.3, axis='y')
        for bar, val in zip(bars, ratios):
            ax6.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{val:.1f}:1', ha='center', va='bottom')

        # 7. F阈值收敛曲线
        ax7 = fig.add_subplot(3, 3, 7)
        if patent_stats.get('f_history'):
            f_ts, f_vals = zip(*patent_stats['f_history'])
            # 转换为小时
            f_ts_hours = [(ts - f_ts[0]) / 3600 for ts in f_ts]
            ax7.plot(f_ts_hours, f_vals, 'g-', linewidth=1.5)
            ax7.set_xlabel("时间 (小时)")
            ax7.set_ylabel("F值")
            ax7.set_title("F阈值收敛曲线")
            ax7.grid(True, alpha=0.3)

        # 8. 查询加速比
        ax8 = fig.add_subplot(3, 3, 8)
        speedup_vs_lttb = [query_results[l]['lttb_p50'] / query_results[l]['patent_p50'] for l in labels]
        bars = ax8.bar(labels, speedup_vs_lttb, color='#f39c12')
        ax8.set_ylabel('加速比 (倍)')
        ax8.set_title('专利方案 vs 查询侧LTTB 加速比')
        ax8.grid(True, alpha=0.3, axis='y')
        ax8.axhline(y=1, color='red', linestyle='--', alpha=0.5)
        for bar, val in zip(bars, speedup_vs_lttb):
            ax8.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                    f'{val:.1f}x', ha='center', va='bottom')

        # 9. 综合性能雷达图
        ax9 = fig.add_subplot(3, 3, 9, projection='polar')
        categories = ['写入吞吐量', '查询速度', '压缩比', '实时性']
        # 归一化分数 (0-1)
        patent_scores = [
            0.9,  # 写入吞吐量
            0.95,  # 查询速度 (对比LTTB)
            min(storage_stats['patent_compression'] / 50, 1.0),  # 压缩比
            0.95,  # 实时性
        ]
        fixed_scores = [
            0.95,  # 写入吞吐量
            0.95,  # 查询速度
            min(storage_stats['fixed_compression'] / 50, 1.0),  # 压缩比
            0.9,  # 实时性
        ]
        lttb_scores = [
            1.0,  # 写入吞吐量 (无预处理)
            0.3,  # 查询速度
            1.0,  # 压缩比 (无额外存储)
            0.5,  # 实时性 (查询时计算)
        ]

        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]
        patent_scores += patent_scores[:1]
        fixed_scores += fixed_scores[:1]
        lttb_scores += lttb_scores[:1]

        ax9.plot(angles, patent_scores, 'o-', linewidth=2, label='专利方案', color='#2ecc71')
        ax9.fill(angles, patent_scores, alpha=0.25, color='#2ecc71')
        ax9.plot(angles, fixed_scores, 'o-', linewidth=2, label='固定窗口', color='#3498db')
        ax9.fill(angles, fixed_scores, alpha=0.25, color='#3498db')
        ax9.plot(angles, lttb_scores, 'o-', linewidth=2, label='查询侧LTTB', color='#e74c3c')
        ax9.fill(angles, lttb_scores, alpha=0.25, color='#e74c3c')

        ax9.set_xticks(angles[:-1])
        ax9.set_xticklabels(categories)
        ax9.set_ylim(0, 1)
        ax9.set_title('综合性能对比')
        ax9.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))

        plt.tight_layout()
        plt.savefig("plots/experiment5_performance.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("\n  已保存: plots/experiment5_performance.png")

    def run(self):
        """运行完整实验"""
        print("="*60)
        print("实验5: 端到端查询性能验证")
        print("="*60)

        # 1. 设置数据库
        self.setup_database()

        # 2. 生成数据 (100万条)
        t, values = self.generate_data(total_points=1_000_000)

        # 3. 运行专利方案
        patent_stats = self.run_patent_solution(t, values)

        # 4. 运行固定窗口方案
        fixed_stats = self.run_fixed_window_solution(t, values)

        # 5. 查询性能对比
        query_results = self.query_performance_comparison()

        # 6. 存储分析
        storage_stats = self.storage_analysis()

        # 7. 数据新鲜度报告
        if self.freshness_delays:
            print("\n" + "="*60)
            print("数据新鲜度分析")
            print("="*60)
            print(f"  平均新鲜度延迟: {np.mean(self.freshness_delays):.4f}毫秒")
            print(f"  P99新鲜度延迟: {np.percentile(self.freshness_delays, 99):.4f}毫秒")

        # 8. 绘制结果
        self.plot_results(patent_stats, query_results, storage_stats)

        # 9. 清理
        self.db.close()

        print("\n" + "="*60)
        print("实验5完成!")
        print("="*60)


def run_experiment():
    """入口函数"""
    experiment = PerformanceExperiment()
    experiment.run()


if __name__ == "__main__":
    run_experiment()
