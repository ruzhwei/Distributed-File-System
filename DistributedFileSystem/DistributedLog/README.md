# Distributed log querier 

## 依赖环境

1. python 2.7
2. pyyaml，rstr

## 运行
0. 运行前将所有节点的 ip 及配置信息写在 conf.yaml 文件中。
1. 在每一个节点上执行 `python server.py` 并保持运行。
2. 在想要查询的节点上，执行`python client.py` ，输入 grep 命令即可查询。
3. 执行 `python gen_testlog.py` 可以产生测试日志。
4. 执行 `python test.py` 可以基于测试日志进行测试。