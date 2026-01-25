from apscheduler.schedulers.background import BackgroundScheduler
from service.hpc_manager import hpc_manager
from service.user import user_service
from datetime import datetime, timedelta
from common import logger

scheduler = BackgroundScheduler()
scheduler.add_job(hpc_manager.refresh_info, 'interval', seconds=20, 
            max_instances=1, id='refresh_info')
scheduler.add_job(hpc_manager.save_history, 'interval', seconds=450,
            max_instances=1, id='save_history', next_run_time=datetime.now() + timedelta(seconds=1))
scheduler.add_job(hpc_manager.daily_statistic, 'cron', hour=23, minute=59, 
            max_instances=1, id='daily_statistic')
scheduler.add_job(user_service.get_and_update_users, 'interval', seconds=3600, 
            max_instances=1, id='update_all_users', next_run_time=datetime.now())

scheduler.start()
logger.info(f"定时任务启动完成")


