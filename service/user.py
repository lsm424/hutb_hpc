from models.model import THpcUserInfo
from models import get_db_context_session
import time
from infra.hpc_api import api
from sqlalchemy import insert, or_
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
        all_users = list(map(lambda x: {
            'hpc_id': x['id'],
            'username': x['username'],
            'realname': x['realname'],
            'email': x['email'],
            'phone': x['phone'],
            'role_name': ','.join(x['roleNameList']),
            'register_time': x['createTime'],
            'status': x['status_dictText'],
        }, all_users))
        with get_db_context_session() as session:
            stmt = insert(THpcUserInfo).prefix_with('IGNORE').values(all_users)
            session.execute(stmt)
            session.commit()
        end = time.time()
        logger.info(f"更新所有用户完成，耗时：{end - start}秒, 用户数：{len(all_users)}")
        if status:
            all_users = list(filter(lambda x: x['status'] == status, all_users))
        return all_users


user_service = User()