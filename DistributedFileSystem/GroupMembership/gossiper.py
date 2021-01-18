#!/usr/bin/env python
#coding:utf-8


import logging
import socket
import thread
import json
import time
import random

# 日志的配置信息
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s %(levelname)s %(threadName)-10s %(message)s',
    filename='Gossiper.log.' + str(int(time.time())),
    filemode='w',
)

LOGGER = logging.getLogger('Gossiper')

# 同步 gossip() 和 listen()
member_list_lock = thread.allocate_lock()

# 配置信息
introducer_ip='192.168.0.102'
port=2334
interval_gossip=0.2
interval_reading=0.2
threshold_suspect=2
threshold_fail=4
threshold_forget=2

class MemberList(object):
    """ 由 gossiper 维护的成员列表 """

    def __init__(self, gossiper):
        super(MemberList, self).__init__()
        # 维护该成员列表的 gossiper
        self.gossiper = gossiper
        # introducer 的 ip 地址
        self.introducer_ip = introducer_ip    
        # 记录格式 -- id : {'heartbeat' : heartbeat, 'timestamp' : timestamp, 'status' : status}
        self.members = {}

    def __str__(self):
        begin = '%sMEMBERLIST BEGINS%s\n' % ('-' * 15, '-' * 15)
        content = ['%s : %6d, %f, %s\n' % (id, info['heartbeat'], info['timestamp'], info['status']) for id, info in self.members.iteritems()]
        end = '%sMEMBERLIST ENDS%s\n' % ('-' * 15, '-' * 18)
        return begin + ''.join(content) + end

    # 成员列表中是否含有 introducer
    def has_introducer(self):
        for id in self.members:
            if id.split('_')[0] == self.introducer_ip:
                return True
        return False

    # 添加 introducer
    def add_introducer(self):
        # 类似于接收到关于 introducer 的 rumor 消息
        id = self.introducer_ip
        self.members[id] = {
            'heartbeat': 0, 
            'timestamp': 0,
            'status': 'ADDED',
        }
        LOGGER.info('[ADDED INTRODUCER] %s : %s' % (id, str(self.members[id])))

    # 删除 introducer
    def del_introducer(self):
        if self.introducer_ip in self.members:
            del self.members[self.introducer_ip]
            LOGGER.info('[DELETED INTRODUCER] %s' % self.introducer_ip)

    # 处理收到的 rumor
    def merge(self, rumor):
        for id, heard in rumor.iteritems():
            # 清理虚拟的 introducer 信息，准备接收真实的 introducer 信息
            if self.introducer_ip in self.members and id.split('_')[0] == self.introducer_ip:
                self.del_introducer()

            if heard['status'] == 'LEFT':
                # 复制收到的 LEFT rumor
                if not id in self.members or self.members[id]['status'] == 'LEFT':
                    continue
                else:
                    self.members[id].update({
                        'heartbeat' : heard['heartbeat'],
                        'timestamp' : time.time(),
                        'status'    : 'LEFT',
                    })
                    LOGGER.info('[LEFT] %s : %s' % (id, str(self.members[id])))
            elif heard['status'] == 'JOINED':
                # 有新的成员
                if not id in self.members:
                    self.members[id] = {
                        'heartbeat' : heard['heartbeat'],
                        'timestamp' : time.time(),
                        'status'    : 'JOINED',
                    }
                    LOGGER.info('[JOINED] %s : %s' % (id, str(self.members[id])))
                else:
                    mine = self.members[id]
                    # 在收到更新的 heartbeat 后更新信息
                    if heard['heartbeat'] > mine['heartbeat']:
                        mine.update({
                            'heartbeat' : heard['heartbeat'],
                            'timestamp' : time.time(),
                            'status'    : 'JOINED',
                        })
                        # LOGGER.info('[UPDATED] %s : %s' % (id, str(self.members[id])))
            else:
                LOGGER.info('Unhandled status (%s) in rumor' % heard['status'])

    # 刷新成员状态
    def refresh(self):
        # 必要的时候改变成员状态
        # 使用 items() 而不是 iteritems(), 因为 dict 在 iteration 期间会变化
        for id, info in self.members.items(): 
            # 忽略 introducer 当它是虚拟的或只有该一个成员
            if info['status'] == 'ADDED':
                continue

            if info['status'] == 'JOINED' and time.time() - info['timestamp'] > float(threshold_suspect):
                info['status'] = 'SUSPECTED'
                LOGGER.info('[SUSPECTED] %s : %s' % (id, self.members[id]))
            elif info['status'] == 'SUSPECTED' and time.time() - info['timestamp'] > float(threshold_fail):
                LOGGER.info('[FAILING] %s : %s' % (id, self.members[id]))
                del self.members[id]
            elif info['status'] == 'LEFT' and time.time() - info['timestamp'] > float(threshold_forget):
                LOGGER.info('[FORGETING] %s : %s' % (id, self.members[id]))
                del self.members[id]

        if not self.has_introducer() and not self.gossiper.is_introducer():
            # 至少 introducer 被添加到本地
            self.add_introducer()

    # 随机挑选一名成员，返回它的IP
    def get_one_to_gossip_to(self, status=('JOINED', 'ADDED')):
        # 向状态为 ADDED 的节点发送 Gossip 的目的:
        #   1. 初始化我的存在
        #   2. 从坏的交流中恢复
        #   3. 帮助 introducer 在它失效后重新加入群组中
        candidates = [id for id, info in self.members.iteritems() if info['status'] in status]
        if not candidates:
            return None
        dest_id = random.choice(candidates)
        dest_ip = dest_id.split('_')[0]
        return dest_ip

    # 生成 rumor
    def gen_rumor(self, dest_ip):
        # Rumor 规则:
        #   0. timestamp 可以被忽略
        #   1. 包括那些为 'JOINED' 或 'LEFT' 状态的 gossiper
        #   2. 包括目的地址
        #   3. 包括我自己
        rumor_filter = lambda m : m[1]['status'] in ('JOINED', 'LEFT') and m[0].split('_')[0] != dest_ip
        rumor_candidates = {id : {'heartbeat' : info['heartbeat'], 'status' : info['status']} for id, info in self.members.iteritems()}
        rumor = dict(filter(rumor_filter, rumor_candidates.iteritems()))
        # 加入我自己
        rumor[self.gossiper.id] = {
            'heartbeat' : self.gossiper.heartbeat,
            'status'    : self.gossiper.status,
        } 
        return rumor
    # 含有特定状态成员的个数
    def count_member(self, status):
        return sum([1 for info in self.members.values() if info['status'] in status])

