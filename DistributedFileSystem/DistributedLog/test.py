#!/usr/bin/env python
#coding:utf-8
import client
import unittest
import yaml
import os
import sys
import time
import rstr
import logging

# logging 配置信息
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(threadName)-10s %(message)s',
    # filename='DLQServer.log',
    # filemode='a+',
)

LOGGER = logging.getLogger('DLQ Tester')

class DLCTestCase(unittest.TestCase):
    """对于 DistributedLogClient 的单元测试"""

    # 测试是否生成了对应数量的符合正则表达式的日志
    def test_frequency(self):
        with open('conf.yaml') as f:
            self.conf = yaml.safe_load(f)

        for pattern, frequency in self.conf['test']['frequency'].iteritems():
            grep_cmd = ['grep', '-E', self.conf['test']['pattern'][pattern]]
            c = client.LogQueryClient(grep_cmd)
            c.conf['log_path'] = self.conf['test']['log_path']

            sys.stdout = open('temp.test.out.%s' % pattern, 'w')
            c.query()
            sys.stdout = sys.__stdout__
            query_result = c.line_dict

            server_number = len(self.conf['server_list'])
            size_of_this_type = int(self.conf['test']['size'] * float(frequency))
            truth = {i : size_of_this_type for i in xrange(1, server_number + 1)}

            self.assertDictEqual(query_result, truth)

    # 测试特定服务器上是否有已知的日志
    def test_coverage(self):
        with open('conf.yaml') as f:
            self.conf = yaml.safe_load(f)

        # 1. 一个服务器应找到该信息
        grep_cmd = ['grep', 'server 1']
        c = client.LogQueryClient(grep_cmd)
        c.conf['log_path'] = self.conf['test']['log_path']

        sys.stdout = open('temp.test.out.one', 'w')
        c.query()
        sys.stdout = sys.__stdout__
        query_result = c.line_dict

        ground_truth = {1 : 1}

        self.assertDictEqual(query_result, ground_truth)  

        # 2. 某些特定服务器（hit_server）应找到该信息
        grep_cmd = ['grep', 'hit_server']
        c = client.LogQueryClient(grep_cmd)
        c.conf['log_path'] = self.conf['test']['log_path']

        sys.stdout = open('temp.test.out.some', 'w')
        c.query()
        sys.stdout = sys.__stdout__
        query_result = c.line_dict
        ground_truth = {i : 1 for i in self.conf['test']['hit_servers']}

        self.assertDictEqual(query_result, ground_truth)  

        # 3. 所有的服务器都应找到该信息
        grep_cmd = ['grep', 'all_server']
        c = client.LogQueryClient(grep_cmd)
        c.conf['log_path'] = self.conf['test']['log_path']

        sys.stdout = open('temp.test.out.all', 'w')
        c.query()
        sys.stdout = sys.__stdout__
        query_result = c.line_dict

        ground_truth = {i + 1 : 1 for i in xrange(len(self.conf['server_list']))}

        self.assertDictEqual(query_result, ground_truth) 

# 测试查询延迟
def test_speed():
        with open('conf.yaml') as f:
            conf = yaml.safe_load(f)

        latency = []
        sys.stdout = open('temp.test.out.speed', 'w')
        for i in xrange(conf['test']['speed_test_size']):
            grep_cmd = ['grep', rstr.xeger(r'[a-z]{,4}[.][a-z]{1,3}')]
            c = client.LogQueryClient(grep_cmd)

            tick = time.time()
            c.query()
            tock = time.time()
            
            latency.append(tock - tick)
        sys.stdout = sys.__stdout__

        average_latency = sum(latency) / len(latency)
        LOGGER.info('Average latency is ' + str(average_latency))

def main():
    test_speed()
    suite = unittest.TestLoader().loadTestsFromTestCase(DLCTestCase)
    unittest.TextTestRunner(verbosity=2).run(suite)

if __name__ == '__main__':
    main()
