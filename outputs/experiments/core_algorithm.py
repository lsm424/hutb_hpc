import os
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional
import sqlite3


@dataclass
class BucketResult:
    bucket_start: int
    bucket_end: int
    first_val: float
    p5_val: float
    p5_ts: int
    p95_val: float
    p95_ts: int
    last_val: float
    bucket_range: float
    close_reason: str
    f_value: float = 0.0


class AdaptiveDownsampler:
    def __init__(
        self,
        tmax: int = 15000,
        tmin: int = 60,
        alpha: float = 0.25,
        f_initial: float = 50.0,
        f_min: float = 5.0,
    ):
        self.tmax = tmax
        self.tmin = tmin
        self.alpha = alpha
        self.f = f_initial
        self.f_min = f_min

        self.t0 = 0
        self.first_val = 0.0
        self.last_val = 0.0
        self.last_ts = 0
        self.has_open_bucket = False

        self.values_buffer: List[float] = []
        self.timestamps_buffer: List[int] = []

        self.results: List[BucketResult] = []
        self.f_history: List[Tuple[int, float]] = []
        self.bucket_ranges: List[Tuple[int, float]] = []

    def process(self, ts: int, value: float) -> Optional[BucketResult]:
        if not self.has_open_bucket:
            self._create_bucket(ts, value)
            return None

        self.values_buffer.append(value)
        self.timestamps_buffer.append(ts)
        self.last_val = value
        self.last_ts = ts

        p5, p5_ts = self._compute_percentile(0.05)
        p95, p95_ts = self._compute_percentile(0.95)
        bucket_range = p95 - p5

        time_elapsed = ts - self.t0

        cond1 = time_elapsed > self.tmax
        cond2 = (time_elapsed > self.tmin) and (bucket_range > self.f)

        if cond1 or cond2:
            reason = "TMAX" if cond1 else "FLUCTUATION"
            result = self._close_bucket(ts, value, p5, p5_ts, p95, p95_ts, bucket_range, reason)
            self._create_bucket(ts, value)
            return result

        return None

    def _create_bucket(self, ts: int, value: float):
        self.t0 = ts
        self.first_val = value
        self.last_val = value
        self.last_ts = ts
        self.values_buffer = [value]
        self.timestamps_buffer = [ts]
        self.has_open_bucket = True

    def _compute_percentile(self, p: float) -> Tuple[float, int]:
        if not self.values_buffer:
            return 0.0, self.t0

        sorted_pairs = sorted(zip(self.values_buffer, self.timestamps_buffer))
        idx = int(p * len(sorted_pairs))
        idx = min(idx, len(sorted_pairs) - 1)
        return sorted_pairs[idx][0], sorted_pairs[idx][1]

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
        # 记录当前f值（用于此bucket的阈值）
        current_f = self.f

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

        # 更新f值用于下一个bucket
        self.f = max(
            self.alpha * bucket_range + (1 - self.alpha) * self.f,
            self.f_min,
        )
        self.f_history.append((ts, self.f))

        self.has_open_bucket = False
        return result

    def flush(self) -> Optional[BucketResult]:
        if not self.has_open_bucket:
            return None

        p5, p5_ts = self._compute_percentile(0.05)
        p95, p95_ts = self._compute_percentile(0.95)
        bucket_range = p95 - p5

        return self._close_bucket(
            self.last_ts, self.last_val, p5, p5_ts, p95, p95_ts, bucket_range, "FLUSH"
        )


class SQLiteStorage:
    def __init__(self, db_path: str = ":memory:"):
        # if os.path.exists(db_path):
        #     os.remove(db_path)
        self.conn = sqlite3.connect(db_path)
        self._init_tables()

    def _init_tables(self):
        # 原始数据表（永久存储，用于复现）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_data (
                ts INTEGER NOT NULL,
                value REAL NOT NULL,
                series_id TEXT NOT NULL
            )
        """)
        # 备份表（每次运行清空，存储本次运行的完整数据链路）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_data_backup (
                ts INTEGER NOT NULL,
                value REAL NOT NULL,
                series_id TEXT NOT NULL,
                run_id INTEGER NOT NULL DEFAULT 1
            )
        """)
        # 清空备份表
        self.conn.execute("DELETE FROM raw_data_backup")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS downsampled (
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
                close_reason TEXT NOT NULL,
                f_value REAL NOT NULL DEFAULT 0.0
            )
        """)
        self.conn.commit()


    def insert_raw_batch(self, timestamps, values, series_id: str):
        """批量插入原始数据主表，不写入备份表"""
        self.conn.executemany(
            "INSERT INTO raw_data (ts, value, series_id) VALUES (?, ?, ?)",
            [(int(ts), float(value), series_id) for ts, value in zip(timestamps, values)],
        )

    def insert_raw_backup(self, ts: int, value: float, series_id: str):
        """仅插入备份表，不写入原始数据主表"""
        self.conn.execute(
            "INSERT INTO raw_data_backup (ts, value, series_id) VALUES (?, ?, ?)",
            (ts, value, series_id),
        )

    def insert_bucket(self, result: BucketResult, series_id: str):
        self.conn.execute(
            """
            INSERT INTO downsampled (
                series_id, bucket_start, bucket_end, first_val,
                p5_val, p5_ts, p95_val, p95_ts, last_val,
                bucket_range, close_reason, f_value
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                series_id,
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
                result.f_value,
            ),
        )

    def get_raw(self, series_id: str) -> List[Tuple[int, float]]:
        cursor = self.conn.execute(
            "SELECT ts, value FROM raw_data WHERE series_id = ? ORDER BY ts",
            (series_id,),
        )
        return cursor.fetchall()

    def get_downsampled(self, series_id: str) -> List[Tuple]:
        cursor = self.conn.execute(
            """
            SELECT bucket_start, bucket_end, first_val, p5_val, p95_val, last_val,
                   bucket_range, close_reason, f_value
            FROM downsampled
            WHERE series_id = ?
            ORDER BY bucket_start
            """,
            (series_id,),
        )
        return cursor.fetchall()

    def delete_raw(self, series_id: str):
        """删除指定序列的原始数据主表记录"""
        self.conn.execute("DELETE FROM raw_data WHERE series_id = ?", (series_id,))

    def delete_downsampled(self, series_id: str):
        """删除指定序列的降采样数据"""
        self.conn.execute("DELETE FROM downsampled WHERE series_id = ?", (series_id,))

    def get_raw_backup(self, series_id: str) -> List[Tuple[int, float]]:
        """获取备份表中的原始数据（本次运行的数据链路）"""
        cursor = self.conn.execute(
            "SELECT ts, value FROM raw_data_backup WHERE series_id = ? ORDER BY ts",
            (series_id,),
        )
        return cursor.fetchall()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()
