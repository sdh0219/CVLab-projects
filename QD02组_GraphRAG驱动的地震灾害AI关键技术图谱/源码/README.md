# 源码运行说明

本目录保留项目可复现源码，不包含 node_modules、dist、.wrangler 等依赖和缓存目录。

## 环境准备
1. 安装 Node.js 18+。
2. 在本目录执行：npm.cmd install
3. 启动前端：npm.cmd run dev
4. 访问：http://localhost:3000

## 常用命令
- npm.cmd run lint
- npm.cmd run build
- npm.cmd run atlas:refresh

## 说明
GraphRAG 索引数据和前端 atlas 快照已放在“1_数据包/processed_data”。
