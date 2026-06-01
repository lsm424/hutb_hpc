import numpy as np
from typing import List, Tuple


def generate_cpu_data(duration_hours: float = 7*24, interval_sec: float = 5) -> Tuple[np.ndarray, np.ndarray]:
    # 计算数据点数量：将小时转换为秒，然后除以采样间隔
    n = int(duration_hours * 3600 / interval_sec)
    # 生成时间戳数组，每个元素代表从起始时刻经过的秒数
    t = np.arange(n) * interval_sec

    # 基础CPU使用率，设定为50%
    base = 50.0
    # 季节性波动：每小时一个周期，振幅为20%
    seasonal = 20.0 * np.sin(2 * np.pi * t / 3600)
    # 随机噪声：均值为0，标准差为10的正态分布
    noise = np.random.normal(0, 10.0, n)
    # 随机尖峰：2%概率出现30%的尖峰，98%概率为0
    spikes = np.random.choice([0, 30], size=n, p=[0.98, 0.02])

    # 将基础值、季节性、噪声和尖峰叠加
    values = base + seasonal + noise + spikes
    # 将数值限制在0-100范围内（百分比）
    values = np.clip(values, 0, 100)
    # 返回时间戳（转为整数）和对应的CPU使用率值
    return t.astype(int), values


def generate_memory_data(duration_hours: float = 7*24, interval_sec: float = 5) -> Tuple[np.ndarray, np.ndarray]:
    n = int(duration_hours * 3600 / interval_sec)
    t = np.arange(n) * interval_sec

    values = np.zeros(n)
    values[0] = 128.0

    for i in range(1, n):
        step = np.random.choice([-20, 0, 20], p=[0.1, 0.8, 0.1])
        values[i] = values[i-1] + step + np.random.normal(0, 5.0)

    values = np.clip(values, 0, 256)
    return t.astype(int), values


def generate_network_data(duration_hours: float = 7*24, interval_sec: float = 5) -> Tuple[np.ndarray, np.ndarray]:
    n = int(duration_hours * 3600 / interval_sec)
    t = np.arange(n) * interval_sec

    base = 5000.0
    noise = np.random.normal(0, 500.0, n)

    spikes = np.zeros(n)
    spike_times = np.random.choice(n, size=int(n * 0.05), replace=False)
    spikes[spike_times] = np.random.uniform(3000, 5000, size=len(spike_times))

    values = base + noise + spikes
    values = np.clip(values, 0, 10000)
    return t.astype(int), values


def generate_transition_data(duration_hours: float = 24, interval_sec: float = 5) -> Tuple[np.ndarray, np.ndarray]:
    n = int(duration_hours * 3600 / interval_sec)
    t = np.arange(n) * interval_sec

    phase_duration = n // 4
    values = np.zeros(n)

    for i in range(n):
        phase = i // phase_duration
        phase_pos = (i % phase_duration) / phase_duration

        if phase == 0:
            base = 50.0
            noise_std = 5.0
        elif phase == 1:
            base = 50.0 + phase_pos * 30.0
            noise_std = 5.0 + phase_pos * 45.0
        elif phase == 2:
            base = 80.0 - phase_pos * 30.0
            noise_std = 50.0 - phase_pos * 45.0
        else:
            base = 50.0
            noise_std = 25.0

        values[i] = base + np.random.normal(0, noise_std)

    values = np.clip(values, 0, 100)
    return t.astype(int), values


def generate_spike_data(
    duration_hours: float = 6,
    interval_sec: float = 5,
    spike_freq: float = 0.01,
    spike_amp: float = 10.0,
) -> Tuple[np.ndarray, np.ndarray]:
    n = int(duration_hours * 3600 / interval_sec)
    t = np.arange(n) * interval_sec

    base = 50.0
    noise = np.random.normal(0, 3.0, n)
    spikes = np.zeros(n)

    spike_indices = np.random.choice(n, size=int(n * spike_freq), replace=False)
    spikes[spike_indices] = spike_amp * np.random.uniform(0.5, 1.5, size=len(spike_indices))

    values = base + noise + spikes
    return t.astype(int), values
