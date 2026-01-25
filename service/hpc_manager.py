from collections import Counter
from typing import Any
from infra.hpc_api import HpcApi
from common import cfg, logger
from threading import Lock
from itertools import groupby
from common.utils import Unit2int
from datetime import datetime, timedelta
from functools import reduce
from sqlalchemy import and_, tuple_, text, insert, func
from sqlalchemy.exc import IntegrityError
from models.model import TNodeCpuHistoryInfo, TNodeGpuHistoryInfo, TNodeMemHistoryInfo, TDailyReportInfo
from models import get_db_context_session
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
import time
import pandas as pd
from infra.hpc_api import api


def _extract_gpu_key(info: dict):
    for key in info.keys():
        if ':' in key:
            return key
    return ''


def map2resourcedesc(task):
    if task['cpu'] is None or pd.isna(task['cpu']):
        return '-'
    
    resp = f"{int(task['cpu'])}C / {task['mem']}"
    if task['card'] is not None and not pd.isna(task['card']):
        resp += f" / {task['card_type']}:{int(task['card'])}卡"
    return resp

class Task:
    tasks_info = []
    tasks_by_node = {}
    tasks_by_partition = {}
    tasks_by_id = {}

    def __init__(self, task_id):
        self.task_info = Task.tasks_by_id.get(task_id, {})
        
    def get_daily_report(self):
        submit_time = datetime.strptime(self.task_info['submitTime'], '%Y-%m-%d %H:%M:%S')
        if self.task_info['startTime']:
            start_time = datetime.strptime(self.task_info['startTime'], '%Y-%m-%d %H:%M:%S')
        else:
            start_time = datetime.now()
        wait_time = start_time - submit_time
        # 将timedelta类型的wait_time转为易读的字符串
        total_seconds = int(wait_time.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            wait_time_str = f"{days}天{hours}小时{minutes}分"
        elif hours > 0:
            wait_time_str = f"{hours}小时{minutes}分"
        elif minutes > 0:
            wait_time_str = f"{minutes}分{seconds}秒"
        else:
            wait_time_str = f"{seconds}秒"

        return {
            'job_id': self.task_info['slurmJobId'],
            'user': self.task_info['createBy'],
            'partition': self.task_info['partition'],
            'submit_time': self.task_info['submitTime'],
            'wait_time': wait_time_str,
            'resource': map2resourcedesc(self.task_info),
        }

    @staticmethod
    def map2resources(task):
        try:
            resourceUsed = task['resourceUsed']
            gpu_key = _extract_gpu_key(resourceUsed)
            task['cpu'] = int(resourceUsed['cpu'])
            task['mem'] = resourceUsed['mem']
            task['card'] = int(resourceUsed[gpu_key]) if gpu_key else None
            task['card_type'] = gpu_key
        except Exception as e:
            task['cpu'] = None
            task['mem'] = None
            task['card'] = None
            task['card_type'] = None

    @staticmethod
    def mapstatus2ch(status):
        if status == 'RUNNING':
            return '运行中'
        elif status == 'PENDING':
            return '排队中'
        elif status == 'COMPLETED':
            return '已完成'
        elif status == 'FAILED':
            return '失败'
        elif status == 'CANCELLED':
            return '已取消'
        else:
            return '未知'

    @staticmethod
    def update_tasks_info():
        tasks = []
        for status in [api.StatusRunning, api.StatusPending, api.StatusCompleted, api.StatusFailed]:
            for i in range(5):
                tasks_info = api.get_tasks(status)
                if not tasks_info:
                    continue
                list(map(lambda x: x.update({'status': Task.mapstatus2ch(x['status'])}), tasks_info))
                tasks.extend(tasks_info)
                break
        for task in tasks:
            Task.map2resources(task)
        Task.tasks_info = tasks
        Task.tasks_by_node = {node: list(tasks) for node, tasks in groupby(sorted(tasks, key=lambda x: x.get('nodes', '')), lambda x: x.get('nodes', ''))}
        Task.tasks_by_partition = {partition: list(tasks) for partition, tasks in groupby(sorted(tasks, key=lambda x: x['partition']), lambda x: x['partition'])}
        Task.tasks_by_id = {task['slurmJobId']: task for task in tasks}


class Node:
    nodes_info = []
    nodes_dict_info = []
    def __init__(self, node, partion):
        self.partition = partion
        self.node = node
        self.cpu = self.memory = self.card = self.ip = self.active = None
        self._update_info()

    def get_daily_report(self):
        return {
            'node_id': self.node,
            'partition': self.partition.partition_name,
            'status': self.health,
            'reason': self.slurmState,
            # 'duration': self.updated_at - self.created_at,
        }
    
    def get_history(self, history_type, recent_days=30, max_points=2000):
        """
        获取节点历史数据，支持数据库层面的降采样优化
        
        Args:
            history_type: 历史类型 ('CPU', 'Memory', 'GPU')
            recent_days: 最近天数
            max_points: 最大返回数据点数，超过此值会在数据库层面进行降采样
        """
        start_timestampe = time.time()
        if history_type == 'CPU':
            table = TNodeCpuHistoryInfo
            usage_field = 'cpu_usage'
        elif history_type == 'Memory':
            table = TNodeMemHistoryInfo
            usage_field = 'mem_usage'
        elif history_type == 'GPU':
            table = TNodeGpuHistoryInfo
            usage_field = 'gpu_usage'
        else:
            return []
        
        start_time = int((datetime.now() - timedelta(days=recent_days)).timestamp())
        
        with get_db_context_session() as session:
            # data = session.query(table).filter(and_(table.node == self.node, table.timestamp >= start_time)).order_by(table.timestamp.asc()).all()
            try:
                # 合并查询：同时获取数据总量和时间范围（使用ORM方式）
                base_filter = and_(table.node == self.node, table.timestamp >= start_time)
                stats_query = session.query(
                    func.count(table.id).label('total_count'),
                    func.min(table.timestamp).label('min_ts'),
                    func.max(table.timestamp).label('max_ts')
                ).filter(base_filter).first()
                
                if not stats_query:
                    return []
                
                total_count = stats_query.total_count or 0
                
                # 如果数据量超过阈值，使用数据库层面的降采样
                if total_count > max_points and stats_query.min_ts is not None and stats_query.max_ts is not None:
                    min_ts = stats_query.min_ts
                    max_ts = stats_query.max_ts
                    time_span = max_ts - min_ts
                    # 计算采样间隔（秒），确保采样后不超过max_points
                    interval = max(1, int(time_span / max_points))
                    
                    # 使用SQLAlchemy ORM方式实现窗口函数降采样
                    # 这个逻辑的目的是对一段时间内的历史节点数据进行降采样，以数据量不过多、画图平滑为目标。
                    # 主体逻辑：
                    # 1. 使用ROW_NUMBER()窗口函数，给每个采样区间（通过FLOOR((timestamp - min_ts)/interval)分组）内的数据按timestamp升序编号
                    # 2. 只保留每组的第一个点（rn = 1），也就是每个采样区间的起始数据
                    # 3. 按照时间戳升序排序，返回不超过max_points条
                    
                    data = session.execute(
                        # 解释为什么要用子查询：ROW_NUMBER() 是窗口函数，rn 是 select 阶段动态生成的别名，不能直接在同级 WHERE 子句使用，
                        # 因为 WHERE 在 SELECT 之前执行。必须用子查询先选出带 rn 的表，再在外层 where 过滤 rn=1。
                        # 
                        # 关于 limit：如果把 limit 放在子查询里，仅对子查询的原始行数做限制（不是降采样后的数据点，也不是最终的结果），
                        # 这样可能导致采样区间不完整或有遗漏，最终采样点不足 max_points。所以 limit 只能放到最外层，确保拿到足够的降采样点后再截断。
                        text(f"""
                            SELECT timestamp, {usage_field}
                            FROM (
                                SELECT timestamp, {usage_field},
                                    ROW_NUMBER() OVER (
                                        PARTITION BY FLOOR((timestamp - :min_ts) / :interval)
                                        ORDER BY timestamp ASC
                                    ) as rn
                                FROM {table.__tablename__}
                                WHERE node = :node AND timestamp >= :start_time
                            ) sub
                            WHERE rn = 1
                            ORDER BY timestamp ASC
                            LIMIT :limit
                        """),
                        {
                            'node': self.node,
                            'start_time': start_time,
                            'min_ts': min_ts,
                            'interval': interval,
                            'limit': max_points
                        }
                    ).fetchall()
                                            
                    # 转换为字典格式
                    data = [
                        {'timestamp': row[0], usage_field: row[1]}
                        for row in data
                    ]
                                            
                    logger.info(f"get_history {history_type} 数据库降采样: 原始{total_count}条 -> 采样后{len(data)}条, 间隔{interval}秒, 用时：{time.time() - start_timestampe:.3f}s")
                    return data
                # 数据量不大，直接查询全部
                data = session.query(table).filter(
                    and_(table.node == self.node, table.timestamp >= start_time)
                ).order_by(table.timestamp.asc()).all()
                # 转换为字典格式
                data = [
                    {
                        'timestamp': item.timestamp,
                        usage_field: getattr(item, usage_field)
                    }
                    for item in data
                ]
                
                logger.info(f"get_history {history_type} 直接查询: 原始{total_count}条 -> 采样后{len(data)}条, 用时：{time.time() - start_timestampe:.3f}s")
                return data
            except Exception as e:
                logger.error(f"获取节点{self.node}历史信息失败: {e}")
                return []

    def save_cpu_history(self):
        data = api.get_node_cpu_usage(self.node)
        if not data:
            return {}
        try:
            cpu = sorted(reduce(lambda x, y: x + y, map(lambda x: x['values'], data)), key=lambda x: x[0])
        except Exception as e:
            logger.error(f"保存节点{self.node}CPU历史信息失败: {e}")
            return {}
        cpu = {k: list(v) for k, v in groupby(cpu, lambda x: x[0])}
        cpu = {k: sum(map(lambda x: float(x[1]), v)) / len(v) for k, v in cpu.items()}
        cpu = {'data_type': 'CPU', 'data': cpu, 'node': self.node}
        
        return cpu
        # self._save_history_with_dedup(models, TNodeCpuHistoryInfo, 'CPU')

    def save_mem_history(self):
        data = api.get_node_memory_usage(self.node)
        if not data:
            return {}
        mem = sorted(reduce(lambda x, y: x + y, map(lambda x: x['values'], data)), key=lambda x: x[0])
        mem = {k: list(v) for k, v in groupby(mem, lambda x: x[0])}
        mem = {k: sum(map(lambda x: float(x[1]), v)) / len(v) for k, v in mem.items()}
        mem = {'data_type': 'Memory', 'data': mem, 'node': self.node}
        # models = [TNodeMemHistoryInfo(node=self.node, timestamp=k, mem_usage=v) for k, v in mem.items()]
        return mem
        # self._save_history_with_dedup(models, TNodeMemHistoryInfo, '内存')

    def save_gpu_history(self):
        data = api.get_gpu_usage(self.node)
        if not data:
            return {}
        gpu = sorted(reduce(lambda x, y: x + y, map(lambda x: x['values'], data)), key=lambda x: x[0])
        gpu = {k: list(v) for k, v in groupby(gpu, lambda x: x[0])}
        gpu = {k: sum(map(lambda x: float(x[1]), v)) / len(v) for k, v in gpu.items()}
        gpu = {'data_type': 'GPU', 'data': gpu, 'node': self.node}
        # models = [TNodeGpuHistoryInfo(node=self.node, timestamp=k, gpu_usage=v) for k, v in gpu.items()]
        return gpu
        # self._save_history_with_dedup(models, TNodeGpuHistoryInfo, 'GPU')

    def _update_info(self):
        self.gpu_info = api.get_node_gpu_info(self.node)

        nodeComputingResource = Partition.overview['nodeComputingResource'][self.node]
        if not nodeComputingResource:
            logger.error(f"获取节点{self.node}GPU信息失败, 数据为：{Partition.overview['nodeComputingResource']}")
            return
        gpu_key = _extract_gpu_key(nodeComputingResource)
        self.card_type = gpu_key.split(':')[-1]

        self.memory_str = nodeComputingResource['mem']
        self.memory = Unit2int(self.memory_str)
        self.cpu = nodeComputingResource['cpu']
        self.card = nodeComputingResource.get(gpu_key, 0)

        nodeComputingResourceIdled = Partition.overview['nodeComputingResourceIdled'][self.node]
        self.idled_mem_str = nodeComputingResourceIdled['mem']
        self.idled_mem = Unit2int(self.idled_mem_str)
        self.idled_cpu = nodeComputingResourceIdled['cpu']
        self.idled_card = nodeComputingResourceIdled.get(gpu_key, 0)
        
        for node in Node.nodes_dict_info:
            if node['name'] == self.node:
                self.ip = node['ip']
                self.active = node['state'] == 'active'
                self.cabinet = node['cabinet']
                self.slurmState = node['slurmState']
                break       

        self.cpu_util_pct = round((1 - self.idled_cpu / self.cpu) * 100)
        self.mem_util_pct = round((1 - self.idled_mem / self.memory) * 100)
        self.gpu_util_pct = round((1 - self.idled_card / self.card) * 100) if self.card > 0 else 0
        if not self.active:
            self.health = '离线'
        else:
            self.health = '告警' if (self.cpu_util_pct > 85 or self.gpu_util_pct > 85 or self.mem_util_pct > 85) else '健康'

        self.tasks = Task.tasks_by_node.get(self.node, [])  
        for task in self.tasks:
            task['node'] = self.node
            task['partition'] = self.partition.partition_name
        self.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    @staticmethod
    def update_nodes_info():
        for i in range(5):
            nodes_info = api.get_nodes_info()
            if not nodes_info:
                continue
            nodes = []
            for cabinet in nodes_info:
                for node in cabinet['nodes']:
                    node['cabinet'] = cabinet['cabinet']
                    nodes.append(node)
            Node.nodes_dict_info = nodes
            break

class Partition:
    overview = {}

    def __init__(self, partition_name) -> None:
        self.partition_name = partition_name
        self._update_info()
    
    def statistic(self):
        partition = self.partition_name
        if self.card_type:
            partition = f'{self.partition_name}({self.card_type})'
        return {
            'partition': partition,
            'total_jobs': len(list(filter(lambda x: x['status'] == '运行中', self.tasks))),
            'queued_jobs': len(list(filter(lambda x: x['status'] == '排队中', self.tasks))),
            # 'success_rate': round(len(list[Any](filter(lambda x: x['status'] == 'COMPLETED', self.tasks))) / len(self.tasks) * 100, 2),
            'cpu_alloc': f'{self.cpu_util_pct}%',
            'gpu_alloc': f'{self.gpu_util_pct}%' if self.total_card > 0 else '-',
            'mem_alloc': f'{self.mem_util_pct}%',
            'nodes_status': f'{len(list(filter(lambda x: x.active, self.nodes.values())))}/{len(self.nodes)}',
        }

    def _update_info(self): 
        partitionComputingResource = Partition.overview['partitionComputingResource'][self.partition_name]
        gpu_key = _extract_gpu_key(partitionComputingResource)
        self.card_type = gpu_key.split(':')[-1]

        self.total_mem_str = partitionComputingResource['mem']
        self.total_mem = Unit2int(self.total_mem_str)
        self.total_cpu = int(partitionComputingResource['cpu'])
        self.total_card = int(partitionComputingResource.get(gpu_key, 0))

        partitionComputingResourceIdled = Partition.overview['partitionComputingResourceIdled'][self.partition_name]
        self.idled_mem_str = partitionComputingResourceIdled['mem']
        self.idled_mem = Unit2int(self.idled_mem_str)
        self.idled_cpu = partitionComputingResourceIdled['cpu']
        self.idled_card = partitionComputingResourceIdled.get(gpu_key, 0)

        nodes = Partition.overview['partitionNode'][self.partition_name]
        self.nodes = {node: Node(node, self) for node in nodes}
        self.nodes = {key: value for key, value in self.nodes.items() if hasattr(value, 'cpu')}
        self.tasks = Task.tasks_by_partition.get(self.partition_name, [])
        self.updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.cpu_util_pct = round((1 - self.idled_cpu/self.total_cpu)*100)
        self.mem_util_pct = round((1 - self.idled_mem/self.total_mem)*100)
        self.gpu_util_pct = round((1 - self.idled_card/self.total_card)*100) if self.total_card > 0 else 0
        self.is_stressed = self.cpu_util_pct > 85 or self.gpu_util_pct > 85 or self.mem_util_pct > 85

    @staticmethod
    def update_partition_info():
        for i in range(5):
            partition_overview = api.get_overview()
            if not partition_overview:
                continue
            Partition.overview = partition_overview
            break


class HpcManager:
    def __init__(self) -> None:
        self.refresh_info()

    def refresh_info(self):
        Task.update_tasks_info()
        Node.update_nodes_info()
        Partition.update_partition_info()
        self.partitions = {partition: Partition(partition) for partition in Partition.overview['partitionComputingResource'].keys()}
        self.user_total = api.get_user_total()
        Node.nodes_info = reduce(lambda x, y: x + y, [list(node.nodes.values()) for node in self.partitions.values()])
        logger.info(f"刷新信息完成，用户数：{self.user_total['total']}，节点数：{len(Node.nodes_info)}，分区数：{len(self.partitions)}")

    def save_history(self):
        # 使用 with 语句确保线程池正确关闭
        start_time = time.time()    
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有任务（注意：传递函数引用，不要调用函数）
            futures = []
            for node in Node.nodes_info:
                futures.append(executor.submit(node.save_cpu_history))
                futures.append(executor.submit(node.save_mem_history))
                futures.append(executor.submit(node.save_gpu_history))
            
            # 等待所有任务完成
            wait(futures, return_when=ALL_COMPLETED)
            
            # 收集结果并过滤空字典
            results = []
            for future in futures:
                try:
                    result = future.result()
                    if result and isinstance(result, dict) and result.get('data'):
                        results.append(result)
                except Exception as e:
                    logger.error(f"获取历史信息结果失败: {e}")
        
        # 按 data_type 分组并转换为模型对象
        cpu_models = []
        mem_models = []
        gpu_models = []
        
        for result in results:
            data_type = result.get('data_type')
            node_name = result.get('node')
            data = result.get('data', {})
            
            if data_type == 'CPU':
                cpu_models.extend([
                    TNodeCpuHistoryInfo(node=node_name, timestamp=k, cpu_usage=v)
                    for k, v in data.items()
                ])
            elif data_type == 'Memory':
                mem_models.extend([
                    TNodeMemHistoryInfo(node=node_name, timestamp=k, mem_usage=v)
                    for k, v in data.items()
                ])
            elif data_type == 'GPU':
                gpu_models.extend([
                    TNodeGpuHistoryInfo(node=node_name, timestamp=k, gpu_usage=v)
                    for k, v in data.items()
                ])
        
        # 批量保存到数据库
        if cpu_models:
            self._save_history_with_dedup(cpu_models, TNodeCpuHistoryInfo)
        if mem_models:
            self._save_history_with_dedup(mem_models, TNodeMemHistoryInfo)
        if gpu_models:
            self._save_history_with_dedup(gpu_models, TNodeGpuHistoryInfo)
        end_time = time.time()
        logger.info(f"保存历史信息完成，CPU：{len(cpu_models)}，内存：{len(mem_models)}，GPU：{len(gpu_models)}，耗时：{round(end_time - start_time, 2)}秒")


    def _save_history_with_dedup(self, models, model_class):
        """
        批量保存历史记录，自动过滤重复的(node, timestamp)组合（跳过重复记录）
        
        使用 MySQL 的 INSERT IGNORE 优化性能，避免先查询再插入的两步操作
        
        Args:
            models: 要保存的模型对象列表
            model_class: 模型类（TNodeCpuHistoryInfo/TNodeMemHistoryInfo/TNodeGpuHistoryInfo）
            history_type: 历史类型名称（用于日志），如'CPU'、'内存'、'GPU'
        """
        start_time = time.time()
        if not models:
            return
        
        # 确定字段名
        if model_class == TNodeCpuHistoryInfo:
            usage_field = 'cpu_usage'
            history_type = 'CPU'
        elif model_class == TNodeMemHistoryInfo:
            usage_field = 'mem_usage'
            history_type = '内存'
        elif model_class == TNodeGpuHistoryInfo:
            usage_field = 'gpu_usage'
            history_type = 'GPU'
        else:
            return
        
        # 转换为字典列表，用于批量插入
        data_list = [
            {
                'node': m.node,
                'timestamp': m.timestamp,
                usage_field: getattr(m, usage_field)
            }
            for m in models
        ]
        
        # 使用 MySQL 的 INSERT IGNORE，让数据库自动忽略重复键，完全避免查询步骤
        with get_db_context_session() as session:
            # 分批插入，每批1000条，平衡性能和内存
            batch_size = 1000
            total_inserted = 0
            
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i + batch_size]
                
                try:
                    # 使用 SQLAlchemy 的 insert().prefix_with('IGNORE') 方式
                    # 代码更简洁可读，且自动处理参数化查询，防止SQL注入
                    stmt = insert(model_class).prefix_with('IGNORE').values(batch)
                    session.execute(stmt)
                    session.commit()
                    # INSERT IGNORE 不会抛出异常，会静默跳过重复记录
                    # 注意：MySQL 的 INSERT IGNORE 不返回实际插入的行数
                    # 这里使用批次大小作为估算值
                    total_inserted += len(batch)
                except Exception as e:
                    session.rollback()
                    logger.error(f"批量插入{history_type}历史信息失败: {e}")
                    # 如果批量插入失败，回退到 bulk_insert_mappings（会抛出 IntegrityError）
                    try:
                        session.bulk_insert_mappings(model_class, batch, render_nulls=True)
                        session.commit()
                        total_inserted += len(batch)
                    except IntegrityError:
                        # 如果还是遇到重复键错误，说明数据有问题，记录日志但继续
                        session.rollback()
                        logger.warning(f"{history_type}历史信息批次中存在重复记录，已跳过")
                        # 尝试逐条插入以获取更准确的计数
                        for item in batch:
                            try:
                                session.bulk_insert_mappings(model_class, [item], render_nulls=True)
                                session.commit()
                                total_inserted += 1
                            except IntegrityError:
                                session.rollback()
                                # 忽略重复键错误
                                continue
                            except Exception as e2:
                                session.rollback()
                                logger.error(f"插入单条{history_type}历史信息失败: {e2}")
        
        skipped_count = len(models) - total_inserted
        end_time = time.time()
        logger.info(f"保存历史信息完成，{history_type}：{total_inserted}条（跳过{skipped_count}条重复记录），耗时：{round(end_time - start_time, 2)}秒")
    
    def daily_statistic(self):
        today = datetime.now().strftime('%Y-%m-%d')
        with get_db_context_session() as session:
            daily_report = session.query(TDailyReportInfo).filter(TDailyReportInfo.date == today).first()
            if not daily_report:
                partition_info = list(map(lambda x: x.statistic(), 
                    self.partitions.values()))
                exception_nodes = list(map(lambda x: x.get_daily_report(), 
                    filter(lambda x: not x.active, Node.nodes_info)))
                queuing_jobs = list(map(lambda x: Task(x['slurmJobId']).get_daily_report(), 
                    filter(lambda x: x['status'] == '排队中', Task.tasks_info)))
                daily_report = TDailyReportInfo(
                    date=today, 
                    partition_info=partition_info,
                    total_users=self.total_user,
                    online_users=self.user_active,
                    exception_nodes=exception_nodes,
                    queuing_jobs=queuing_jobs,
                )
                session.add(daily_report)
                session.commit()
    
    def get_daily_report_days(self):
        with get_db_context_session() as session:
            days = session.query(TDailyReportInfo.date).order_by(TDailyReportInfo.date.desc()).limit(180).all()
        return [x[0] for x in days]

    def get_daily_statistic(self, date):
        with get_db_context_session() as session:
            daily_report = session.query(TDailyReportInfo).filter(TDailyReportInfo.date == date).first()
            if not daily_report:
                return {}
        return daily_report.to_dict()

    @property
    def total_user(self):
        return self.user_total['total']

    @property
    def user_active(self):
        return self.user_total['active']

    @property
    def partition(self):
        return self.partitions

hpc_manager = HpcManager()
