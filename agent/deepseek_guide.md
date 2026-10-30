# DeepSeek Agent 集成指南 / DeepSeek Agent Integration Guide

## 概述 / Overview

本目录提供将 eval_ms_pipeline 集成到 DeepSeek AI Agent 的全部配置文件。

This directory provides all configuration files to integrate eval_ms_pipeline into a DeepSeek AI Agent.

## 文件说明 / Files

| 文件 | 用途 |
|------|------|
| `tool_manifest.json` | OpenAI function calling 格式的工具定义（兼容 DeepSeek API） |
| `system_prompt.md` | AI Agent 的系统提示词（描述工具能力与使用规则） |
| `deepseek_guide.md` | 本文件：DeepSeek 集成步骤 |

## 集成步骤 / Integration Steps

### 方式 1：DeepSeek API + Function Calling

```python
import json
from openai import OpenAI

client = OpenAI(
    api_key="your-deepseek-api-key",
    base_url="https://api.deepseek.com/v1"
)

# 加载工具定义
with open("agent/tool_manifest.json") as f:
    tools = json.load(f)["tools"]

# 加载系统提示词
with open("agent/system_prompt.md") as f:
    system_prompt = f.read()

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "帮我评估 E:\\test\\mydata 的质谱参数"}
    ],
    tools=tools
)

# 处理 tool_calls
for choice in response.choices:
    if choice.finish_reason == "tool_calls":
        for tool_call in choice.message.tool_calls:
            fn = tool_call.function
            if fn.name == "run_evaluation":
                args = json.loads(fn.arguments)
                result = subprocess.run(
                    ["python", "eval_ms_pipeline.py", args["dataset"]],
                    capture_output=True, text=True
                )
                # 将 result 返回给 DeepSeek 继续对话
```

### 方式 2：DeepSeek + LangChain

```python
from langchain.tools import tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI

@tool
def run_evaluation(dataset: str) -> str:
    """运行质谱参数评估流水线"""
    import subprocess
    result = subprocess.run(
        ["python", "eval_ms_pipeline.py", dataset],
        capture_output=True, text=True, cwd="/path/to/eval_ms_pipeline"
    )
    return result.stdout + result.stderr

@tool
def list_datasets() -> str:
    """列出已配置的数据集"""
    import subprocess
    result = subprocess.run(
        ["python", "-c",
         "from eval_ms_pipeline import DATASETS; print(list(DATASETS.keys()))"],
        capture_output=True, text=True, cwd="/path/to/eval_ms_pipeline"
    )
    return result.stdout

llm = ChatOpenAI(
    model="deepseek-chat",
    api_key="your-key",
    base_url="https://api.deepseek.com/v1"
)

tools = [run_evaluation, list_datasets]
agent = create_openai_tools_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 使用
result = executor.invoke({
    "input": "评估 E:\\test\\mydata 的质谱参数，用 Trypsin 搜库结果"
})
```

### 方式 3：直接 CLI（无 AI Agent）

```bash
# 无需 AI，直接运行
cd /path/to/eval_ms_pipeline
python eval_ms_pipeline.py mydata
```

## 工具定义说明 / Tool Manifest

`tool_manifest.json` 遵循 OpenAI function calling schema（DeepSeek 兼容）：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `run_evaluation` | 运行全流程评估 | `dataset`（必填）、`lang`（可选） |
| `add_dataset` | 添加数据集配置 | 全部配置字段 |
| `list_datasets` | 列出已配置数据集 | 无 |
| `detect_engine` | 自动检测搜索引擎 | `result_path` |
| `get_summary` | 读取评估结果汇总 | `dataset` |

## 常见问题 / FAQ

**Q: DeepSeek 无法执行 Python？**

A: DeepSeek API 只生成 tool_calls，实际执行在你的应用层。参考方式 1 的代码，用 `subprocess` 执行。

**Q: 如何自定义系统提示词？**

A: 编辑 `system_prompt.md`，添加你的特定指令（如数据路径约定、报告格式要求等）。

**Q: 支持其他 AI 框架吗？**

A: `tool_manifest.json` 兼容所有支持 OpenAI function calling 格式的框架（DeepSeek、Claude、GPT、通义千问等）。
