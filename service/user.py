import concurrent.futures
from models.model import THpcUserInfo
from models import get_db_context_session
import time
from infra.hpc_api import api
from sqlalchemy import insert, or_, update
from common import logger

class User:
    def __init__(self):
        pass

    def get_and_update_users(self, username=None, status=None, role=None):
        '''
        获取并更新用户信息
        :param username: 用户名，如果为None，则更新所有用户并返回，如果为空字符串，则获取所有用户，否则获取指定用户
        :return: 用户信息列表
        '''
        if username is not None or status is not None or role is not None:
            with get_db_context_session() as session:
                users = session.query(THpcUserInfo)
                if username:
                    users = users.filter(or_(THpcUserInfo.username.like(f'%{username}%'), 
                        THpcUserInfo.realname.like(f'%{username}%')))
                if status:
                    users = users.filter(THpcUserInfo.status == status)
                if role:
                    users = users.filter(THpcUserInfo.role_name.like(f'%{role}%'))
                users = users.all()
                if users:
                    return list(map(lambda x: x.to_dict(), users))

        start = time.time()
        all_users = api.get_all_users(username=username)
        with concurrent.futures.ThreadPoolExecutor() as executor:
            recent_login_dates = list(executor.map(api.recent_login_date, [x['username'] for x in all_users]))
            login_time = {x[0]: x[1] for x in recent_login_dates}
        
        all_users = list(map(lambda x: {
            'hpc_id': x['id'],
            'username': x['username'],
            'realname': x['realname'] or '',
            'email': x['email'] or '',
            'phone': x['phone'] or '',
            'role_name': ','.join(x['roleNameList']) if x.get('roleNameList') else '',
            'register_time': x['createTime'],
            'status': x['status_dictText'] or '',
            'recent_login_time': login_time.get(x['username'], None)
        }, all_users))
        with get_db_context_session() as session:
            # 使用 INSERT ... ON DUPLICATE KEY UPDATE 实现存在则更新，不存在则插入
            from sqlalchemy.dialects.mysql import insert as mysql_insert
            stmt = mysql_insert(THpcUserInfo).values(all_users)
            update_dict = {
                'hpc_id': stmt.inserted.hpc_id,
                'realname': stmt.inserted.realname,
                'email': stmt.inserted.email,
                'phone': stmt.inserted.phone,
                'role_name': stmt.inserted.role_name,
                'status': stmt.inserted.status,
                'register_time': stmt.inserted.register_time,
                'recent_login_time': stmt.inserted.recent_login_time,
            }
            stmt = stmt.on_duplicate_key_update(**update_dict)
            session.execute(stmt)
            session.commit()
        end = time.time()
        logger.info(f"更新所有用户完成，耗时：{end - start}秒, 用户数：{len(all_users)}")
        if status:
            all_users = list(filter(lambda x: x['status'] == status, all_users))
        return all_users


user_service = User()