import os
import sqlite3
import numpy as np
import matplotlib.pyplot as plt

from core_algorithm import AdaptiveDownsampler
from data_generator import generate_spike_data
from matplotlib_config import setup_chinese_font

# 设置中文字体
setup_chinese_font()

# 使用脚本所在目录作为数据库路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "experiment3_data.db")


def init_database():
    """初始化数据库，创建数据表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment3_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_name TEXT NOT NULL,
            spike_freq REAL,
            spike_amp REAL,
            t BLOB,
            values_data BLOB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def check_data_exists(scenario_name: str, spike_freq: float, spike_amp: float) -> bool:
    """检查指定场景的数据是否已存在"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM experiment3_data WHERE scenario_name = ? AND spike_freq = ? AND spike_amp = ?",
        (scenario_name, spike_freq, spike_amp)
    )
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def save_data(scenario_name: str, spike_freq: float, spike_amp: float, t: np.ndarray, values: np.ndarray):
    """保存实验数据到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO experiment3_data (scenario_name, spike_freq, spike_amp, t, values_data) VALUES (?, ?, ?, ?, ?)",
        (scenario_name, spike_freq, spike_amp, t.tobytes(), values.tobytes())
    )
    conn.commit()
    conn.close()


def load_data(scenario_name: str, spike_freq: float, spike_amp: float) -> tuple:
    """从数据库加载实验数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT t, values_data, length(t), length(values_data) FROM experiment3_data WHERE scenario_name = ? AND spike_freq = ? AND spike_amp = ?",
        (scenario_name, spike_freq, spike_amp)
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        t_bytes, values_bytes, t_len, v_len = row
        # 计算元素个数: float64=8字节
        v_count = v_len // 8
        # t 存储时可能是 int32 或 int64，根据 values 的长度推断
        # t 和 values 长度相同
        t_count = v_count
        if t_len // t_count == 8:
            t_dtype = np.int64
        else:
            t_dtype = np.int32
        t = np.frombuffer(t_bytes, dtype=t_dtype).reshape(-1)[:t_count]
        values = np.frombuffer(values_bytes, dtype=np.float64).reshape(-1)[:v_count]
        return t, values
    return None, None


def get_or_generate_data(scenario_name: str, spike_freq: float, spike_amp: float, seed: int = 42):
    """获取或生成实验数据"""
    if check_data_exists(scenario_name, spike_freq, spike_amp):
        print(f"  从数据库加载数据: {scenario_name}")
        return load_data(scenario_name, spike_freq, spike_amp)
    else:
        print(f"  生成新数据: {scenario_name}")
        np.random.seed(seed)
        t, values = generate_spike_data(
            duration_hours=12,
            interval_sec=5,
            spike_freq=spike_freq,
            spike_amp=spike_amp,
        )
        save_data(scenario_name, spike_freq, spike_amp, t, values)
        return t, values


def run_experiment():
    os.makedirs("plots", exist_ok=True)
    init_database()

    scenarios = {
        "stable": {"spike_freq": 0.0, "spike_amp": 0.0, "label": "平稳 (噪声=3)"},
        "moderate": {"spike_freq": 0.01, "spike_amp": 10.0, "label": "中等 (1%毛刺)"},
        "volatile": {"spike_freq": 0.05, "spike_amp": 20.0, "label": "剧烈 (5%毛刺)"},
    }

    fig, axes = plt.subplots(3, 3, figsize=(18, 14))

    for col, (scenario_name, params) in enumerate(scenarios.items()):
        print(f"\n场景: {scenario_name}")
        t, values = get_or_generate_data(
            scenario_name,
            spike_freq=params["spike_freq"],
            spike_amp=params["spike_amp"],
        )

        downsampler = AdaptiveDownsampler(
            tmax=1800,
            tmin=60,
            alpha=0.4,
            f_initial=50.0,
            f_min=5.0,
        )

        for ts, val in zip(t, values):
            result = downsampler.process(int(ts), float(val))

        downsampler.flush()

        ax_raw = axes[0, col]
        ax_raw.plot(t, values, "b-", alpha=0.5, linewidth=0.5)
        ax_raw.set_title(params["label"], fontsize=12)
        ax_raw.set_ylabel("数值")
        ax_raw.grid(True, alpha=0.3)

        ax_down = axes[1, col]
        ax_down.plot(t, values, "b-", alpha=0.15, linewidth=0.3)
        for b in downsampler.results:
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
            ax_down.plot(bucket_t, bucket_v, color=color, marker="o", markersize=1.5, linewidth=1.2, alpha=0.7)
        ax_down.set_ylabel("数值")
        ax_down.grid(True, alpha=0.3)

        ax_f = axes[2, col]
        if downsampler.f_history:
            f_ts, f_vals = zip(*downsampler.f_history)
            ax_f.plot(f_ts, f_vals, "g-", linewidth=2)
            ax_f.set_xlabel("时间 (秒)")
            ax_f.set_ylabel("F值")
            ax_f.grid(True, alpha=0.3)

        print(f"  桶数量: {len(downsampler.results)}")
        print(f"  最终F值: {downsampler.f:.2f}")
        print(f"  压缩比: {len(t) / len(downsampler.results):.1f}:1")

    plt.tight_layout()
    plt.savefig("plots/experiment3_bucket_density.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("\n  已保存: plots/experiment3_bucket_density.png")

    analyze_density_vs_fluctuation()


def analyze_density_vs_fluctuation():
    print(f"\n{'='*60}")
    print("实验3: 桶密度与波动水平分析")
    print(f"{'='*60}")

    fluctuation_levels = [3, 5, 10, 20, 30, 50]
    bucket_counts = []

    for fluct in fluctuation_levels:
        np.random.seed(42)
        n = int(12 * 3600 / 5)
        t = np.arange(n) * 5
        values = 50 + np.random.normal(0, fluct, n)

        downsampler = AdaptiveDownsampler(
            tmax=15000, tmin=60, alpha=0.25, f_initial=50.0, f_min=5.0
        )

        for ts, val in zip(t, values):
            downsampler.process(int(ts), float(val))
        downsampler.flush()

        bucket_counts.append(len(downsampler.results))
        print(f"  波动水平 σ={fluct:2d}: {len(downsampler.results):4d} 个桶, F最终值={downsampler.f:.1f}")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(fluctuation_levels, bucket_counts, "bo-", linewidth=2, markersize=8)
    ax.set_xlabel("波动水平 (σ)", fontsize=12)
    ax.set_ylabel("桶数量 (12小时周期)", fontsize=12)
    ax.set_title("桶数量与波动水平关系 (稳态)", fontsize=14)
    ax.grid(True, alpha=0.3)

    for i, count in enumerate(bucket_counts):
        ax.annotate(str(count), (fluctuation_levels[i], count), textcoords="offset points", xytext=(0, 10), ha="center")

    plt.tight_layout()
    plt.savefig("plots/experiment3_density_vs_fluctuation.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  已保存: plots/experiment3_density_vs_fluctuation.png")

    print(f"\n{'='*60}")
    print("关键发现: 稳态时桶数量相对稳定")
    print("不同波动水平下主要由时间上限(TMAX)决定")
    print(f"{'='*60}")


if __name__ == "__main__":
    run_experiment()
