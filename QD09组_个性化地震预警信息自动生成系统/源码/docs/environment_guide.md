# 环境部署与启动说明

## 使用方式

### 首次运行（在新电脑上）
```text
双击 一键部署环境.bat
```
自动完成：
1. 检测系统Python（3.10-3.12）
2. 如无Python，安装项目自带的Python 3.11
3. 创建虚拟环境 .venv
4. 安装依赖（优先离线，失败则联网）
5. 验证核心模块可导入
6. 运行 main.py 生成统计图
7. 执行Flask基础自检

### 后续启动
```text
双击 start_project.bat
```
自动完成：
1. 检查虚拟环境
2. 检查核心依赖
3. 检查地震数据
4. 运行 main.py 更新统计图
5. 启动Flask Web服务
6. 等待服务就绪后打开浏览器

## 手动运行方式
```bash
cd 2_源码
.venv\Scripts\python.exe app.py
```
浏览器访问：http://127.0.0.1:5000

## 常见问题

### 问题 1：提示"环境尚未部署"
请先双击 `一键部署环境.bat` 完成环境安装。

### 问题 2：pip install 速度很慢
项目已包含离线依赖包（wheelhouse/），部署脚本会优先使用离线安装。
如需联网安装，可使用国内镜像：
```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 3：地震数据无法采集（网络不可用）
系统会自动使用上一次成功缓存的真实数据，不影响演示。

### 问题 4：页面能打开但没有统计图
运行以下命令重新生成统计图：
```bash
.venv\Scripts\python.exe main.py
```

### 问题 5：定位按钮无法获取位置
浏览器拒绝了定位权限，或电脑没有定位硬件。可以直接在位置输入框中手动输入地址名称。

### 问题 6：页面显示乱码
在浏览器中手动将编码设置为 UTF-8，或使用 Chrome 浏览器访问。
