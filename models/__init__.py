from .base import Base, engine, metadata, async_engine
from contextlib import contextmanager, asynccontextmanager
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError, DisconnectionError, TimeoutError
import asyncio
import time
from common import logger
# t = Table(AdminUser.__tablename__, metadata, autoload=True)

Base.metadata.create_all(engine, checkfirst=True)


def get_db_session(engine):
    DbSession = sessionmaker()
    DbSession.configure(bind=engine)
    return DbSession()


@contextmanager
def get_db_context_session(transaction=False, engine=engine):
    session = get_db_session(engine)

    if transaction:
        try:
            session.begin()
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()
    else:
        try:
            yield session
        except:
            raise
        finally:
            session.close()


# 创建全局异步会话工厂
async_session_factory = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


def log_pool_status():
    """记录连接池状态"""
    try:
        # 同步连接池状态
        sync_pool = engine.pool
        logger.info(f"同步连接池状态 - 大小: {sync_pool.size()}, 已检查: {sync_pool.checkedin()}, 已检出: {sync_pool.checkedout()}, 溢出: {sync_pool.overflow()}")
        
        # 异步连接池状态
        async_pool = async_engine.pool
        logger.info(f"异步连接池状态 - 大小: {async_pool.size()}, 已检查: {async_pool.checkedin()}, 已检出: {async_pool.checkedout()}, 溢出: {async_pool.overflow()}")
        
        # 计算连接池使用率
        total_sync = sync_pool.size() + sync_pool.overflow()
        used_sync = sync_pool.checkedout()
        sync_usage = (used_sync / total_sync * 100) if total_sync > 0 else 0
        
        total_async = async_pool.size() + async_pool.overflow()
        used_async = async_pool.checkedout()
        async_usage = (used_async / total_async * 100) if total_async > 0 else 0
        
        logger.info(f"连接池使用率 - 同步: {sync_usage:.1f}%, 异步: {async_usage:.1f}%")
        
    except Exception as e:
        logger.warning(f"无法获取连接池状态: {e}")


def get_pool_status():
    """获取连接池状态字典"""
    try:
        sync_pool = engine.pool
        async_pool = async_engine.pool
        
        return {
            'sync_pool': {
                'size': sync_pool.size(),
                'checkedin': sync_pool.checkedin(),
                'checkedout': sync_pool.checkedout(),
                'overflow': sync_pool.overflow(),
                'usage_percent': (sync_pool.checkedout() / (sync_pool.size() + sync_pool.overflow()) * 100) if (sync_pool.size() + sync_pool.overflow()) > 0 else 0
            },
            'async_pool': {
                'size': async_pool.size(),
                'checkedin': async_pool.checkedin(),
                'checkedout': async_pool.checkedout(),
                'overflow': async_pool.overflow(),
                'usage_percent': (async_pool.checkedout() / (async_pool.size() + async_pool.overflow()) * 100) if (async_pool.size() + async_pool.overflow()) > 0 else 0
            }
        }
    except Exception as e:
        logger.warning(f"无法获取连接池状态: {e}")
        return None


@asynccontextmanager
async def async_db_session_with_retry(max_retries=3, retry_delay=1):
    """带重试机制的异步数据库会话"""
    for attempt in range(max_retries):
        try:
            # 记录连接池状态
            if attempt > 0:
                log_pool_status()
                
            async with async_session_factory() as session:
                yield session
                return
        except (OperationalError, DisconnectionError, TimeoutError) as e:
            logger.warning(f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                # 指数退避，但限制最大等待时间
                wait_time = min(retry_delay * (2 ** attempt), 10)
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"数据库连接重试失败，已达到最大重试次数: {e}")
                log_pool_status()
                raise
        except Exception as e:
            logger.error(f"数据库连接出现未知错误: {e}")
            log_pool_status()
            raise


def async_db_session(async_engine=async_engine):
    """保持向后兼容的异步会话函数"""
    return async_session_factory()


@asynccontextmanager
async def async_session_scope(commit=False):
    """创建一个上下文管理器用于异步会话的管理"""
    async with async_db_session_with_retry() as session:
        async with session.begin():
            yield session
            if commit:
                # 提交事务
                await session.commit()
