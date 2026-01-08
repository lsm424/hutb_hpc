from infra.hpc_api import HpcApi
from common import cfg
from threading import Lock
from itertools import groupby

api = HpcApi(cfg.get('account', 'user'), cfg.get('account', 'passwd'), cfg.get('account', 'signature'))


        

def _extract_gpu_key(info: dict):
    for key in info.keys():
        if ':' in key:
            return key
    return ''

class Task:
    tasks_info = []
    tasks_by_node = {}
    tasks_by_partition = {}

    def __init__(self, task_id):
        pass

    @staticmethod
    def update_tasks_info():
        tasks = []
        for status in [api.StatusRunning, api.StatusPending]:
            for i in range(5):
                tasks_info = api.get_tasks()
                if not tasks_info:
                    continue
                tasks.extend(tasks_info)
                break
        Task.tasks_info = tasks
        Task.tasks_by_node = {node: list(tasks) for node, tasks in groupby(tasks, lambda x: x.get('nodes', ''))}
        Task.tasks_by_partition = {partition: list(tasks) for partition, tasks in groupby(tasks, lambda x: x['partition'])}

class Node:
    nodes_info = []

    def __init__(self, node, partion):
        self.partition = partion
        self.node = node
        self.cpu = self.memory = self.card = self.ip = self.active = None
        self._update_info()

    def _update_info(self):
        nodeComputingResource = Partition.overview['nodeComputingResource'][self.node]
        gpu_key = _extract_gpu_key(nodeComputingResource)
        self.card_type = gpu_key.split(':')[-1]

        self.cpu = nodeComputingResource['cpu']
        self.memory = nodeComputingResource['mem']
        self.card = nodeComputingResource.get(gpu_key, 0)

        nodeComputingResourceIdled = Partition.overview['nodeComputingResourceIdled'][self.node]
        self.idled_mem = nodeComputingResourceIdled['mem']
        self.idled_cpu = nodeComputingResourceIdled['cpu']
        self.idled_card = nodeComputingResourceIdled.get(gpu_key, 0)
        
        for cabinet in Node.nodes_info:
            for node in cabinet['nodes']:
                if node['name'] == self.node:
                    self.ip = node['ip']
                    self.active = node['state'] == 'active'
                    self.cabinet = cabinet['cabinet']
                    break       

        self.tasks = Task.tasks_by_node.get(self.node, [])  

    @staticmethod
    def update_nodes_info():
        for i in range(5):
            nodes_info = api.get_nodes_info()
            if not nodes_info:
                continue
            Node.nodes_info = nodes_info
            break

class Partition:
    overview = {}

    def __init__(self, partition_name) -> None:
        self.partition_name = partition_name
        self._update_info()

    def _update_info(self): 
        partitionComputingResource = Partition.overview['partitionComputingResource'][self.partition_name]
        gpu_key = _extract_gpu_key(partitionComputingResource)
        self.card_type = gpu_key.split(':')[-1]

        self.total_mem = partitionComputingResource['mem']
        self.total_cpu = partitionComputingResource['cpu']
        self.total_card = partitionComputingResource.get(gpu_key, 0)

        partitionComputingResourceIdled = Partition.overview['partitionComputingResourceIdled'][self.partition_name]
        self.idled_mem = partitionComputingResourceIdled['mem']
        self.idled_cpu = partitionComputingResourceIdled['cpu']
        self.idled_card = partitionComputingResourceIdled.get(gpu_key, 0)

        nodes = Partition.overview['partitionNode'][self.partition_name]
        self.nodes = {node: Node(node, self) for node in nodes}
        self.tasks = Task.tasks_by_partition.get(self.partition_name, [])

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
