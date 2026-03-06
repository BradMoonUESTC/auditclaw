# auditclaw

`auditclaw` 是一个面向代码审计场景的 agent-driven 核心扫描框架。它最核心的价值是：任何审计师只需要把自己的审计知识、检查思路和提示词方法写进 auditor 里的 `Markdown` 文件，就可以组装出一个属于自己的 AI 扫描引擎，而不需要自己重写整套 agent 运行框架。

更具体地说，审计师主要负责把方法论沉淀到 `decompose.md`、`audit.md`、`report.md` 和 `knowledge/*.md` 里；`auditclaw` 则负责把这些知识转成可执行的扫描流水线，包括任务拆解、fan-out 执行、产物归档、日志记录和成本统计。

当前仓库实现的是 `Audit Core`，也就是核心扫描与审计执行层。它已经具备任务拆解、并行审计、运行日志、事件流、产物归档和 findings 落盘等能力，但**还没有**包含类似 `openclaw` 的外围自动化能力，例如目标接入、任务调度、消息通知、工单流转、外部平台联动和长期运营编排等外层系统。

英文说明见 `README.md`。

## 核心设计思路

`auditclaw` 的目标不是做一个完全开放的通用工作流引擎，而是把安全审计里最稳定、最值得复用的主流程收敛成一套固定骨架：

1. 用 `decompose.md` 把目标项目拆成标准化审计任务。
2. 对任务产物做结构校验，确保 fan-out 输入稳定。
3. 用 `audit.md` 对每个任务并行执行审计。
4. 将每个任务的过程记录写入对应输出目录，包括 `memory.md`、`summary.md` 和 `finding.json`。
5. 在核心扫描结束后，按顺序执行可选的 `extra_steps`，例如生成汇总报告。

这样做的关键收益是：

- 审计知识主要沉淀在 `auditor.json`、`decompose.md`、`audit.md`、`report.md` 和 `knowledge/` 中，便于版本化和复用。
- 审计执行层负责并行、日志、成本统计、事件发布、目录初始化和结果归档，减少重复造轮子。
- 审计结果既有适合人阅读的 Markdown，也有适合程序消费的结构化产物，比如 `finding.json`。

## 审计器定义

一个审计器就是一个文件夹，通常长这样：

```text
auditors/
└── my-auditor/
    ├── auditor.json
    ├── decompose.md
    ├── audit.md
    ├── report.md
    └── knowledge/
        └── checklist.md
```

其中：

- `auditor.json` 定义后端、模型、运行 profile、变量和额外步骤。
- `decompose.md` 定义审计师希望 AI 如何拆解目标，生成 `task.json` 集合。
- `audit.md` 定义审计师希望 AI 如何审计单个任务。
- `knowledge/` 存放 checklist、规则和方法论材料，作为扫描过程中的知识注入源。
- `extra_steps` 用于在核心扫描完成后做报告整理等后处理。

核心思想就是：审计师写 `md`，框架负责把这些知识编排成可重复执行的 AI 扫描引擎。

## 运行时目录

执行时，`auditclaw` 会在目标项目根目录下创建固定的 `audit-materials/` 结构：

```text
target-project/
└── audit-materials/
    ├── knowledge/
    ├── decompose/
    │   └── tasks/
    ├── audit/
    │   └── <task_id>/
    │       ├── memory.md
    │       ├── summary.md
    │       └── finding.json
    ├── report/
    └── logs/
```

这里的核心约束是：

- `decompose` 必须产出标准化的 `task.json`
- `audit` 必须按任务子目录写入中间产物
- 审计过程中一旦确认漏洞，需要及时更新该任务目录下的 `finding.json`

## 当前能力边界

目前 `auditclaw` 聚焦在核心扫描能力，已经覆盖：

- 审计任务拆解
- fan-out 并行审计
- 结构化 findings 记录
- 报告后处理步骤
- HTTP / stdio / Python API 访问核心能力
- 运行日志、事件和成本统计

目前**尚未实现**的，是更外围的平台自动化层，例如：

- 类似 `openclaw` 的目标管理和接入流程
- 任务调度、重试编排和批量队列治理
- 通知、审批、工单和协作流转
- 面向团队运营的持续化审计平台能力
- 完整的外部系统集成与闭环自动化

可以把现在的 `auditclaw` 理解为一个可嵌入、可扩展的核心引擎，而不是完整的审计平台产品。

## 快速开始

安装后可以直接使用 CLI：

```bash
auditclaw init demo-auditor
auditclaw validate ./auditors/example-sol-audit
auditclaw run --auditor ./auditors/example-sol-audit --target ./bankroll
```

也可以通过 Python API 调用：

```python
from auditclaw.runner import run_auditor

result = run_auditor(
    "./auditors/example-sol-audit",
    "./bankroll",
)

print(result.summary_path)
```

如果需要把核心能力暴露给外部系统，还可以启动 HTTP 服务或 stdio RPC 桥接层。

## 项目定位

`auditclaw` 当前的定位很明确：

- 它是审计核心扫描引擎
- 它不是完整的外围自动化平台
- 它适合作为后续接入更大系统时的核心执行层