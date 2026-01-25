import base64
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import struct
import requests
import time
from common import logger, cfg
import threading
import os


def check_login(func):
    def wrapper(self, *args, **kwargs):
        r = func(self, *args, **kwargs)
        if not r:
            return r
        if isinstance(r, dict) and r.get('code', '') == 401:
            with self.lock:
                r = func(self, *args, **kwargs)
                if isinstance(r, dict) and r.get('code', '') == 401:
                    self.login()
                    r = func(self, *args, **kwargs)
                    # logger.warning(f'ticket {self.ticket} 失效')
        return r
    return wrapper

class HpcApi:
    StatusRunning = 'isRunning'
    StatusPending = 'isPending'
    StatusCompleted = 'isFinishedOnlySuccessed'
    StatusFailed = 'isError'
    StatusCancelled = 'isCancelled'

    def __init__(self, username, passwd, signature) -> None:
        self.username = username
        self.passwd = passwd
        self.signature = signature
        self.session = requests.Session()
        if os.path.exists('assets/token.txt'):
            token = open('assets/token.txt', 'r').read().strip()
            self.session.headers['Cookie'] = f'X-Access-Token={token}'
        self.lock = threading.Lock()


    def login(self) -> bool:
        try:
            body = {
                "username": self.username,
                "password": self.passwd,
                "signature": self.signature,
                "captcha": "",
                "checkKey": int(time.time() * 1000)
            }
            response = self.session.post("http://hpc.hutb.edu.cn/hpc-backend/sys/encryptLogin", json=body, verify=False)
            if response.status_code != 200:
                logger.error(f"登录失败，状态码：{response.status_code}，响应内容：{response.text}")
            with open('assets/token.txt', 'w+') as f:
                token = response.json()['result']['token']
                self.session.headers['Cookie'] = f'X-Access-Token={token}'
                f.write(token)
        except Exception as e:
            logger.error(f"登录请求异常：{e}")
            
    @check_login
    def get_overview(self) -> dict:
        url = f'http://hpc.hutb.edu.cn/hpc-backend/qos/compositeComputingResourceRelation?_t={int(time.time() * 1000)}'
        data = self.session.get(url).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPCOverview失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_nodes_info(self) -> dict:
        '''主要用于获得节点的ip地址，是否可用'''
        url = 'http://hpc.hutb.edu.cn/hpc-backend/realtime-monitoring/deployment?_t=1767923755865'
        data = self.session.get(url).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC节点信息失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_user_total(self) -> dict:
        url = f'http://hpc.hutb.edu.cn/hpc-backend/sys/user/activeStatistics?_t={int(time.time() * 1000)}'
        data = self.session.get(url).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPCUserTotal失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_tasks(self, status=None, partition=None, createBy=None, task_name=None, startTime=None, endTime=None, page_no=1, pagesize=1000) -> dict:
        url = 'http://hpc.hutb.edu.cn/hpc-backend/task/pageList'
        
        params = {
            'column': 'startTime',
            'order': 'desc',
            'pageNo': page_no,
            'pageSize': pagesize,
            'status': '',
            'all': 'true',
            'timeColumn': 'startTime',
            '_t': int(time.time() * 1000),
        }
        if status:
            params[status] = True
        if partition:
            params['partition'] = partition
        if createBy:
            params['createBy'] = createBy
        if task_name:
            params['name'] = task_name
        if startTime:
            params['startTime'] = startTime
        if endTime:
            params['endTime'] = endTime

        data = self.session.get(url, params=params).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC任务失败，参数：{params}，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']['records']

    @check_login
    def get_user_list(self, username=None, realname=None, page_no=1, pagesize=10) -> dict:
        url = 'http://hpc.hutb.edu.cn/hpc-backend/sys/user/listAll'
        params = {
            'column': 'createTime',
            'order': 'desc',
            'pageNo': page_no,
            'pageSize': pagesize,
            'username': username,
            'realname': realname,
            '_t': int(time.time() * 1000),
        }

        data = self.session.get(url, params=params).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC用户列表失败，参数：{params}，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_node_cpu_usage(self, node_name=None) -> dict:
        url = 'http://hpc.hutb.edu.cn/hpc-backend/realtime-monitoring/cpuUsage'
        body = {
        "node": node_name
        }

        data = self.session.post(url, json=body).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC节点{node_name}CPU占用失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_node_memory_usage(self, node_name=None) -> dict:
        url = 'http://hpc.hutb.edu.cn/hpc-backend/realtime-monitoring/memoryUsage'
        body = {
            "node": node_name
        }

        data = self.session.post(url, json=body).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC节点{node_name}内存占用失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_node_gpu_info(self, node_name=None) -> dict:
        url = f'http://hpc.hutb.edu.cn/hpc-backend/monitoring/card/metrics?node={node_name}&_t={int(time.time() * 1000)}'
        data = self.session.get(url).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC节点{node_name}显卡信息失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_gpu_usage(self, node_name=None) -> dict:
        '''获得节点所有显卡的使用率'''
        url = f'http://hpc.hutb.edu.cn/hpc-backend/monitoring/card/usageTrend?node={node_name}&_t={int(time.time() * 1000)}'
        data = self.session.get(url).json()
        if data.get('code', '') != 200:
            logger.error(f"获取HPC节点{node_name}显卡使用率失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']

    @check_login
    def get_all_users(self, page_no=1, pagesize=1000, username=None) -> list[dict]:
        url = f'http://hpc.hutb.edu.cn/hpc-backend/sys/user/listAll?column=createTime&order=desc&pageNo={page_no}&pageSize={pagesize}&_t={int(time.time() * 1000)}'
        if username:
            url += f'&username={username}'
        data = self.session.get(url).json()
        if data.get('code', '') != 0:
            logger.error(f"获取HPC所有用户失败，状态码：{data.get('code', '')}，响应内容：{data}")
            return data
        return data['result']['records']

    # 简化版本，直接使用UTF-8编码的字节作为密钥和IV
    def _encrypt_username_simple(self, username):
        """
        简化版本：直接使用UTF-8编码的字符串作为密钥和IV
        """
        # 密钥和IV
        key = "akamario@funsine".encode('utf-8')[:16].ljust(16, b'\x00')
        iv = "funsine@akamario".encode('utf-8')[:16].ljust(16, b'\x00')

        # 要加密的数据
        data = username.encode('utf-8')

        # PKCS7填充
        data_padded = pad(data, AES.block_size, style='pkcs7')

        # AES-128-CBC加密
        cipher = AES.new(key, AES.MODE_CBC, iv)
        encrypted_data = cipher.encrypt(data_padded)

        # Base64编码
        return base64.b64encode(encrypted_data).decode('utf-8')

api = HpcApi(cfg.get('account', 'user'), cfg.get('account', 'passwd'), cfg.get('account', 'signature'))
