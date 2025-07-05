# 🎙️ 实时语音整理助手

> 🚀 基于腾讯云ASR + DeepSeek的实时语音转文字与智能优化系统

一个优雅的实时语音转录和智能文本处理工具，采用苹果风格的现代化界面设计，支持实时语音识别、文本可读性优化和准确性检查。

## ✨ 核心特性

### 🎯 **语音识别**
- **实时转录** - 基于腾讯云ASR，支持中英文混合识别
- **高精度识别** - 16kHz高质量音频处理
- **即时反馈** - WebSocket实时通信，低延迟响应

### 🧠 **智能优化**
- **可读性整理** - 使用DeepSeek AI优化文本结构和表达
- **给我点启发** - 生成洞见与思考挑战，激发灵感
- **自定义提示词** - 用户可个性化配置AI处理逻辑

### 🎨 **现代界面**
- **苹果风格设计** - 磨玻璃效果和优雅动画
- **响应式布局** - 完美适配桌面、平板、手机
- **深色模式** - 自动适配系统主题偏好
- **无障碍支持** - 符合Web可访问性标准

## 🛠️ 技术架构

```
Frontend (静态文件)          Backend (FastAPI)           第三方服务
├── HTML/CSS/JS            ├── 实时WebSocket服务        ├── 腾讯云ASR
├── 苹果风格UI             ├── DeepSeek集成            └── DeepSeek API
├── WebSocket客户端        ├── 音频处理引擎
└── 设置管理 (含模型选择)   └── REST API端点
```

## 📋 环境要求

- **Python**: 3.8+
- **操作系统**: Windows/macOS/Linux
- **浏览器**: Chrome 88+, Firefox 85+, Safari 14+
- **网络**: 稳定的互联网连接（用于API调用）

## 🚀 快速开始

### 1️⃣ **克隆项目**

   ```bash
git clone https://github.com/Squareczm/STTstructured/
   cd STTstructured
   ```

### 2️⃣ **安装依赖**

   ```bash
pip install -r requirements.txt
```

### 3️⃣ **获取API密钥**

#### 腾讯云ASR配置
1. 访问 [腾讯云控制台](https://console.cloud.tencent.com/)
2. 开通"语音识别"服务
3. 获取以下信息：
   - `APP_ID`: 应用ID
   - `SECRET_ID`: 密钥ID  
   - `SECRET_KEY`: 密钥Key

#### DeepSeek配置
1. 访问 [DeepSeek平台](https://platform.deepseek.com/)
2. 注册账号并创建API密钥
3. 获取 `API_KEY`

### 4️⃣ **配置环境变量**

复制环境变量模板：
     ```bash
cp env.template .env
     ```

编辑 `.env` 文件，填入您的API密钥：
     ```bash
# 腾讯云ASR配置
TENCENT_APP_ID=your_app_id_here
TENCENT_SECRET_ID=your_secret_id_here  
TENCENT_SECRET_KEY=your_secret_key_here

# DeepSeek配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
     ```

### 5️⃣ **启动服务**

   ```bash
python realtime_server.py
```

或使用uvicorn：
   ```bash
   uvicorn realtime_server:app --host 0.0.0.0 --port 3006
   ```

### 6️⃣ **访问应用**

打开浏览器访问：**http://localhost:3006**

## 📱 使用指南

### 🎙️ **语音录制**
1. 点击中央的**录音按钮**开始录制
2. 对着麦克风清晰地说话
3. 再次点击按钮停止录制
4. 系统会实时显示转录结果

### ⚙️ **个性化设置**
1. 点击右上角的**设置按钮**（⚙️）
2. 自定义**可读性整理提示词** - 控制文本优化方式
3. 自定义**给我点启发提示词** - 控制启发式生成逻辑
4. 点击**保存设置**应用更改

### 🔄 **文本处理**
- **可读性整理按钮** - 优化文本可读性
- **给我点启发按钮** - 产出富有洞察力的启发内容
- **Copy按钮** - 一键复制处理结果

### 🌙 **主题切换**
点击右上角的**主题按钮**在浅色/深色模式间切换

## 📝 项目结构

```
brainwave/
├── 📄 realtime_server.py      # FastAPI后端服务器
├── 📄 llm_processor.py        # DeepSeek AI处理器
├── 📄 tencent_asr_client.py   # 腾讯云ASR客户端
├── 📄 prompts.py              # AI提示词模板
├── 📄 requirements.txt        # Python依赖
├── 📄 env.template           # 环境变量模板
├── 📂 static/                # 前端静态文件
│   ├── 📄 realtime.html      # 主页面
│   ├── 📄 main.js            # JavaScript逻辑
│   └── 📄 style.css          # 苹果风格样式
└── (已省略tests目录)
```

> 当前版本暂未包含自动化测试用例，如有需要欢迎贡献。

## 🔧 常见问题

### ❓ **麦克风权限问题**
- **现象**: 浏览器无法访问麦克风
- **解决**: 在浏览器设置中允许麦克风权限，确保使用HTTPS或localhost

### ❓ **连接状态异常**
- **现象**: 页面左上角指示灯为红色
- **解决**: 检查API密钥配置，确保网络连接正常

### ❓ **音频质量问题**
- **现象**: 识别准确率低
- **解决**: 
  - 确保环境安静
  - 麦克风距离适中（15-30cm）
  - 说话清晰，语速适中

### ❓ **API调用失败**
- **现象**: 处理按钮无响应或报错
- **解决**: 
  - 验证DeepSeek API密钥是否正确
  - 检查账户余额是否充足
  - 确认网络连接稳定

## 🚀 部署指南

### Docker部署
   ```bash
# 构建镜像
docker build -t brainwave .

# 运行容器
docker run -d \
  -p 3006:3006 \
  -e TENCENT_APP_ID=your_app_id \
  -e TENCENT_SECRET_ID=your_secret_id \
  -e TENCENT_SECRET_KEY=your_secret_key \
  -e DEEPSEEK_API_KEY=your_api_key \
  brainwave
```

### 云服务器部署
1. 上传代码到服务器
2. 安装Python依赖
3. 配置环境变量
4. 使用进程管理器（如PM2）启动服务
5. 配置反向代理（Nginx）

## 🤝 贡献指南

欢迎提交Issue和Pull Request！

1. Fork本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建Pull Request

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [腾讯云](https://cloud.tencent.com/) - 提供语音识别服务
- [DeepSeek](https://www.deepseek.com/) - 提供AI语言模型
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架
- [苹果设计语言](https://developer.apple.com/design/) - 设计灵感来源

---

**💡 如有问题或建议，欢迎提交Issue或联系开发者！**
