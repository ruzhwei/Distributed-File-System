#!/usr/bin/env python
#coding:utf-8

import random
import rstr
import yaml
import socket

# 生成日志
# 一部分日志是已知的，另一部分日志是随机的
def gen_testlog():
    with open('conf.yaml') as f:
        test_conf = yaml.safe_load(f)['test']
    total_size = test_conf['size']
    size_dict = {t : int(total_size * float(f)) for t, f in test_conf['frequency'].iteritems()}
    # 本机的编号 id
    # 根据本机 ip 地址获取本机编号 id
    # 获取本机 ip 地址
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('8.8.8.8', 0))
    ip_address =sock.getsockname()[0]
    with open('conf.yaml') as f:
        server_list = yaml.safe_load(f)['server_list']
    for s in server_list:
        if s['ip'] == ip_address:
            local_id=s['id']
 
    
    # 用 '' 来占位，初始化 log_list
    log_list = ['' for i in xrange(total_size)]
 
    # 仅为当前服务器生成一行日志
    random_index = int(random.random() * total_size)
    log_list[random_index] = 'server %d' % local_id

    # 为 conf 中的特定服务器（hit_servers）生成一行日志
    if local_id in test_conf['hit_servers']:
        random_index = int(random.random() * total_size)
        # 检测该行是否已经存在
        while log_list[random_index]:
            random_index = int(random.random() * total_size)
        log_list[random_index] = 'hit_server'

    # 为所有的服务器生成一行日志
    random_index = int(random.random() * total_size)
    # 检测该行是否已经存在
    while log_list[random_index]:
        random_index = int(random.random() * total_size)
    log_list[random_index] = 'all_server'

    # 根据格式的不同频率生成日志
    for pattern, frequency in size_dict.iteritems():
        count = 0
        while count < frequency:
            random_index = int(random.random() * total_size)
            while log_list[random_index]:
                random_index = int(random.random() * total_size)
            # 通过反转正则表达式生成日志
            log_list[random_index] = rstr.xeger(test_conf['pattern'][pattern])
            count += 1

    # 随机生成剩下的日志
    for i in xrange(total_size):
        if not log_list[i]:
            log_list[i] = rstr.xeger(test_conf['pattern']['random']) 

    # 写入文件当中
    with open('%svm%d.log' % (test_conf['log_path'], local_id), 'w') as f:
        for i in xrange(total_size):
            f.write(log_list[i] + '\n')
         
if __name__ == '__main__':
    gen_testlog()
