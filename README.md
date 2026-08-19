# harness-prompt-radar

持续追踪主流 AI Agent Harness(Claude Code、Codex CLI、Kimi Code CLI、OpenCode)的 system prompt,记录版本演变,公开可视化对比。

这是一个数据项目,不是分析项目:只做"抓取 + 存储 + 展示",不解读这些差异意味着什么。

完整背景和设计见 [docs.md](docs.md)。

## 结构

```
scrapers/       每个 harness 一个抓取脚本 + 公共存储逻辑
data/           抓取结果,每个 harness 一个 JSON 文件(版本历史数组)
site/           静态只读展示页面,无构建步骤
```

## 数据来源与抓取方式

| Harness | 来源 | 方式 | 置信度 |
|---|---|---|---|
| Claude Code | npm 原生二进制包 | 从内嵌的 V8 快照里按锚点提取字符串片段并拼接 | 低 — 拼接顺序为启发式推断 |
| Codex CLI | GitHub 仓库源码(`gpt_5_codex_prompt.md`) | 按 release tag 直接拉取文本文件 | 高 |
| Kimi Code CLI | npm JS bundle | 正则定位字符串字面量并解码 | 高 |
| OpenCode | GitHub 仓库源码(`prompt/default.txt`) | 按 release tag 直接拉取文本文件 | 高 |

Claude Code 的抓取方式和 docs.md 最初设想的不同:该包目前只分发编译后的原生二进制(不再是可读的 JS bundle),因此改用字符串启发式提取,并如实标记为低置信度。

## 本地运行

```bash
pip install -r requirements.txt
cd scrapers
python3 run_all.py       # 抓取全部 harness,生成 data/*.json 和 manifest.json
```

单个 harness:

```bash
python3 claude_code.py
python3 codex_cli.py
python3 kimi_code.py
python3 opencode.py
```

预览展示页(需要先跑一次抓取生成 data/):

```bash
python3 -m http.server 8000
# 打开 http://localhost:8000/site/index.html
```

## 自动化

- `.github/workflows/scrape.yml`:每天定时跑一次全部抓取脚本,把新增数据提交回仓库。单个 harness 抓取失败不影响其他 harness(`run_all.py` 内部隔离)。
- `.github/workflows/pages.yml`:`site/` 或 `data/` 有变更时,把两者一起发布到 GitHub Pages。

## 数据模型

见 [docs.md](docs.md#4-数据模型)。
