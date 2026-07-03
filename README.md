# DOUYlike

抖音收藏夹自动更新系统 — 采集、转写、AI分析、飞书多维表格同步

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Whisper-faster--whisper-green" alt="Whisper">
  <img src="https://img.shields.io/badge/LLM-OpenAI%20Compatible-orange" alt="LLM">
  <img src="https://img.shields.io/badge/Feishu-Bitable%20API-blue" alt="Feishu">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen" alt="MIT">
</p>

## 功能特性

- **收藏夹自动采集** — 通过 Chrome CDP 连接本地浏览器，增量采集抖音收藏夹视频
- **Whisper 语音转写** — faster-whisper 本地转写，支持 CUDA 加速
- **AI 纠错优化** — LLM 自动纠正逐字稿中的错别字、同音字、断句错误
- **多维度 AI 分析** — 视频内容分析、选题趋势分析、爆款公式提炼
- **飞书多维表格同步** — 数据自动写入飞书 Bitable，支持多表关联
- **Web 控制台** — 可视化配置、实时日志、一键执行
- **定时任务** — 支持每隔 N 小时自动执行，也可手动触发

## 架构

```
抖音收藏夹
    │
    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  采集下载    │───▶│  Whisper    │───▶│  AI 分析    │───▶│  飞书同步   │
│  Chrome CDP  │    │  逐字稿     │    │  + 纠错     │    │  Bitable    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                                    │
       ▼                                    ▼
  SQLite 本地库                        Prompt 可配置
```

## 飞书多维表格结构

| 数据表 | 字段 |
|--------|------|
| **Videos** | 标题、作者、链接、点赞/评论/收藏/转发/播放数、时长、发布时间、标签、BGM |
| **Transcripts** | 逐字稿全文（AI纠错）、字数、时长 |
| **AI Analysis** | 主题、内容类型、目标受众、钩子分析、内容结构、差异化卖点、AI评分、爆款潜力 |
| **Topic Analysis** | 话题名称、频率、趋势方向、热度评分、选题建议、空白点 |
| **Hotspots** | 关键词、平台、热度指数、趋势描述、时效性 |

## 快速开始

### 环境要求

- Python 3.11+
- Chrome 浏览器（需登录抖音）
- FFmpeg（Whisper 提取音频用）
- GPU 可选（CUDA 加速 Whisper 转写）

### 安装

```bash
git clone https://github.com/yourname/DOUYlike.git
cd DOUYlike
pip install -r requirements.txt
playwright install chromium
```

### 配置

1. **飞书自建应用**
   - 登录 [飞书开放平台](https://open.feishu.cn/) → 创建自建应用
   - 开通 `bitable:app` 权限
   - 记录 App ID 和 App Secret

2. **LLM API**
   - 支持任何 OpenAI 兼容 API（OpenAI / DeepSeek / 通义千问等）

3. **编辑 config.yaml**

```yaml
llm:
  base_url: "https://api.openai.com/v1"
  api_key: "sk-your-key"
  model: "gpt-4o"

feishu:
  app_id: "cli_xxxx"
  app_secret: "xxxx"
```

### 运行

```bash
# 启动 Chrome（需登录抖音）
# Chrome 启动参数：--remote-debugging-port=9222 --user-data-dir=你的目录

# 执行完整流水线
python main.py run

# 仅采集收藏夹
python main.py collect

# 仅转写逐字稿
python main.py transcribe

# AI 纠错逐字稿
python main.py fix-typos

# 仅 AI 分析
python main.py analyze

# 仅同步飞书
python main.py sync

# 查看统计
python main.py stats

# 启动 Web 控制台
python webui.py
# 访问 http://localhost:8088
```

### Web 控制台

启动 `python webui.py` 后访问 http://localhost:8088

- **控制台** — 数据统计、Chrome 状态、执行按钮、实时日志
- **配置** — 飞书/LLM/Whisper/抖音/定时任务
- **提示词** — 3 个 AI 分析 Prompt 可在线编辑
- **日志** — 完整运行历史

## 项目结构

```
DOUYlike/
├── main.py              # CLI 入口
├── webui.py             # Web 控制台
├── config.yaml          # 配置文件
├── requirements.txt     # 依赖
├── core/
│   ├── config.py        # 配置管理
│   ├── database.py      # SQLite 数据库
│   ├── collector.py     # 抖音收藏夹采集
│   ├── downloader.py    # 视频下载
│   ├── transcriber.py   # Whisper 转写 + AI 纠错
│   ├── analyzer.py      # AI 多维度分析
│   ├── feishu.py        # 飞书多维表格同步
│   ├── scheduler.py     # 定时任务
│   └── pipeline.py      # 流水线编排
├── prompts/             # AI 分析 Prompt 模板
│   ├── analyze_video.txt
│   ├── analyze_topic.txt
│   └── analyze_viral.txt
└── data/                # 本地数据
    ├── downloads/
    ├── transcripts/
    └── reports/
```

## 与 DyD 的关系

DOUYlike 的采集和转写模块参考了 [AI 内容罗盘 (DyD)](https://github.com/yourname/DyD) 的架构设计，通过 Chrome CDP 连接本地浏览器获取抖音数据，避免逆向认证。两个项目可独立运行。

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `douyin.chrome_debug_port` | Chrome 远程调试端口 | 9222 |
| `whisper.model_size` | Whisper 模型 (base/medium/large) | medium |
| `whisper.device` | 设备 (cuda/cpu) | cuda |
| `llm.model` | LLM 模型名 | gpt-4o |
| `scheduler.interval_hours` | 定时间隔（小时） | 4 |

## License

MIT License

## 致谢

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — 高效 Whisper 推理
- [lark-oapi](https://github.com/larksuite/oapi-sdk-python) — 飞书 Open API SDK
- [Playwright](https://playwright.dev/) — 浏览器自动化