class Gossiper(object):
    """ 维护成员列表的 gossiper """

    def __init__(self):
        super(Gossiper, self).__init__()
       
	# 获取本机 ip 地址
	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.connect(('8.8.8.8', 0))
	self.ip=sock.getsockname()[0]

        self.id = '%s_%d' % (self.ip, int(time.time()))
        self.heartbeat = 1
        self.timestamp = time.time()
        self.status = 'JOINED'
        
        # 在成员列表中添加自己
        self.member_list = MemberList(self)
        # 在成员列表中添加 introducer
        if not self.is_introducer():
            self.member_list.add_introducer()

    # 判断自己是否为 introducer
    def is_introducer(self):
        return self.ip == introducer_ip

    # 心跳
    def heartbeat_once(self, last=False):
        self.heartbeat += 1
        self.timestamp = time.time()
        if last:
            self.status = 'LEFT'

    # 发送 Gossip
    def gossip(self):
        LOGGER.info('Start gossiping!')
        while True:
            member_list_lock.acquire()
            self.member_list.refresh()

            if self.status == 'TO_LEAVE':
                dest_ip = self.member_list.get_one_to_gossip_to(('JOINED'))
                # 发送离开的消息给随机一个状态为 JOINED 的成员
                if dest_ip:
                    self.heartbeat_once(last=True)
                    rumor = self.member_list.gen_rumor(dest_ip)
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(json.dumps(rumor), (dest_ip, port))
                    except Exception:
                        pass
                # 安全离开
                self.status = 'AFTER_LEFT'
                break
            elif self.status == 'JOINED':
                dest_ip = self.member_list.get_one_to_gossip_to()
                if dest_ip:
                    self.heartbeat_once()
                    rumor = self.member_list.gen_rumor(dest_ip)
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        sock.sendto(json.dumps(rumor), (dest_ip, port))
                    except Exception:
                        pass
            else:
                LOGGER.info('Unhandled status (%s) of gossiper' % self.status)

            member_list_lock.release()

            time.sleep(float(interval_gossip))

    # 监听其他成员发来的 rumor
    def listen(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.ip, port))
        LOGGER.info('Start listening!')
        while self.status == 'JOINED':
            rumor = json.loads(sock.recvfrom(1024)[0].strip())
            if rumor:
                member_list_lock.acquire()
                self.member_list.merge(rumor)
                member_list_lock.release()

   
    def run(self):
        # 初始化两个线程，一个用来发 gossip，一个用来监听其他成员发来的 rumor
        thread.start_new_thread(self.gossip,  ())
        thread.start_new_thread(self.listen,  ())
	while True:
            cmd = raw_input('list (list members)\nself (my id)\nleave\n')
            if cmd == 'list':
                print self.member_list
            elif cmd == 'self':
                print self.id
            elif cmd == 'leave':
                # 发送最后一个 rumor
                self.status = 'TO_LEAVE'
                LOGGER.info('Leaving...')
                # 一直等待直到发送 rumor 完成
                while self.status != 'AFTER_LEFT':
                    pass
                LOGGER.info('Left completely.')
                break
            else:
                print 'Wrong command.'

if __name__ == '__main__':
    gossiper = Gossiper()
    tick = time.time()
    gossiper.run()
    tock=time.time()




