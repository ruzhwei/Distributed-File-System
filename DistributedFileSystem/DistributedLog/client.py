#!/usr/bin/env python
#coding:utf-8

import yaml
import logging
import socket
import threading
import shlex
import json
import time
import operator
import string

# logging 
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(threadName)-10s %(message)s',
)

LOGGER = logging.getLogger('DLQ Client')

class LogQueryThread(threading.Thread):
    """用来查询指定服务器的工作线程"""
    def __init__(self, client, server_information, grep_cmd):
        super(LogQueryThread, self).__init__()
        self.client = client
        self.server_information = server_information
        self.grep_cmd = grep_cmd + [self.client.conf['log_path'] + server_information['logfile']]
        self.buffer_size = 1024

    def run(self):
        
        try:
	    tick = time.time()
            HOST, PORT = self.server_information['ip'], self.client.conf['port']
            sock_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_connection.connect((HOST, PORT))
            sock_connection.sendall(json.dumps(self.grep_cmd))

            # 将查询的结果存储在临时文件中，这样匹配到的一行就不会被分割成两个结果
            with open('temp.result.server.%d' % self.server_information['id'], 'w+') as f:
                while True:
                    # 接收返回的消息，最大数据量为 1024
                    result = sock_connection.recv(self.buffer_size)
                    # 收集 server 上的所有结果
                    if result:
                        # 写到文件中
                        f.write(result)
                    # 输出收集到的结果
                    else:
                        # 输出临时文件中的每一行信息
                        f.seek(0)
                        for line in f.read().split('\n'):
                            # 去掉首尾的空字符
                            if line.strip():
                               print 'From %s: %s' % (self.server_information['logfile'], line)
                        # 统计临时文件中的行数并记录到 client.line_dict 中
                        f.seek(0)
                        line_count = len([1 for l in f.read().split('\n') if l])
                        if line_count:
                            self.client.line_dict.setdefault(self.server_information['id'], line_count)
                        break
        except socket.error, e:
            LOGGER.error('Server-%s %s' % (self.server_information['id'], e))
        else:
            LOGGER.info('Done with Server-%s' % self.server_information['id'])
        finally:
            sock_connection.close()
	    tock = time.time()

class LogQueryClient():
    """日志查询客户端"""
    def __init__(self, grep_cmd):
        with open('conf.yaml') as f:
            self.conf = yaml.safe_load(f)
        # 存放 grep 命令
        self.grep_cmd = grep_cmd
        # 存放服务器编号与匹配到的行数的字典
        self.line_dict = {}

    def analysis(self):
	self.total_line_count = reduce(operator.add, self.line_dict.values()) if self.line_dict else 0
        LOGGER.info('Totally found %d lines.' % self.total_line_count)
        LOGGER.info('Each server: ' + str(self.line_dict))
	
    def query(self):
        # 为每台 server 分配一个查询线程
        threads = []
        for server_information in self.conf['server_list']:
            worker_thread = LogQueryThread(self, server_information, self.grep_cmd)
            worker_thread.start()
            threads.append(worker_thread)

        # 保证该个命令所有查询完成后才进行下个命令的查询
        for t in threads:
            t.join()
		
        # 对结果进行分析
        self.analysis()

def main():
    while True:
        grep_cmd = shlex.split(raw_input('DLQ > '))
        client = LogQueryClient(grep_cmd)
	tick = time.time()
        client.query()
	tock=time.time()

if __name__ == '__main__':
        main()    
