# coding: utf-8
from sqlalchemy import Column, Enum, Float, ForeignKey, Integer, JSON, String, TIMESTAMP, Text, text, BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from models.base import Base

metadata = Base.metadata


class TDailyReportInfo(Base):
    __tablename__ = 't_daily_report_info'
    __table_args__ = {'comment': '日报表'}
    serialize_only = ('id', 'date', 'total_users', 'online_users', 'exception_nodes', 'queuing_jobs', 'partition_info', 'created_at', 'updated_at')
    id = Column(Integer, primary_key=True)
    date = Column(String(64), nullable=False, server_default=text("''"), comment='日期')
    total_users = Column(Integer, nullable=False, server_default=text("'0'"), comment='总用户数')
    online_users = Column(Integer, nullable=False, server_default=text("'0'"), comment='在线用户数')
    exception_nodes = Column(JSON, nullable=False, server_default=text("'[]'"), comment='异常节点列表')
    queuing_jobs = Column(JSON, nullable=False, server_default=text("'[]'"), comment='排队中的任务')
    partition_info = Column(JSON, nullable=False, server_default=text("'[]'"), comment='分区信息')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment='更新时间')


class TNodeGpuHistoryInfo(Base):
    __tablename__ = 't_node_gpu_history_info'
    __table_args__ = {'comment': '节点GPU历史信息表'}
    serialize_only = ('id', 'node', 'timestamp', 'gpu_usage', 'created_at', 'updated_at')
    id = Column(Integer, primary_key=True)
    node = Column(String(255), nullable=False, server_default=text("''"), comment='节点名称')
    timestamp = Column(Integer, nullable=False, server_default=text("'0'"), comment='时间戳')
    gpu_usage = Column(Float, nullable=False, server_default=text("'0'"), comment='GPU使用率')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment='更新时间')


class TNodeMemHistoryInfo(Base):
    __tablename__ = 't_node_mem_history_info'
    __table_args__ = {'comment': '节点内存历史信息表'}
    serialize_only = ('id', 'node', 'timestamp', 'mem_usage', 'created_at', 'updated_at')
    id = Column(Integer, primary_key=True)
    node = Column(String(255), nullable=False, server_default=text("''"), comment='节点名称')
    timestamp = Column(Integer, nullable=False, server_default=text("'0'"), comment='时间戳')
    mem_usage = Column(Float, nullable=False, server_default=text("'0'"), comment='内存使用率')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment='更新时间')


class TNodeCpuHistoryInfo(Base):
    __tablename__ = 't_node_cpu_history_info'
    __table_args__ = {'comment': '节点CPU历史信息表'}
    serialize_only = ('id', 'node', 'timestamp', 'cpu_usage', 'created_at', 'updated_at')
    id = Column(Integer, primary_key=True)
    node = Column(String(255), nullable=False, server_default=text("''"), comment='节点名称')
    timestamp = Column(Integer, nullable=False, server_default=text("'0'"), comment='时间戳')
    cpu_usage = Column(Float, nullable=False, server_default=text("'0'"), comment='CPU使用率')
    created_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment='创建时间')
    updated_at = Column(TIMESTAMP, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"), comment='更新时间')