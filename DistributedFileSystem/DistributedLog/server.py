#!/usr/bin/env python
#coding:utf-8
import yaml
import logging
import socket, SocketServer
import threading
import subprocess
import json

# logging 配置信息
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(threadName)-10s %(message)s',
)

LOGGER = logging.getLogger('DLQ Server')

class LogQueryRequestHandler(SocketServer.BaseRequestHandler):
    """处理接收到的查询日志请求"""
    def handle(self):
        req = self.request.recv(1024).strip()
        grep_cmd = json.loads(req)

        handler_thread = threading.current_thread()
        LOGGER.info('Handler thread starts querying [%s]' % ' '.join(grep_cmd))
        
        try:
            # 执行收到的命令
            output = subprocess.check_output(grep_cmd)
            # 去掉尾部的'\n'
            output = output[:-1]
            line_count = len(output.split('\n'))
            LOGGER.info('Found %d lines.' % line_count)
        except subprocess.CalledProcessError, e:
            LOGGER.info('No matched lines.')
            output = ''
        except Exception, e:
            LOGGER.info(e.strerror)
        finally:
            self.request.sendall(output)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """与客户端交互的服务器端"""
def main():
    # 加载配置文件
    with open('conf.yaml') as f:
        conf = yaml.safe_load(f)
	
	# 获取本机 ip 地址及端口
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.connect(('8.8.8.8', 0))
    HOST=sock.getsockname()[0]
    PORT=conf['port']
	
    # 开启服务器线程
    try:
	server = ThreadedTCPServer((HOST, PORT), LogQueryRequestHandler)
	server_thread = threading.Thread(target=server.serve_forever())
	LOGGER.info('Server thread starts serving.')
        server_thread.start()
    except KeyboardInterrupt:
        server.shut_down()
        server.close()
    
if __name__ == '__main__':
    main()
