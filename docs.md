# harness-prompt-radar

持续追踪主流 AI Agent Harness(Claude Code、Codex CLI、Kimi Code CLI、OpenCode 等)的 system prompt 与 tool schema,记录版本演变,并公开可视化对比。

> 名字先占位,可以改。核心定位不变:**这是一个数据项目,不是一个分析项目**。MVP 阶段只做"抓取 + 存储 + 展示",不做"这些差异意味着什么"的解读。

---

## 1. 要解决的问题

主流 agent harness 的 system prompt 和工具定义对用户不透明。它们只存在于打包后的 npm 产物或编译二进制里,版本更新后旧内容也会被覆盖、无处查证。目前没有一个公开、持续更新、可回溯版本历史的数据源能回答:

- 某个 harness 当前的 system prompt 有多长?
- 某次版本更新,system prompt 具体改了哪几句话?
- 不同 harness 之间,系统提示词的设计哲学(极简 vs 详尽)差异有多大?

本项目就是做这一件事:**把这些黑盒内容定期抓出来,存成结构化历史数据,公开展示**。

## 2. 范围界定

### 做什么
- 定期抓取目标 harness 的 system prompt 全文
- 定期抓取目标 harness 内置工具(tool/function)的 schema 定义
- 保留完整版本历史,版本间可 diff
- 提供一个只读的公开网页做浏览和对比

### 不做什么(MVP 阶段明确排除)
- 不分析这些 prompt 差异对 benchmark 表现的因果影响(这是后续独立的实验项目,依赖本项目产出的数据,但不在同一个代码库/同一次迭代里做)
- 不做工具 schema 的语义质量评分或 lint
- 不追求首版就覆盖所有 harness,先跑通 3–4 个再横向扩展
- 不做用户账号、评论区等社区功能,纯只读展示

## 3. 目标 Harness(首批)

| Harness | 分发形式 | 抓取难度 |
|---|---|---|
| Claude Code | npm 包 (`@anthropic-ai/claude-code`) | 中 — 需从打包后的 JS bundle 里定位 |
| Codex CLI | GitHub Release 二进制 | 中 — 编译产物,需字符串提取 |
| Kimi Code CLI | npm 包 | 中 |
| OpenCode | GitHub Release 二进制 | 中 |

后续按同一套抓取范式横向扩展,不改变数据模型。

## 4. 数据模型

每次抓取产出一条记录,字段固定:

```
{
  "harness": "claude-code",
  "version": "2.1.88",
  "extracted_at": "2026-08-19T00:00:00Z",
  "source_url": "指向该版本发布产物的原始链接",
  "system_prompt": "抓取到的system prompt全文",
  "system_prompt_token_count": 8421,
  "tool_schemas": [
    {"name": "Read", "schema": { ... }},
    {"name": "Bash", "schema": { ... }}
  ],
  "extraction_method": "npm_bundle_grep | binary_strings",
  "extraction_confidence": "high | low"
}
```

`extraction_confidence` 是必须字段:抓取脚本用正则/锚点定位,遇到 harness 改了混淆方式导致定位可能不准时,标记为 `low` 并在展示层给出视觉提示,而不是静默产出错误数据。

同一 `harness + version` 只保留一条记录,重复抓取不产生冗余数据。版本之间的差异通过对相邻两条记录的 `system_prompt` 字段做文本 diff 实时计算,不需要额外存储 diff 结果。

## 5. 抓取方式

按分发形式分两类,不为每个 harness 单独设计一套逻辑:

**npm 包类**:`npm pack` 下载 tarball → 解包 → 在打包后的 JS 里用锚点字符串(如已知的 system prompt 开场白片段)定位并提取完整文本 → 用相同方法定位工具 schema 定义(通常是相邻的 JSON 结构)。

**二进制类**:`strings` 提取所有可打印字符串 → 用启发式规则(连续长度超过阈值的自然语言文本块 + 已知锚点)过滤出 system prompt 候选 → 人工确认一次锚点后固化进抓取脚本。

每个 harness 对应一个独立的抓取脚本,遵循相同的输入(harness 标识)输出(上述数据模型)约定,互不依赖。

## 6. 更新机制

- 每日定时检查各 harness 的最新版本号(npm registry API / GitHub Releases API)
- 版本号与已存版本一致则跳过,不重复抓取
- 版本号有更新才触发对应抓取脚本
- 抓取脚本运行失败(锚点失效等)不能让整个流程中断,需单独记录失败状态,不影响其他 harness 的抓取

## 7. 展示层

一个静态只读页面,内容:

- 首页:各 harness 当前 system prompt 的 token 数量横向对比
- 详情页:点进某个 harness,展示版本历史列表 + 任意两版本间的 diff 视图

不需要后端服务,数据是静态生成的,页面可以托管在任何静态站点服务上。

## 8. 明确的验收标准(MVP 完成的定义)

- [ ] 4 个目标 harness 均能成功抓取至少 1 条历史记录
- [ ] 版本更新后,系统能自动检测到并触发新一轮抓取,无需人工介入
- [ ] 展示页能正确渲染 token 数对比和至少一组版本 diff
- [ ] 任一 harness 抓取失败不影响其余 harness 的正常运行

## 9. 后续规划(不在本次迭代内,仅记录方向)

- 横向扩展更多 harness
- 工具 schema 的结构化版本对比(不只是 system prompt)
- 基于本项目数据的独立实验:prompt/harness 变化与公开 benchmark 分数的关联分析