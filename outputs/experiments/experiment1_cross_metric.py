"""
实验1：跨指标综合验证
在统一参数下同时验证跨纲量适配、趋势保真、工程性能和外部对比。
外部对比分为：公平预算（1天查询）与固定参数跨查询范围（7天全程查询）。
"""

import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np

from core_algorithm import AdaptiveDownsampler, BucketResult, SQLiteStorage
from data_generator import generate_cpu_data, generate_memory_data
from matplotlib_config import setup_chinese_font

setup_chinese_font()
os.chdir(os.path.dirname(os.path.abspath(__file__)))


# =============================================================================
# 数据类定义
# =============================================================================


@dataclass
class MetricConfig:
    """指标配置"""

    name: str
    generator: Callable
    duration_hours: float = 7*24


@dataclass
class ComparisonResult:
    """对比/消融结果"""

    name: str
    category: str
    output_points: int
    total_buckets: int
    compression_ratio: float
    correlation: float
    nrmse: float
    write_time_ms: float
    query_time_ms: float
    tuning_cost: str
    note: str = ""
    sampled_ts: Optional[np.ndarray] = None
    sampled_vals: Optional[np.ndarray] = None


@dataclass
class EvaluationResult:
    """综合评估结果"""

    # 基础统计
    total_points: int
    total_buckets: int
    compression_ratio: float
    visual_compression_ratio: float
    f_final: float
    f_history: List[Tuple[int, float]]
    close_reasons: List[str]

    # 趋势保真
    correlation: float
    nrmse: float

    # 自适应适配
    convergence_buckets: int
    is_stable: bool
    f_stable_cv: float
    avg_bucket_width: float
    median_bucket_width: float
    fluctuation_ratio: float
    tmax_ratio: float

    # 性能
    process_time_ms: float
    query_speed_ms: float
    write_latency: Optional[Dict] = None

    # 鲁棒性
    spike_filter_rate: float = 0.0
    noise_robustness: Optional[Dict[str, float]] = None

    # 对比结果
    fair_budget_comparisons: Optional[Dict[str, ComparisonResult]] = None
    cross_range_fixed_param_comparisons: Optional[Dict[str, ComparisonResult]] = None


# =============================================================================
# 算法变体
# =============================================================================


class FixedThresholdDownsampler(AdaptiveDownsampler):
    """消融1：关闭EWMA，仅使用固定阈值"""

    def __init__(self, fixed_f: float, **kwargs):
        super().__init__(f_initial=fixed_f, **kwargs)
        self.fixed_f = fixed_f
        self.f = fixed_f

    def _close_bucket(
        self,
        ts: int,
        last_val: float,
        p5: float,
        p5_ts: int,
        p95: float,
        p95_ts: int,
        bucket_range: float,
        reason: str,
    ) -> BucketResult:
        current_f = self.fixed_f
        result = BucketResult(
            bucket_start=self.t0,
            bucket_end=ts,
            first_val=self.first_val,
            p5_val=p5,
            p5_ts=p5_ts,
            p95_val=p95,
            p95_ts=p95_ts,
            last_val=last_val,
            bucket_range=bucket_range,
            close_reason=reason,
            f_value=current_f,
        )
        self.results.append(result)
        self.bucket_ranges.append((ts, bucket_range))
        self.f = self.fixed_f
        self.f_history.append((ts, self.fixed_f))
        self.has_open_bucket = False
        return result


class RawExtremaDownsampler(AdaptiveDownsampler):
    """消融2：用raw min/max代替P5/P95"""

    def _compute_percentile(self, p: float) -> Tuple[float, int]:
        if not self.values_buffer:
            return 0.0, self.t0

        values = np.asarray(self.values_buffer)
        timestamps = np.asarray(self.timestamps_buffer)
        idx = int(np.argmin(values)) if p <= 0.05 else int(np.argmax(values))
        return float(values[idx]), int(timestamps[idx])


class RawExtremaFixedThresholdDownsampler(RawExtremaDownsampler):
    """组合消融：raw min/max + 固定阈值"""

    def __init__(self, fixed_f: float, **kwargs):
        super().__init__(f_initial=fixed_f, **kwargs)
        self.fixed_f = fixed_f
        self.f = fixed_f

    def _close_bucket(
        self,
        ts: int,
        last_val: float,
        p5: float,
        p5_ts: int,
        p95: float,
        p95_ts: int,
        bucket_range: float,
        reason: str,
    ) -> BucketResult:
        current_f = self.fixed_f
        result = BucketResult(
            bucket_start=self.t0,
            bucket_end=ts,
            first_val=self.first_val,
            p5_val=p5,
            p5_ts=p5_ts,
            p95_val=p95,
            p95_ts=p95_ts,
            last_val=last_val,
            bucket_range=bucket_range,
            close_reason=reason,
            f_value=current_f,
        )
        self.results.append(result)
        self.bucket_ranges.append((ts, bucket_range))
        self.f = self.fixed_f
        self.f_history.append((ts, self.fixed_f))
        self.has_open_bucket = False
        return result


# =============================================================================
# 对比基线
# =============================================================================


def lttb_downsample(data: np.ndarray, threshold: int) -> np.ndarray:
    """Largest Triangle Three Buckets (LTTB)"""

    n = len(data)
    threshold = max(3, min(threshold, n))
    if threshold >= n:
        return data

    sampled = np.zeros((threshold, 2))
    sampled[0] = data[0]
    sampled[-1] = data[-1]

    a = 0
    for i in range(1, threshold - 1):
        avg_range_start = int((n - 1) * i / (threshold - 1)) + 1
        avg_range_end = int((n - 1) * (i + 1) / (threshold - 1)) + 1
        avg_range_end = min(avg_range_end, n)
        avg_range = data[avg_range_start:avg_range_end]
        if len(avg_range) == 0:
            avg_point = data[min(avg_range_start, n - 1)]
        else:
            avg_point = np.array([np.mean(avg_range[:, 0]), np.mean(avg_range[:, 1])])

        range_offs = avg_range_start
        range_to = avg_range_end

        point_a_x = data[a][0]
        point_a_y = data[a][1]
        max_area = -1.0
        max_idx = range_offs

        for j in range(range_offs, range_to):
            point_j_x = data[j][0]
            point_j_y = data[j][1]
            area = abs(
                (point_a_x - avg_point[0]) * (point_j_y - point_a_y)
                - (point_a_x - point_j_x) * (avg_point[1] - point_a_y)
            )
            if area > max_area:
                max_area = area
                max_idx = j

        sampled[i] = data[max_idx]
        a = max_idx

    return sampled


