# eval_ms_pipeline

**质谱采集参数评估流水线 / Mass spectrometry acquisition parameter evaluation pipeline**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Engines: 11](https://img.shields.io/badge/Engines-11-blue)](#supported-engines)
[![Languages: zh/en](https://img.shields.io/badge/Reports-zh%2Fen-green)](#bilingual)

一个 GitHub 项目，两种 AI 代理集成方式（ZCode skill + DeepSeek/通用 agent tool），同一条命令出全流程质谱参数评估报告。

One GitHub project, two AI agent integrations (ZCode skill + DeepSeek/universal agent tool), one command for full MS parameter evaluation reports.

## 安装 / Install

```bash
git clone https://github.com/your-username/eval_ms_pipeline.git
cd eval_ms_pipeline
bash install.sh
```

## 两种使用方式 / Two Integration Paths

### 方式 1：ZCode Skill

```bash
# 将 zcode/ 目录复制到 ZCode skills 目录
cp -r zcode/ ~/.zcode/skills/eval_ms_pipeline/

# 在 ZCode 中直接对话使用
# "帮我评估 E:\test\mydata 的质谱参数"
# ZCode 会自动识别 skill 并调用流水线
```

详见 [zcode/SKILL.md](zcode/SKILL.md)

### 方式 2：DeepSeek / 通用 AI Agent

```bash
# 将 agent/tool_manifest.json 配置到你的 AI 代理框架
# 将 agent/system_prompt.md 设为系统提示词
# 代理即可调用 eval_ms_pipeline 工具
```

详见 [agent/deepseek_guide.md](agent/deepseek_guide.md)

### 方式 3：直接运行（无需 AI）

```bash
python eval_ms_pipeline.py mydata
```

## 功能 / Features

| 功能 | 方法 | 依赖 |
|------|------|------|
| raw 内嵌方法提取 | rawmethod.exe → ExportInstrumentMethod | Thermo .raw |
| 逐扫描采集参数 | rawdump.exe → IT/AGC/TIC/CV/master_scan | Thermo .raw |
| TopN/AGC Fill/解析率 | 主洗脱段 [25%–90%] 统计 | rawdump 输出 |
| MIT 分布 | 逐 CV 直方图 + 触顶率 | rawdump 输出 |
| 酶切特异性/漏切 | 引擎原生列或 FASTA 补算 | 搜库结果 (+ FASTA) |
| 肽段半峰宽 | .ms1 XIC 或 rawdump --xic RAW 直读 | .ms1 或 rawdump |
| 酶自切肽 BPC | XIC apex 标注 | 搜库结果 + 酶蛋白 ID |
| 中英文双语报告 | 自动检测或 lang 字段 | 无 |

## Supported Engines / 支持的搜索引擎

| Engine | Result file | Auto-detect | Cleavage QC |
|--------|------------|-------------|-------------|
| pFind 3.x | `pFind-Filtered.spectra` | ✅ | ✅ Native |
| MaxQuant | `msms.txt` | ✅ | ✅ MC column |
| Comet | `pep.txt` | ❌ | ✅ Via FASTA |
| MSFragger | `.tsv` | ❌ | ✅ Via FASTA |
| Sage | `results.sage.tsv` | ✅ | ✅ Via FASTA |
| MetaMorpheus | `AllPeptides.psmtsv` | ✅ | ✅ MC column |
| Mascot | `.csv` | ❌ | ✅ Via FASTA |
| PEAKS | `.csv` | ❌ | ✅ Via FASTA |
| pNovo | via isoPSV | ❌ | ✅ Via FASTA |
| X!Tandem | via isoPSV | ❌ | ✅ Via FASTA |
| isoPSV unified | adapter `.tsv` | ✅ | ✅ Via FASTA |

## Quick Start / 快速开始

### 1. 添加配置

```python
# 在 eval_ms_pipeline.py 的 DATASETS 中添加
DATASETS['mydata'] = dict(
    out=r'E:\test\mydata\output',
    groups={
        'mygroup': dict(
            label='mygroup (sample description)',
            enz='Trypsin (KR_C)',
            color='tab:blue',
            cv_colors={'45V': 'tab:red', '65V': 'tab:orange'},
            cv_off={'45V': -1, '65V': 1},
            datadir=r'E:\test\mydata\raw',
            result=r'E:\test\mydata\pfind\result',
            frac_pat=r'_F(\d+)_90min',
            id_pat=r'_F(\d+)_90min',
            autol_pat='TRYP_PIG|TRY1_BOVIN',
            autol_cn='enzyme autolysis peptides',
            # Optional
            # engine='maxquant',           # or 'sage', 'comet', etc.
            # fasta='protein.fasta',       # triggers cleavage QC computation
            # enz_rule='KR_C',             # or 'KR_N' for LysargiNase
            # lang='en',                   # or 'zh' for Chinese report
        ),
    })
```

### 2. 运行

```bash
python eval_ms_pipeline.py mydata
```

### 3. 查看输出

```
output/
├── mygroup_ms_parameter_report.docx   # 5-section report
├── method_mygroup.tsv
├── group_summary.tsv
├── figs_frac/
├── figs_summary/
└── figs_BPC/
```

## Documentation / 说明文档

| 文档 | 语言 | 内容 |
|------|------|------|
| [docs/guide_zh.md](docs/guide_zh.md) | 中文 | 详细使用指南（10 节） |
| [docs/guide_en.md](docs/guide_en.md) | English | Detailed user guide (10 sections) |
| [docs/configuration.md](docs/configuration.md) | 双语 | 配置参考 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 双语 | 排错指南 |

## Related Projects / 相关项目

- [isoPSV](https://github.com/Songhao-Jiang/isoPSV) — Multi-engine competitive peptide spectrum matching platform

## Project Structure / 项目结构

```
eval_ms_pipeline/
├── README.md                    # This file
├── LICENSE                      # MIT
├── install.sh                   # One-command installer
│
├── eval_ms_pipeline.py          # Main pipeline (single file, ~1300 lines)
├── xic_raw.py                   # rawdump --xic Python wrapper
│
├── zcode/                       # ZCode Skill integration
│   └── SKILL.md                 # YAML frontmatter + usage instructions
│
├── agent/                       # AI Agent integration (DeepSeek, Claude, etc.)
│   ├── tool_manifest.json       # OpenAI function calling schema
│   ├── system_prompt.md         # System prompt for AI agents
│   └── deepseek_guide.md        # DeepSeek-specific setup guide
│
├── tools/                       # Prebuilt binary tools
│   ├── rawdump.exe              # Scan dump + XIC mode
│   └── rawmethod.exe            # Raw method extraction
│
├── src/                         # C# source (for rebuilding)
│   ├── rawdump/
│   └── rawmethod/
│
├── docs/                        # Documentation
│   ├── guide_zh.md              # 中文指南
│   ├── guide_en.md              # English guide
│   ├── configuration.md         # Config reference
│   └── troubleshooting.md       # Troubleshooting
│
└── examples/                    # Configuration examples
    ├── config_mga.py            # FAIMS dual-CV
    ├── config_ntm.py            # Multi-group + enzyme mini-DB
    └── config_913.py            # QE HF, .ms1 XIC
```

## License

MIT
