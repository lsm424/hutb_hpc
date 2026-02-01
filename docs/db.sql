
create table t_node_cpu_history_info (
    `id` int(11) not null auto_increment,
    `node` varchar(255) not null default '' comment '节点名称',
    `timestamp` int(11) not null comment '时间戳',
    `cpu_usage` float not null,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    primary key (`id`),
    INDEX node_idx (node),
    UNIQUE (node, timestamp),
    INDEX timestamp_idx (timestamp),
    INDEX node_timestamp_idx (node, timestamp)
) COMMENT='节点CPU历史信息表';

create table t_node_mem_history_info (
    `id` int(11) not null auto_increment,
    `node` varchar(255) not null default '' comment '节点名称',
    `timestamp` int(11) not null comment '时间戳',
    `mem_usage` float not null,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    primary key (`id`),
    INDEX node_idx (node),
    UNIQUE (node, timestamp),
    INDEX timestamp_idx (timestamp),
    INDEX node_timestamp_idx (node, timestamp)
) COMMENT='节点内存历史信息表';

create table t_node_gpu_history_info (
    `id` int(11) not null auto_increment,
    `node` varchar(255) not null default '' comment '节点名称',
    `timestamp` int(11) not null comment '时间戳',
    `gpu_usage` float not null,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    primary key (`id`),
    INDEX node_idx (node),
    UNIQUE (node, timestamp),
    INDEX timestamp_idx (timestamp),
    INDEX node_timestamp_idx (node, timestamp)
) COMMENT='节点GPU历史信息表';

create table t_daily_report_info (
    `id` int(11) not null auto_increment,
    `date` varchar(64) not null comment '日期',
    `total_users` int(11) not null comment '总用户数',
    `online_users` int(11) not null comment '在线用户数',
    `exception_nodes` json comment '异常节点列表',
    `queuing_jobs` json comment '排队中的任务',
    `partition_info` json comment '分区信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    primary key (`id`),
    unique key (date)
) comment='日报';

-- 为现有表添加联合索引优化查询性能（如果表已存在，单独执行以下语句）
-- ALTER TABLE t_node_cpu_history_info ADD INDEX node_timestamp_idx (node, timestamp);
-- ALTER TABLE t_node_mem_history_info ADD INDEX node_timestamp_idx (node, timestamp);
-- ALTER TABLE t_node_gpu_history_info ADD INDEX node_timestamp_idx (node, timestamp);

-- 覆盖索引：降采样查询只读 (node, timestamp, usage)，无需回表，显著减少 IO（约 25 万行时效果明显）
-- 若已有 node_timestamp_idx，可先 DROP 再建覆盖索引，或直接新增以下索引（查询会优先选用覆盖索引）
-- ALTER TABLE t_node_cpu_history_info ADD INDEX node_ts_cpu_idx (node, timestamp, cpu_usage);
-- ALTER TABLE t_node_mem_history_info ADD INDEX node_ts_mem_idx (node, timestamp, mem_usage);
-- ALTER TABLE t_node_gpu_history_info ADD INDEX node_ts_gpu_idx (node, timestamp, gpu_usage);

create table t_hpc_user_info (
    id int(11) not null auto_increment,
    hpc_id varchar(255) not null default '' comment 'HPC ID',
    username varchar(255) not null default '' comment '用户名',
    realname varchar(255) not null default '' comment '真实姓名',
    email varchar(255) not null default '' comment '邮箱',
    phone varchar(255) not null default '' comment '电话',
    role_name varchar(1024) not null default '' comment '角色名称',
    register_time TIMESTAMP not null comment '注册时间',
    status varchar(255) not null default '0' comment '状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    primary key (`id`),
    unique key (username)
) COMMENT='HPC用户信息表';


set @start = 1769247047;
set @step = 3600;
set @node='xcn1';

SELECT
	@start + bucket_idx * @step AS time_bucket,
	avg_val
FROM
	(
	SELECT (timestamp - @start) DIV @step AS bucket_idx, SUBSTRING_INDEX(GROUP_CONCAT(cpu_usage ORDER BY timestamp ASC), ',', 1) AS avg_val
	FROM t_node_cpu_history_info FORCE INDEX (node_ts_cpu_idx)
	WHERE node = @node  
	GROUP BY (timestamp - @start) DIV @step ) t
ORDER BY
	time_bucket;