def fixed_window_aggregate_by_count(
    timestamps: np.ndarray, values: np.ndarray, target_bucket_count: int
) -> Tuple[np.ndarray, np.ndarray]:
    """固定窗口聚合，窗口数量与本专利方法输出桶数对齐"""

    if len(timestamps) == 0 or target_bucket_count <= 0:
        return np.array([]), np.array([])

    bucket_ts = []
    bucket_vals = []
    edges = np.linspace(timestamps[0], timestamps[-1], target_bucket_count + 1)

    for i in range(target_bucket_count):
        start_edge = edges[i]
        end_edge = edges[i + 1]
        if i == target_bucket_count - 1:
            mask = (timestamps >= start_edge) & (timestamps <= end_edge)
        else:
            mask = (timestamps >= start_edge) & (timestamps < end_edge)

        if not np.any(mask):
            continue

        segment_ts = timestamps[mask]
        segment_vals = values[mask]
        min_idx = int(np.argmin(segment_vals))
        max_idx = int(np.argmax(segment_vals))

        points = [
            (int(segment_ts[0]), float(segment_vals[0])),
            (int(segment_ts[min_idx]), float(segment_vals[min_idx])),
            (int(segment_ts[max_idx]), float(segment_vals[max_idx])),
            (int(segment_ts[-1]), float(segment_vals[-1])),
        ]
        points.sort(key=lambda item: item[0])
        bucket_ts.extend([p[0] for p in points])
        bucket_vals.extend([p[1] for p in points])

    return np.array(bucket_ts), np.array(bucket_vals)


# =============================================================================
# 指标计算器
# =============================================================================


class MetricsCalculator:
    """指标计算器"""

    @staticmethod
    def reconstruct_series(buckets: List[BucketResult]) -> Tuple[np.ndarray, np.ndarray]:
        """从桶重建时间序列"""

        ts, vals = [], []
        for bucket in buckets:
            points = [
                (bucket.bucket_start, bucket.first_val),
                (bucket.p5_ts, bucket.p5_val),
                (bucket.p95_ts, bucket.p95_val),
                (bucket.bucket_end, bucket.last_val),
            ]
            points.sort(key=lambda item: item[0])
            ts.extend([p[0] for p in points])
            vals.extend([p[1] for p in points])
        return np.array(ts), np.array(vals)

    @staticmethod
    def evaluate_sampled_series(
        original_ts: np.ndarray,
        original_vals: np.ndarray,
        sampled_ts: np.ndarray,
        sampled_vals: np.ndarray,
    ) -> Tuple[float, float]:
        """根据采样点重建并评估趋势保真"""

        if len(sampled_ts) < 2:
            return 0.0, float("inf")

        order = np.argsort(sampled_ts)
        sampled_ts = sampled_ts[order]
        sampled_vals = sampled_vals[order]
        reconstructed = np.interp(original_ts, sampled_ts, sampled_vals)
        corr = 0.0
        if np.std(reconstructed) > 0 and np.std(original_vals) > 0:
            corr = np.corrcoef(original_vals, reconstructed)[0, 1]
            if np.isnan(corr):
                corr = 0.0

        rmse = np.sqrt(np.mean((original_vals - reconstructed) ** 2))
        scale = np.mean(np.abs(original_vals))
        if scale == 0:
            nrmse = 0.0 if rmse == 0 else float("inf")
        else:
            nrmse = rmse / scale
        return corr, nrmse

    @staticmethod
    def f_convergence_speed(
        f_history: List[Tuple[int, float]], threshold: float = 0.05
    ) -> Tuple[int, bool]:
        """计算F值收敛速度"""

        if len(f_history) < 20:
            return len(f_history), False

        for i in range(10, len(f_history)):
            window_f = [f for _, f in f_history[i - 10 : i]]
            mean_f = np.mean(window_f)
            cv = np.std(window_f) / mean_f if mean_f > 0 else float("inf")
            if cv < threshold:
                return i, True
        return len(f_history), False

    @staticmethod
    def f_stability_cv(f_history: List[Tuple[int, float]], tail_size: int = 10) -> float:
        """计算后期F值稳定性CV"""

        if not f_history:
            return float("inf")
        tail = [f for _, f in f_history[-tail_size:]]
        mean_f = np.mean(tail)
        return np.std(tail) / mean_f if mean_f > 0 else float("inf")

    @staticmethod
    def bucket_width_stats(buckets: List[BucketResult]) -> Tuple[float, float]:
        """统计桶宽分布"""

        if not buckets:
            return 0.0, 0.0
        widths = [bucket.bucket_end - bucket.bucket_start for bucket in buckets]
        return float(np.mean(widths)), float(np.median(widths))

    @staticmethod
    def close_reason_ratios(buckets: List[BucketResult]) -> Tuple[float, float]:
        """统计波动触发和时间上限触发比例"""

        if not buckets:
            return 0.0, 0.0
        fluctuation_count = sum(1 for bucket in buckets if bucket.close_reason == "FLUCTUATION")
        tmax_count = sum(1 for bucket in buckets if bucket.close_reason == "TMAX")
        total = len(buckets)
        return fluctuation_count / total, tmax_count / total

    @staticmethod
    def correlation(original_ts: np.ndarray, original_vals: np.ndarray, buckets: List[BucketResult]) -> float:
        sampled_ts, sampled_vals = MetricsCalculator.reconstruct_series(buckets)
        return MetricsCalculator.evaluate_sampled_series(
            original_ts, original_vals, sampled_ts, sampled_vals
        )[0]

    @staticmethod
    def reconstruction_error(
        original_ts: np.ndarray, original_vals: np.ndarray, buckets: List[BucketResult]
    ) -> float:
        sampled_ts, sampled_vals = MetricsCalculator.reconstruct_series(buckets)
        return MetricsCalculator.evaluate_sampled_series(
            original_ts, original_vals, sampled_ts, sampled_vals
        )[1]

    @staticmethod
    def spike_filter_rate(
        original_vals: np.ndarray, buckets: List[BucketResult], threshold: float = 2.8
    ) -> float:
        """计算毛刺过滤率"""

        if not buckets or len(original_vals) == 0:
            return 0.0

        mean_val, std_val = np.mean(original_vals), np.std(original_vals)
        if std_val == 0:
            return 100.0

        spikes = np.where(np.abs(original_vals - mean_val) > threshold * std_val)[0]
        if len(spikes) == 0:
            return 100.0

        filtered = sum(
            1
            for idx in spikes
            if not any(bucket.p5_val <= original_vals[idx] <= bucket.p95_val for bucket in buckets)
        )
        return (filtered / len(spikes)) * 100

    @staticmethod
    def noise_robustness(
        timestamps: np.ndarray, original_vals: np.ndarray, noise_levels: List[float] = None
    ) -> Dict[str, float]:
        """测试不同噪声水平下的SNR"""

        if noise_levels is None:
            noise_levels = [0.1, 0.2, 0.5]

        results = {}
        for level in noise_levels:
            noise = np.random.normal(0, level * np.std(original_vals), len(original_vals))
            noisy_vals = original_vals + noise

            downsampler = AdaptiveDownsampler(**CrossMetricExperiment.DOWNSAMPLER_CONFIG)
            for ts, val in zip(timestamps, noisy_vals):
                downsampler.process(int(ts), float(val))
            downsampler.flush()

            if downsampler.results:
                sampled_ts, sampled_vals = MetricsCalculator.reconstruct_series(downsampler.results)
                reconstructed = np.interp(timestamps, sampled_ts, sampled_vals)
                mse = np.mean((original_vals - reconstructed) ** 2)
                signal_power = np.var(original_vals)
                snr = 10 * np.log10(signal_power / mse) if mse > 0 else float("inf")
                results[f"SNR_{level}"] = snr
            else:
                results[f"SNR_{level}"] = 0.0

        return results


