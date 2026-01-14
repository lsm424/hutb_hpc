'''
Author: wadesmli
Date: 2024-08-13 14:59:59
LastEditTime: 2024-08-27 19:17:18
Description: 
'''
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from common import cfg
from sqlalchemy import Column, MetaData, create_engine, func, text, DateTime
from sqlalchemy.ext.asyncio import create_async_engine
from datetime import datetime

Base = declarative_base()

def to_dict(self):
    if not hasattr(self, 'serialize_only'):
        self.serialize_only = list(map(lambda x: x.name, self.__table__.columns))
    ret = {c: getattr(self, c, None) for c in self.serialize_only}
    for k, v in ret.items():
        if isinstance(v, datetime):
            ret[k] = v.strftime('%Y-%m-%d %H:%M:%S')
    return ret

Base.to_dict = to_dict
engine = create_engine(cfg.get('mysql', 'dsn'), 
                      echo=False, 
                      pool_size=100,        # 增加基础连接池大小
                      max_overflow=200,     # 增加溢出连接数
                      pool_recycle=1800,    # 30分钟回收连接
                      pool_pre_ping=True,
                      pool_timeout=30,      # 连接获取超时
                      connect_args={
                          "connect_timeout": 10,
                          "read_timeout": 30,
                          "write_timeout": 30,
                          "charset": "utf8mb4",
                          "autocommit": True,  # 自动提交
                          "sql_mode": "TRADITIONAL"
                      })

metadata = MetaData(bind=engine)

async_engine = create_async_engine(cfg.get('mysql', 'dsn').replace('pymysql', 'aiomysql'),
                                   echo=False,
                                   max_overflow=200,     # 增加溢出连接数
                                   pool_size=100,       # 增加基础连接池大小
                                   pool_recycle=1800,   # 30分钟回收连接
                                   pool_pre_ping=True,
                                   pool_timeout=30,     # 连接获取超时
                                   connect_args={
                                       "connect_timeout": 10,
                                       "charset": "utf8mb4",
                                       "autocommit": True,  # 自动提交
                                       "sql_mode": "TRADITIONAL"
                                   })
async_metadata = MetaData(bind=async_engine)


class TimestampMixin:
    create_time = Column(DateTime, nullable=False, default=datetime.now, server_default=func.now(), comment='创建时间')
    update_time = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='更新时间')
    delete_time = Column(DateTime, nullable=False, server_default=func.now(), comment='删除时间')
