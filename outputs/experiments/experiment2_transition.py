import os
import numpy as np
import matplotlib.pyplot as plt

from core_algorithm import AdaptiveDownsampler, SQLiteStorage, BucketResult
from data_generator import generate_transition_data
from matplotlib_config import setup_chinese_font

# 设置中文字体
setup_chinese_font()


def run_experiment():
    os.makedirs("plots", exist_ok=True)
    db_path = "experiment2.db"
    db = SQLiteStorage(db_path)

    series_id = "transition"

    # 检查是否已有数据
    existing_raw = db.get_raw(series_id)
    existing_downsampled = db.get_downsampled(series_id)

    if existing_raw and existing_downsampled:
        print("发现已有数据，直接读取...")
        print(f"  原始数据点数: {len(existing_raw):,}")
        print(f"  降采样桶数: {len(existing_downsampled)}")

        # 从数据库恢复结果
        buckets = []
        f_history = []
        for row in existing_downsampled:
            buckets.append(BucketResult(
                bucket_start=row[0],
                bucket_end=row[1],
                first_val=row[2],
                p5_val=row[3],
                p95_val=row[4],
                last_val=row[5],
                bucket_range=row[6],
                close_reason=row[7],
                f_value=row[8],
                p5_ts=row[0],
                p95_ts=row[1],
            ))
            f_history.append((row[1], row[8]))

        t = np.array([r[0] for r in existing_raw])
        values = np.array([r[1] for r in existing_raw])

        plot_transition_analysis(t, values, buckets, f_history)
        analyze_transition_phases(t, values, buckets, f_history)
        db.close()
        return

    print("生成过渡期数据 (24小时, 4个阶段)...")
    t, values = generate_transition_data(duration_hours=24, interval_sec=5)

    downsampler = AdaptiveDownsampler(
        tmax=1800,
        tmin=60,
        alpha=0.6,
        f_initial=50.0,
        f_min=5.0,
    )

    for ts, val in zip(t, values):
        db.insert_raw(int(ts), float(val), series_id)
        result = downsampler.process(int(ts), float(val))
        if result:
            db.insert_bucket(result, series_id)

    flush_result = downsampler.flush()
    if flush_result:
        db.insert_bucket(flush_result, series_id)

    db.commit()

    plot_transition_analysis(t, values, downsampler.results, downsampler.f_history)
    analyze_transition_phases(t, values, downsampler.results, downsampler.f_history)

    db.close()


def plot_transition_analysis(t, values, buckets, f_history):
    fig, axes = plt.subplots(4, 1, figsize=(18, 16))

    phase_duration = 24 * 3600 // 4
    phase_labels = ["阶段1: 平稳期", "阶段2: 波动增加", "阶段3: 波动减少", "阶段4: 中等波动"]

    ax_raw = axes[0]
    ax_raw.plot(t, values, "b-", alpha=0.4, linewidth=0.5)
    for i, label in enumerate(phase_labels):
        ax_raw.axvspan(i * phase_duration, (i + 1) * phase_duration, alpha=0.1)
        ax_raw.text(i * phase_duration + phase_duration / 2, ax_raw.get_ylim()[1] * 0.9, label,
                   ha="center", fontsize=10)
    ax_raw.set_title("过渡期数据 - 4个阶段", fontsize=14)
    ax_raw.set_ylabel("数值")
    ax_raw.grid(True, alpha=0.3)

    ax_buckets = axes[1]
    ax_buckets.plot(t, values, "b-", alpha=0.15, linewidth=0.3)

    for b in buckets:
        points = [
            (b.bucket_start, b.first_val),
            (b.p5_ts, b.p5_val),
            (b.p95_ts, b.p95_val),
            (b.bucket_end, b.last_val),
        ]
        points.sort(key=lambda x: x[0])
        bucket_t = [p[0] for p in points]
        bucket_v = [p[1] for p in points]
        color = "red" if b.close_reason == "FLUCTUATION" else "orange"
        ax_buckets.plot(bucket_t, bucket_v, color=color, marker="o", markersize=2, linewidth=1.5, alpha=0.7)

    ax_buckets.set_title("降采样分桶 (红色=波动触发, 橙色=时间上限触发)", fontsize=12)
    ax_buckets.set_ylabel("数值")
    ax_buckets.grid(True, alpha=0.3)

    ax_f = axes[2]
    if f_history:
        f_ts, f_vals = zip(*f_history)
        ax_f.plot(f_ts, f_vals, "g-", linewidth=2, label="F (EWMA)")
        for i in range(4):
            ax_f.axvspan(i * phase_duration, (i + 1) * phase_duration, alpha=0.1)
        ax_f.set_title("F阈值在各阶段的自适应变化", fontsize=12)
        ax_f.set_ylabel("F值")
        ax_f.legend()
        ax_f.grid(True, alpha=0.3)

    ax_width = axes[3]
    bucket_widths = [b.bucket_end - b.bucket_start for b in buckets]
    bucket_starts = [b.bucket_start for b in buckets]
    colors = ["red" if b.close_reason == "FLUCTUATION" else "orange" for b in buckets]

    ax_width.scatter(bucket_starts, bucket_widths, c=colors, s=20, alpha=0.6)
    ax_width.axhline(y=15000, color="gray", linestyle="--", alpha=0.5, label="时间上限=15000")
    for i in range(4):
        ax_width.axvspan(i * phase_duration, (i + 1) * phase_duration, alpha=0.1)
    ax_width.set_title("桶宽度分布 (红色=波动触发, 橙色=时间上限触发)", fontsize=12)
    ax_width.set_xlabel("时间 (秒)")
    ax_width.set_ylabel("桶宽度 (秒)")
    ax_width.legend()
    ax_width.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("plots/experiment2_transition.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  已保存: plots/experiment2_transition.png")


def analyze_transition_phases(t, values, buckets, f_history):
    print(f"\n{'='*60}")
    print("实验2: 过渡期阶段分析")
    print(f"{'='*60}")

    phase_duration = 24 * 3600 // 4

    for phase in range(4):
        start_t = phase * phase_duration
        end_t = (phase + 1) * phase_duration

        phase_buckets = [b for b in buckets if start_t <= b.bucket_start < end_t]
        phase_f = [(ts, f) for ts, f in f_history if start_t <= ts < end_t]

        if not phase_buckets:
            continue

        widths = [b.bucket_end - b.bucket_start for b in phase_buckets]
        fluct_count = sum(1 for b in phase_buckets if b.close_reason == "FLUCTUATION")
        tmax_count = sum(1 for b in phase_buckets if b.close_reason == "TMAX")

        print(f"\n阶段 {phase + 1} ({start_t}-{end_t}秒):")
        print(f"  桶数量:             {len(phase_buckets)}")
        print(f"  平均桶宽度:         {np.mean(widths):.0f}秒")
        print(f"  中位桶宽度:         {np.median(widths):.0f}秒")
        print(f"  波动触发闭合:       {fluct_count}")
        print(f"  时间上限触发闭合:   {tmax_count}")

        if phase_f:
            f_vals = [f for _, f in phase_f]
            print(f"  F值范围:            {min(f_vals):.1f} - {max(f_vals):.1f}")
            print(f"  F最终值:            {f_vals[-1]:.1f}")

    print(f"\n{'='*60}")
    print("关键发现: 稳态时桶宽度主要由时间上限(TMAX)决定")
    print("过渡期效应仅在阶段变化后的前几个桶中可见")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_experiment()