# =============================================================================
# 性能测试器
# =============================================================================


class PerformanceTester:
    """性能测试器"""

    @staticmethod
    def query_speed(db: SQLiteStorage, series_id: str) -> float:
        """测试降采样后数据的查询速度"""

        start = time.time()
        db.get_downsampled(series_id)
        return (time.time() - start) * 1000

    @staticmethod
    def write_latency(
        timestamps: np.ndarray, values: np.ndarray, sample_size: int = 100
    ) -> Dict[str, float]:
        """测试单条写时处理延迟"""

        downsampler = AdaptiveDownsampler(**CrossMetricExperiment.DOWNSAMPLER_CONFIG)
        latencies = []
        for ts, val in zip(timestamps[:sample_size], values[:sample_size]):
            start = time.perf_counter()
            downsampler.process(int(ts), float(val))
            latencies.append((time.perf_counter() - start) * 1000)

        return {
            "mean_ms": float(np.mean(latencies)),
            "std_ms": float(np.std(latencies)),
            "max_ms": float(np.max(latencies)),
            "min_ms": float(np.min(latencies)),
        }


# =============================================================================
# 可视化器
# =============================================================================


class Visualizer:
    """可视化器"""

    @staticmethod
    def plot_comparison(
        series_name: str,
        timestamps: np.ndarray,
        values: np.ndarray,
        buckets: List[BucketResult],
        f_history: List[Tuple[int, float]],
    ):
        """绘制本专利方法的主结果图"""

        fig, axes = plt.subplots(3, 1, figsize=(16, 12))

        ax = axes[0]
        ax.plot(timestamps, values, "b-", alpha=0.5, linewidth=0.5, label="原始数据")
        ax.set_title(f"{series_name} - 原始数据与降采样对比", fontsize=14)
        ax.set_ylabel("数值")
        ax.legend()
        ax.grid(True, alpha=0.3)

        ax = axes[1]
        ax.plot(timestamps, values, "b-", alpha=0.2, linewidth=0.3, label="原始数据")
        for bucket in buckets:
            points = sorted(
                [
                    (bucket.bucket_start, bucket.first_val),
                    (bucket.p5_ts, bucket.p5_val),
                    (bucket.p95_ts, bucket.p95_val),
                    (bucket.bucket_end, bucket.last_val),
                ]
            )
            ax.plot(
                [p[0] for p in points],
                [p[1] for p in points],
                "r-o",
                markersize=2,
                linewidth=1.5,
                alpha=0.7,
            )
            color = "green" if bucket.close_reason == "FLUCTUATION" else "orange"
            ax.axvspan(bucket.bucket_start, bucket.bucket_end, alpha=0.15, color=color)

        ax.set_title("降采样分桶 (绿色=波动触发, 橙色=时间上限)", fontsize=12)
        ax.set_ylabel("数值")
        ax.legend(["原始数据", "降采样"])
        ax.grid(True, alpha=0.3)

        ax = axes[2]
        if f_history:
            f_ts, f_vals = zip(*f_history)
            ax.plot(f_ts, f_vals, "g-", linewidth=2, label="F (EWMA阈值)")
            ax.set_title("EWMA阈值F收敛曲线", fontsize=12)
            ax.set_xlabel("时间 (秒)")
            ax.set_ylabel("F值")
            ax.legend()
            ax.grid(True, alpha=0.3)

        plt.tight_layout()

        name_map = {"使用率": "cpu", "使用量": "memory"}
        filename = series_name.lower()
        for cn_name, en_name in name_map.items():
            filename = filename.replace(cn_name, en_name)

        plt.savefig(f"plots/experiment1_{filename}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  已保存: plots/experiment1_{filename}.png")

    @staticmethod
    def plot_external_comparison(
        series_name: str,
        timestamps: np.ndarray,
        values: np.ndarray,
        comparisons: Dict[str, ComparisonResult],
        title_suffix: str,
        file_suffix: str,
    ):
        """绘制外部对比图"""

        color_map = {
            "patent": "red",
            "lttb": "blue",
            "fixed_window": "green",
        }
        ordered_keys = ["patent", "lttb", "fixed_window"]
        fig, axes = plt.subplots(4, 1, figsize=(16, 12), sharex=True)
        fig.suptitle(f"{series_name} - {title_suffix}", fontsize=14)

        axes[0].plot(
            timestamps,
            values,
            color="slateblue",
            alpha=0.65,
            linewidth=0.6,
            label=f"原始数据 ({len(values):,}点)",
        )
        axes[0].set_ylabel("原始值")
        axes[0].set_title("原始数据", fontsize=11)
        axes[0].grid(True, alpha=0.25)
        axes[0].legend(loc="upper right")

        for ax, key in zip(axes[1:], ordered_keys):
            result = comparisons.get(key)
            if result is None or result.sampled_ts is None or result.sampled_vals is None:
                continue

            ax.plot(
                timestamps,
                values,
                color="lightgray",
                alpha=0.35,
                linewidth=0.45,
                label="原始数据背景",
            )
            ax.plot(
                result.sampled_ts,
                result.sampled_vals,
                linewidth=1.35,
                alpha=0.95,
                color=color_map.get(key, "black"),
                marker="o",
                markersize=1.8,
                markevery=max(1, len(result.sampled_ts) // 80),
                label=(
                    f"{result.name} | 点数={result.output_points}, "
                    f"NRMSE={result.nrmse:.4f}, 相关={result.correlation:.4f}"
                ),
            )
            ax.set_ylabel("摘要值")
            ax.set_title(result.name, fontsize=11)
            ax.grid(True, alpha=0.25)
            ax.legend(loc="upper right", fontsize=9)

        axes[-1].set_xlabel("时间 (秒)")
        plt.tight_layout()

        name_map = {"使用率": "cpu", "使用量": "memory"}
        filename = series_name.lower()
        for cn_name, en_name in name_map.items():
            filename = filename.replace(cn_name, en_name)

        plt.savefig(
            f"plots/experiment1_external_{file_suffix}_{filename}.png",
            dpi=150,
            bbox_inches="tight",
        )
        plt.close()
        print(f"  已保存: plots/experiment1_external_{file_suffix}_{filename}.png")


# =============================================================================
# 报告生成器
# =============================================================================


class ReportGenerator:
    """报告生成器"""

    @staticmethod
    def print_summary(results: Dict[str, EvaluationResult]):
        """打印汇总报告"""

        print("\n" + "=" * 88)
        print("实验1总结: 跨指标综合验证（CPU + Memory，1天公平预算对比 + 7天固定参数跨查询范围）")
        print("=" * 88)

        for series_id, result in results.items():
            ReportGenerator._print_metric_report(series_id, result)

        ReportGenerator._print_conclusions()

    @staticmethod
    def _print_metric_report(series_id: str, result: EvaluationResult):
        """打印单个指标报告"""

        print(f"\n{series_id}:")
        print(f"  原始数据点数:         {result.total_points:,}")
        print(f"  降采样桶数:           {result.total_buckets}")
        print(f"  存储压缩比(bucket):   {result.compression_ratio:.1f}:1")
        print(f"  可视化压缩比(4点):    {result.visual_compression_ratio:.1f}:1")
        print(f"  最终F值:              {result.f_final:.2f}")

        reasons = result.close_reasons
        print(
            f"  闭合原因:             时间上限={reasons.count('TMAX')}, "
            f"波动触发={reasons.count('FLUCTUATION')}, 刷新={reasons.count('FLUSH')}"
        )

        print(f"\n  【自适应适配】")
        print(f"  F收敛速度:            {result.convergence_buckets} 桶")
        print(f"  是否达到稳态:         {'是' if result.is_stable else '否'}")
        print(f"  F稳态CV:              {result.f_stable_cv:.4f}")
        print(f"  平均桶宽:             {result.avg_bucket_width:.2f} 秒")
        print(f"  中位桶宽:             {result.median_bucket_width:.2f} 秒")
        print(f"  波动触发占比:         {result.fluctuation_ratio:.2%}")
        print(f"  时间上限占比:         {result.tmax_ratio:.2%}")

        print(f"\n  【趋势保真】")
        print(f"  相关系数:             {result.correlation:.4f}")
        print(f"  重建误差NRMSE:        {result.nrmse:.4f}")

        print(f"\n  【工程性能】")
        print(f"  全流程写时耗时:       {result.process_time_ms:.4f} ms")
        print(f"  查询速度:             {result.query_speed_ms:.4f} ms")
        if result.write_latency:
            latency = result.write_latency
            print(
                f"  单条处理延迟:         {latency['mean_ms']:.4f} ± {latency['std_ms']:.4f} ms"
            )

        print(f"\n  【鲁棒性】")
        print(f"  毛刺过滤率:           {result.spike_filter_rate:.2f}%")
        if result.noise_robustness:
            for key, value in result.noise_robustness.items():
                print(f"  噪声鲁棒性({key}):     {value:.2f} dB")

        ReportGenerator._print_comparison_section(
            "  【外部对比：公平预算（1天查询）】", result.fair_budget_comparisons
        )
        ReportGenerator._print_comparison_section(
            "  【外部对比：固定参数跨查询范围】",
            result.cross_range_fixed_param_comparisons,
        )
    @staticmethod
    def _print_comparison_section(
        title: str, comparison_results: Optional[Dict[str, ComparisonResult]]
    ):
        """打印对比或消融结果"""

        if not comparison_results:
            return

        print(f"\n{title}")
        for comparison in comparison_results.values():
            print(
                f"  {comparison.name:<18}"
                f"点数={comparison.output_points:>5}  "
                f"压缩比={comparison.compression_ratio:>6.2f}:1  "
                f"相关={comparison.correlation:>7.4f}  "
                f"NRMSE={comparison.nrmse:>7.4f}  "
                f"写入={comparison.write_time_ms:>8.3f}ms  "
                f"查询={comparison.query_time_ms:>8.3f}ms  "
                f"{comparison.tuning_cost}"
            )
            if comparison.note:
                print(f"    说明: {comparison.note}")

    @staticmethod
    def _print_conclusions():
        """打印核心结论"""

        print("\n" + "=" * 88)
        print("核心结论:")
        print("  1. experiment1 聚焦 CPU 与 Memory 两类代表性场景，验证统一参数跨场景适配。")
        print("  2. 公平预算对比用于比较1天查询、相同输出预算下的趋势保真。")
        print("  3. 固定参数跨查询范围对比用于比较从1天扩展到7天后外部方法的调参依赖。")
        print("=" * 88)


# =============================================================================
# 主实验类
# =============================================================================


class CrossMetricExperiment:
    """跨指标综合验证实验"""

    FAIR_QUERY_DIVISOR = 7
    FAIR_QUERY_LABEL = "1天查询"
    FULL_QUERY_LABEL = "7天全程查询"
    RESULTS_SUMMARY_JSON = "experiment1_results_current.json"
    RESULTS_FULL_JSON = "experiment1_results_full.json"
    DOWNSAMPLER_CONFIG = {
        "tmax": 1800,
        "tmin": 60,
        "alpha": 0.4,
        "f_initial": 50,
        "f_min": 5.0,
    }
    METRIC_CONFIGS = {
        "CPU": MetricConfig("CPU使用率", generate_cpu_data),
        "Memory": MetricConfig("内存使用量", generate_memory_data),
    }

    def __init__(self, db_path: str = "experiment1.db"):
        self.db_path = db_path
        self.db = SQLiteStorage(db_path)
        self.calculator = MetricsCalculator()
        self.perf_tester = PerformanceTester()
        self.visualizer = Visualizer()

    def run(self) -> Dict[str, EvaluationResult]:
        """运行实验"""

        os.makedirs("plots", exist_ok=True)
        results = {}

        for series_id, config in self.METRIC_CONFIGS.items():
            print(f"\n{'=' * 60}")
            print(f"处理指标: {config.name}")
            print(f"{'=' * 60}")

            existing_raw = self.db.get_raw(series_id)
            self.db.delete_downsampled(series_id)

            if existing_raw:
                print("  发现已有原始数据，重新计算降采样...")
                timestamps = np.array([row[0] for row in existing_raw])
                values = np.array([row[1] for row in existing_raw])
            else:
                print("  生成实验数据...")
                timestamps, values = config.generator(duration_hours=config.duration_hours)
                self.db.insert_raw_batch(timestamps, values, series_id)
                self.db.commit()

            results[series_id] = self._process_and_evaluate(series_id, timestamps, values)

        self.db.close()
        ReportGenerator.print_summary(results)
        self.export_results_json(results)
        return results

    @staticmethod
    def _metric_plot_filename(series_name: str) -> str:
        """将中文指标名映射为图像文件名后缀"""

        name_map = {"使用率": "cpu", "使用量": "memory"}
        filename = series_name.lower()
        for cn_name, en_name in name_map.items():
            filename = filename.replace(cn_name, en_name)
        return filename

    @staticmethod
    def _json_safe(value):
        """将 numpy / dataclass 结果转为可序列化对象"""

        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, dict):
            return {key: CrossMetricExperiment._json_safe(val) for key, val in value.items()}
        if isinstance(value, (list, tuple)):
            return [CrossMetricExperiment._json_safe(item) for item in value]
        return value

    def _comparison_to_summary(self, comparison: ComparisonResult) -> Dict:
        """提取用于报告核对的精简对比结果"""

        return {
            "name": comparison.name,
            "category": comparison.category,
            "output_points": comparison.output_points,
            "total_buckets": comparison.total_buckets,
            "compression_ratio": comparison.compression_ratio,
            "correlation": comparison.correlation,
            "nrmse": comparison.nrmse,
            "write_time_ms": comparison.write_time_ms,
            "query_time_ms": comparison.query_time_ms,
            "tuning_cost": comparison.tuning_cost,
            "note": comparison.note,
        }

    def _metric_artifacts(self, series_id: str) -> Dict[str, str]:
        """返回场景对应的图像产物路径"""

        metric_name = self.METRIC_CONFIGS[series_id].name
        filename = self._metric_plot_filename(metric_name)
        return {
            "main_plot": f"plots/experiment1_{filename}.png",
            "fair_budget_plot": f"plots/experiment1_external_fair_{filename}.png",
            "cross_range_plot": f"plots/experiment1_external_unified_{filename}.png",
        }

    def _build_summary_payload(self, results: Dict[str, EvaluationResult]) -> Dict:
        """构造供 Markdown 和图表核对使用的摘要 JSON"""

        total_duration_hours = next(iter(self.METRIC_CONFIGS.values())).duration_hours
        fair_duration_hours = total_duration_hours / self.FAIR_QUERY_DIVISOR
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "db_path": self.db_path,
            "downsampler_config": dict(self.DOWNSAMPLER_CONFIG),
            "protocol": {
                "fair_budget": {
                    "label": self.FAIR_QUERY_LABEL,
                    "duration_hours": fair_duration_hours,
                    "duration_days": fair_duration_hours / 24,
                    "fraction_of_full_range": f"1/{self.FAIR_QUERY_DIVISOR}",
                    "description": "在前1天查询窗口内按相同输出预算比较趋势保真",
                },
                "cross_range_fixed_param": {
                    "label": self.FULL_QUERY_LABEL,
                    "duration_hours": total_duration_hours,
                    "duration_days": total_duration_hours / 24,
                    "fixed_parameter_source": self.FAIR_QUERY_LABEL,
                    "description": "在7天全程查询中沿用1天查询确定的外部方法参数",
                },
            },
            "metrics": {},
        }

        for series_id, result in results.items():
            payload["metrics"][series_id] = {
                "metric_name": self.METRIC_CONFIGS[series_id].name,
                "artifacts": self._metric_artifacts(series_id),
                "summary": {
                    "total_points": result.total_points,
                    "total_buckets": result.total_buckets,
                    "compression_ratio": result.compression_ratio,
                    "visual_compression_ratio": result.visual_compression_ratio,
                    "f_final": result.f_final,
                    "correlation": result.correlation,
                    "nrmse": result.nrmse,
                },
                "adaptive_behavior": {
                    "convergence_buckets": result.convergence_buckets,
                    "is_stable": result.is_stable,
                    "f_stable_cv": result.f_stable_cv,
                    "avg_bucket_width": result.avg_bucket_width,
                    "median_bucket_width": result.median_bucket_width,
                    "fluctuation_ratio": result.fluctuation_ratio,
                    "tmax_ratio": result.tmax_ratio,
                },
                "performance": {
                    "process_time_ms": result.process_time_ms,
                    "query_speed_ms": result.query_speed_ms,
                    "write_latency": self._json_safe(result.write_latency),
                },
                "robustness": {
                    "spike_filter_rate": result.spike_filter_rate,
                    "noise_robustness": self._json_safe(result.noise_robustness),
                },
                "fair_budget_comparisons": {
                    key: self._comparison_to_summary(val)
                    for key, val in (result.fair_budget_comparisons or {}).items()
                },
                "cross_range_fixed_param_comparisons": {
                    key: self._comparison_to_summary(val)
                    for key, val in (result.cross_range_fixed_param_comparisons or {}).items()
                },
            }

        return payload

    def export_results_json(self, results: Dict[str, EvaluationResult]):
        """自动导出实验结果 JSON，供后续文案和图表核对使用"""

        summary_payload = self._build_summary_payload(results)
        full_payload = self._json_safe({series_id: asdict(result) for series_id, result in results.items()})
        for output_path in (self.RESULTS_SUMMARY_JSON, self.RESULTS_FULL_JSON):
            if os.path.exists(output_path):
                os.remove(output_path)

        with open(self.RESULTS_SUMMARY_JSON, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, ensure_ascii=False, indent=2)

        with open(self.RESULTS_FULL_JSON, "w", encoding="utf-8") as f:
            json.dump(full_payload, f, ensure_ascii=False, indent=2)

        print(f"\n已导出摘要结果: {self.RESULTS_SUMMARY_JSON}")
        print(f"已导出完整结果: {self.RESULTS_FULL_JSON}")

    def _process_and_evaluate(
        self, series_id: str, timestamps: np.ndarray, values: np.ndarray
    ) -> EvaluationResult:
        """处理主流程并评估"""

        write_latency = self.perf_tester.write_latency(timestamps, values)
        downsampler = AdaptiveDownsampler(**self.DOWNSAMPLER_CONFIG)

        process_start = time.perf_counter()
        for ts, val in zip(timestamps, values):
            self.db.insert_raw_backup(int(ts), float(val), series_id)
            if result := downsampler.process(int(ts), float(val)):
                self.db.insert_bucket(result, series_id)

        if flush_result := downsampler.flush():
            self.db.insert_bucket(flush_result, series_id)

        self.db.commit()
        process_time_ms = (time.perf_counter() - process_start) * 1000
        query_speed_ms = self.perf_tester.query_speed(self.db, series_id)

        fair_budget_comparisons, cross_range_fixed_param_comparisons = self._run_external_comparisons(
            timestamps,
            values,
            downsampler.results,
            process_time_ms,
            query_speed_ms,
        )
        metric_name = self.METRIC_CONFIGS[series_id].name
        self.visualizer.plot_comparison(
            metric_name, timestamps, values, downsampler.results, downsampler.f_history
        )
        self.visualizer.plot_external_comparison(
            metric_name,
            timestamps[: max(2, len(timestamps) // 7)],
            values[: max(2, len(values) // 7)],
            fair_budget_comparisons,
            title_suffix="外部对比（公平预算，1天查询，分面展示）",
            file_suffix="fair",
        )
        self.visualizer.plot_external_comparison(
            metric_name,
            timestamps,
            values,
            cross_range_fixed_param_comparisons,
            title_suffix="外部对比（固定参数跨查询范围，7天全程查询，分面展示）",
            file_suffix="unified",
        )

        return self._compute_evaluation_result(
            timestamps=timestamps,
            values=values,
            buckets=downsampler.results,
            f_history=downsampler.f_history,
            process_time_ms=process_time_ms,
            query_speed_ms=query_speed_ms,
            write_latency=write_latency,
            fair_budget_comparisons=fair_budget_comparisons,
            cross_range_fixed_param_comparisons=cross_range_fixed_param_comparisons,
        )

    def _run_external_comparisons(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        patent_buckets: List[BucketResult],
        patent_write_time_ms: float,
        patent_query_time_ms: float,
    ) -> Tuple[Dict[str, ComparisonResult], Dict[str, ComparisonResult]]:
        """运行两套外部对比：公平预算（1天查询）+ 固定参数跨查询范围（7天全程）"""

        half_idx = max(2, len(timestamps) // 7)
        fair_timestamps = timestamps[:half_idx]
        fair_values = values[:half_idx]
        fair_end_ts = int(fair_timestamps[-1])

        patent_ts, patent_vals = self.calculator.reconstruct_series(patent_buckets)
        patent_bucket_count_full = len(patent_buckets)
        patent_ts_fair = patent_ts[patent_ts <= fair_end_ts]
        patent_vals_fair = patent_vals[: len(patent_ts_fair)]
        if len(patent_ts_fair) < 2:
            patent_ts_fair = patent_ts[: min(2, len(patent_ts))]
            patent_vals_fair = patent_vals[: len(patent_ts_fair)]
        patent_bucket_count_fair = sum(1 for bucket in patent_buckets if bucket.bucket_start <= fair_end_ts)

        patent_corr_fair, patent_nrmse_fair = self.calculator.evaluate_sampled_series(
            fair_timestamps, fair_values, patent_ts_fair, patent_vals_fair
        )
        patent_result_fair = ComparisonResult(
            name="本专利方法",
            category="external",
            output_points=len(patent_ts_fair),
            total_buckets=max(patent_bucket_count_fair, 1),
            compression_ratio=len(fair_values) / max(len(patent_ts_fair), 1),
            correlation=patent_corr_fair,
            nrmse=patent_nrmse_fair,
            write_time_ms=patent_write_time_ms,
            query_time_ms=patent_query_time_ms,
            tuning_cost="统一参数，无需额外调参",
            note="1天查询窗口内直接读取写时生成的降采样结果",
            sampled_ts=patent_ts_fair,
            sampled_vals=patent_vals_fair,
        )

        patent_corr_full, patent_nrmse_full = self.calculator.evaluate_sampled_series(
            timestamps, values, patent_ts, patent_vals
        )
        patent_result_full = ComparisonResult(
            name="本专利方法",
            category="external",
            output_points=len(patent_ts),
            total_buckets=patent_bucket_count_full,
            compression_ratio=len(values) / max(len(patent_ts), 1),
            correlation=patent_corr_full,
            nrmse=patent_nrmse_full,
            write_time_ms=patent_write_time_ms,
            query_time_ms=patent_query_time_ms,
            tuning_cost="统一参数，无需额外调参",
            note="7天全程查询窗口内直接读取写时生成的降采样结果",
            sampled_ts=patent_ts,
            sampled_vals=patent_vals,
        )

        fair_budget = {"patent": patent_result_fair}
        cross_range_fixed_param = {"patent": patent_result_full}
        data_matrix = np.column_stack([timestamps, values])
        fair_data_matrix = np.column_stack([fair_timestamps, fair_values])
        fair_output_points = max(3, len(patent_ts_fair))
        fair_bucket_count = max(patent_bucket_count_fair, 1)

        fair_budget["lttb"] = self._evaluate_lttb_comparison(
            timestamps=fair_timestamps,
            values=fair_values,
            data_matrix=fair_data_matrix,
            output_points=fair_output_points,
            name="查询侧LTTB",
            note="1天查询阶段扫描原始序列后再降采样",
        )
        fair_budget["fixed_window"] = self._evaluate_fixed_window_comparison(
            timestamps=fair_timestamps,
            values=fair_values,
            target_bucket_count=fair_bucket_count,
            name="固定窗口聚合",
            tuning_cost=f"需预设窗口数({fair_bucket_count})",
            note="1天查询中，固定窗口数量与本专利方法的桶数对齐",
        )

        cross_range_fixed_param["lttb"] = self._evaluate_lttb_comparison(
            timestamps=timestamps,
            values=values,
            data_matrix=data_matrix,
            output_points=fair_output_points,
            name="查询侧LTTB",
            note="查询范围扩展到7天全程，但仍沿用1天查询确定的输出点数",
        )
        cross_range_fixed_param["fixed_window"] = self._evaluate_fixed_window_comparison(
            timestamps=timestamps,
            values=values,
            target_bucket_count=fair_bucket_count,
            name="固定窗口聚合",
            tuning_cost=f"固定窗口数({fair_bucket_count})，查询范围扩大后不调整",
            note="查询范围扩展到7天全程，但仍沿用1天查询确定的桶数",
        )

        return fair_budget, cross_range_fixed_param

    def _evaluate_lttb_comparison(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        data_matrix: np.ndarray,
        output_points: int,
        name: str,
        note: str,
    ) -> ComparisonResult:
        """统一评估 LTTB 对比结果"""

        lttb_start = time.perf_counter()
        lttb_result = lttb_downsample(data_matrix, output_points)
        lttb_query_time_ms = (time.perf_counter() - lttb_start) * 1000
        lttb_ts = lttb_result[:, 0]
        lttb_vals = lttb_result[:, 1]
        lttb_corr, lttb_nrmse = self.calculator.evaluate_sampled_series(
            timestamps, values, lttb_ts, lttb_vals
        )
        return ComparisonResult(
            name=name,
            category="external",
            output_points=len(lttb_ts),
            total_buckets=0,
            compression_ratio=len(values) / max(len(lttb_ts), 1),
            correlation=lttb_corr,
            nrmse=lttb_nrmse,
            write_time_ms=0.0,
            query_time_ms=lttb_query_time_ms,
            tuning_cost=f"需预设输出点数({output_points})",
            note=note,
            sampled_ts=lttb_ts,
            sampled_vals=lttb_vals,
        )

    def _evaluate_fixed_window_comparison(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        target_bucket_count: int,
        name: str,
        tuning_cost: str,
        note: str,
    ) -> ComparisonResult:
        """统一评估固定窗口聚合结果"""

        fixed_start = time.perf_counter()
        fixed_ts, fixed_vals = fixed_window_aggregate_by_count(
            timestamps, values, target_bucket_count
        )
        fixed_query_time_ms = (time.perf_counter() - fixed_start) * 1000
        fixed_corr, fixed_nrmse = self.calculator.evaluate_sampled_series(
            timestamps, values, fixed_ts, fixed_vals
        )
        return ComparisonResult(
            name=name,
            category="external",
            output_points=len(fixed_ts),
            total_buckets=target_bucket_count,
            compression_ratio=len(values) / max(len(fixed_ts), 1),
            correlation=fixed_corr,
            nrmse=fixed_nrmse,
            write_time_ms=0.0,
            query_time_ms=fixed_query_time_ms,
            tuning_cost=tuning_cost,
            note=note,
            sampled_ts=fixed_ts,
            sampled_vals=fixed_vals,
        )

    def _run_ablation_studies(
        self, timestamps: np.ndarray, values: np.ndarray
    ) -> Dict[str, ComparisonResult]:
        """运行内部消融实验"""

        config = self.DOWNSAMPLER_CONFIG
        return {
            "fixed_f": self._evaluate_downsampler_variant(
                name="消融A: 固定阈值",
                downsampler=FixedThresholdDownsampler(
                    fixed_f=config["f_initial"],
                    tmax=config["tmax"],
                    tmin=config["tmin"],
                    alpha=config["alpha"],
                    f_min=config["f_min"],
                ),
                timestamps=timestamps,
                values=values,
                tuning_cost=f"固定F={config['f_initial']}",
                note="关闭EWMA，只保留P5/P95切桶逻辑",
            ),
            "raw_extrema": self._evaluate_downsampler_variant(
                name="消融B: raw min/max",
                downsampler=RawExtremaDownsampler(**config),
                timestamps=timestamps,
                values=values,
                tuning_cost="保持EWMA，改用raw min/max",
                note="验证分位数设计相对极值设计的价值",
            ),
            "raw_extrema_fixed_f": self._evaluate_downsampler_variant(
                name="消融C: 双重移除",
                downsampler=RawExtremaFixedThresholdDownsampler(
                    fixed_f=config["f_initial"],
                    tmax=config["tmax"],
                    tmin=config["tmin"],
                    alpha=config["alpha"],
                    f_min=config["f_min"],
                ),
                timestamps=timestamps,
                values=values,
                tuning_cost="固定F + raw min/max",
                note="同时移除两个创新点，作为组合基线",
            ),
        }

    def _evaluate_downsampler_variant(
        self,
        name: str,
        downsampler: AdaptiveDownsampler,
        timestamps: np.ndarray,
        values: np.ndarray,
        tuning_cost: str,
        note: str,
    ) -> ComparisonResult:
        """统一评估消融变体"""

        start = time.perf_counter()
        for ts, val in zip(timestamps, values):
            downsampler.process(int(ts), float(val))
        if downsampler.has_open_bucket:
            downsampler.flush()
        write_time_ms = (time.perf_counter() - start) * 1000

        query_start = time.perf_counter()
        sampled_ts, sampled_vals = self.calculator.reconstruct_series(downsampler.results)
        query_time_ms = (time.perf_counter() - query_start) * 1000

        corr, nrmse = self.calculator.evaluate_sampled_series(
            timestamps, values, sampled_ts, sampled_vals
        )
        return ComparisonResult(
            name=name,
            category="ablation",
            output_points=len(sampled_ts),
            total_buckets=len(downsampler.results),
            compression_ratio=len(values) / max(len(sampled_ts), 1),
            correlation=corr,
            nrmse=nrmse,
            write_time_ms=write_time_ms,
            query_time_ms=query_time_ms,
            tuning_cost=tuning_cost,
            note=note,
            sampled_ts=sampled_ts,
            sampled_vals=sampled_vals,
        )

    def _compute_evaluation_result(
        self,
        timestamps: np.ndarray,
        values: np.ndarray,
        buckets: List[BucketResult],
        f_history: List[Tuple[int, float]],
        process_time_ms: float,
        query_speed_ms: float,
        write_latency: Optional[Dict] = None,
        fair_budget_comparisons: Optional[Dict[str, ComparisonResult]] = None,
        cross_range_fixed_param_comparisons: Optional[Dict[str, ComparisonResult]] = None,
    ) -> EvaluationResult:
        """计算综合评估结果"""

        sampled_ts, sampled_vals = self.calculator.reconstruct_series(buckets)
        correlation, nrmse = self.calculator.evaluate_sampled_series(
            timestamps, values, sampled_ts, sampled_vals
        )
        convergence_buckets, is_stable = self.calculator.f_convergence_speed(f_history)
        avg_bucket_width, median_bucket_width = self.calculator.bucket_width_stats(buckets)
        fluctuation_ratio, tmax_ratio = self.calculator.close_reason_ratios(buckets)

        return EvaluationResult(
            total_points=len(values),
            total_buckets=len(buckets),
            compression_ratio=len(values) / max(len(buckets), 1),
            visual_compression_ratio=len(values) / max(len(sampled_ts), 1),
            f_final=f_history[-1][1] if f_history else 0.0,
            f_history=f_history,
            close_reasons=[bucket.close_reason for bucket in buckets],
            correlation=correlation,
            nrmse=nrmse,
            convergence_buckets=convergence_buckets,
            is_stable=is_stable,
            f_stable_cv=self.calculator.f_stability_cv(f_history),
            avg_bucket_width=avg_bucket_width,
            median_bucket_width=median_bucket_width,
            fluctuation_ratio=fluctuation_ratio,
            tmax_ratio=tmax_ratio,
            process_time_ms=process_time_ms,
            query_speed_ms=query_speed_ms,
            write_latency=write_latency,
            spike_filter_rate=self.calculator.spike_filter_rate(values, buckets),
            noise_robustness=self.calculator.noise_robustness(timestamps, values),
            fair_budget_comparisons=fair_budget_comparisons,
            cross_range_fixed_param_comparisons=cross_range_fixed_param_comparisons,
        )


# =============================================================================
# 入口
# =============================================================================


if __name__ == "__main__":
    experiment = CrossMetricExperiment()
    experiment.run()
