# 券商营业部小红书文案自动生成系统

每天自动抓取 A 股真实市场数据，调用 AI 生成多篇小红书文案，支持配图和定时任务。

## 功能特性

- 📊 **真实市场数据** — 通过 akshare 对接东方财富/财联社，抓取指数、板块涨跌、财经快讯、IPO 日历
- ✍️ **6 种内容分类** — 市场热点 / 新闻动态 / IPO / 投顾服务 / 投资者教育 / 每日精选
- 🎨 **AI 配图** — DALL-E 3 自动生成小红书封面图（可在配置中开关）
- ⏰ **自动调度** — Windows Task Scheduler 每天收盘后自动运行
- 🛡️ **容错设计** — 数据失败继续、LLM 失败自动回退、非交易日只生成投教内容
- 📁 **日期归档** — `output/YYYY-MM-DD/` 结构，含市场数据快照供人工复核

## 项目结构

```
├── generate_xhs_copy.py              # 主入口 CLI
├── config.json                       # 配置（分类、时间、图片等）
├── .env.example                      # 环境变量模板
├── requirements.txt                  # 依赖清单
│
├── xhs_generator/                    # 核心包
│   ├── data/                         # 数据采集（akshare）
│   │   ├── fetcher.py                #   基类 + 工具函数
│   │   ├── market_data.py            #   指数、板块、涨跌家数
│   │   ├── news_data.py              #   东方财富/财联社快讯
│   │   └── ipo_data.py               #   新股 IPO 日历
│   ├── generator/                    # 内容生成
│   │   ├── prompt_builder.py         #   6 种分类提示词（注入真实数据）
│   │   ├── llm_client.py             #   OpenAI 封装 + 重试 + 回退
│   │   └── image_generator.py        #   DALL-E 3 配图
│   ├── scheduler/                    # 调度
│   │   ├── daily_runner.py           #   每日编排主流程
│   │   └── task_scheduler.py         #   Python schedule + CLI 入口
│   └── output/
│       └── file_manager.py           #   日期文件夹输出管理
│
├── scripts/
│   ├── install_scheduled_task.ps1    # Windows 计划任务一键安装
│   └── run_daily.bat                 # 批处理包装
│
└── tests/                            # 单元测试
    ├── test_generate_xhs_copy.py
    ├── test_data_fetchers.py
    ├── test_prompt_builder.py
    └── test_file_manager.py
```

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
copy .env.example .env
```

编辑 `.env` 填入你的 OpenAI API Key：

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
```

### 3. 试运行

```bash
# 预览效果，不保存文件
python generate_xhs_copy.py --dry-run

# 只生成单个分类
python generate_xhs_copy.py --content-type 市场热点 --dry-run

# 不生成配图
python generate_xhs_copy.py --dry-run --no-image
```

### 4. 正式运行

```bash
# 全部分类 + 配图
python generate_xhs_copy.py

# 指定日期
python generate_xhs_copy.py --date 2026-07-06
```

输出示例：

```
output/
└── 2026-07-06/
    ├── 00_market_snapshot.md    # 市场数据快照
    ├── 01_市场热点.md
    ├── 02_新闻动态.md
    ├── 03_IPO.md
    ├── 04_投顾服务.md
    ├── 05_投资者教育.md
    ├── 06_每日精选.md
    ├── _summary.md              # 运行摘要
    └── images/
        ├── 01_市场热点.png
        └── ...
```

## 定时任务

### Windows 计划任务（推荐）

以管理员身份运行 PowerShell：

```powershell
.\scripts\install_scheduled_task.ps1
```

默认每天下午 4:00（A 股收盘后）自动运行。可自定义：

```powershell
.\scripts\install_scheduled_task.ps1 -RunTime "17:00" -TaskName "我的小红书写手"
```

### 守护进程模式（开发用）

```bash
python generate_xhs_copy.py --daemon --time 16:00
```

进程会常驻后台，每天定时执行。

## 配置说明

编辑 `config.json`：

| 字段 | 说明 | 默认值 |
|---|---|---|
| `model` | LLM 模型 | `gpt-4o-mini` |
| `tone` | 文案风格 | 专业、平实、亲切 |
| `hashtags` | 话题标签 | 券商、A股、投资教育 |
| `length` | 字数区间 | 150-220字 |
| `schedule.enabled_categories` | 启用的分类 | 全部 6 个 |
| `schedule.time` | 每日运行时间 | 16:00 |
| `generation.temperature` | 生成温度 | 0.8 |
| `generation.retry_count` | 失败重试次数 | 3 |
| `image.enabled` | 是否生成配图 | true |
| `image.model` | 图片模型 | dall-e-3 |
| `data.top_sectors_count` | 板块取前几名 | 5 |

## 运行测试

```bash
python -m unittest tests.test_prompt_builder tests.test_file_manager -v
```

## 非交易日处理

周末/节假日 A 股不交易时，系统自动检测无行情数据，仅生成「投顾服务」和「投资者教育」两类文案，跳过市场相关分类。

## 注意事项

- 文案由 AI 生成，发布前请人工审核
- 市场数据来自公开信息，仅供资讯分享，不构成投资建议
- DALL-E 配图会产生 API 费用（约 $0.04/张）
