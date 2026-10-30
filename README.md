# eval_ms_pipeline

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![MSHub Plugin](https://img.shields.io/badge/MSHub-ms.s1.acquisition--eval-teal)](plugin.yaml)

---

## English

**MSHub capability pack** for mass spectrometry acquisition parameter evaluation.
Part of the [AI4MSOmics](https://github.com/AI4MSOmics) ecosystem.
See [MSHub](https://github.com/AI4MSOmics/MSHub) for the hub specification.

A configuration-driven pipeline that reads Thermo `.raw` files and search results from **11 engines**, producing per-group bilingual evaluation reports with method parameters, per-fraction QC, MIT distribution, cleavage QC, peptide FWHM, and enzyme autolysis annotation.

### Installation

```bash
git clone https://github.com/AI4MSOmics/eval_ms_pipeline_repo.git
cd eval_ms_pipeline_repo
bash install.sh
```

### Usage — three integration paths

#### 1. MSHub skill card

This repository follows the [MSHub plugin specification](https://github.com/AI4MSOmics/MSHub/blob/main/docs/03-plugin-spec.md). The [SKILL.md](SKILL.md) at the root is the MSHub-format skill card.

#### 2. ZCode / Claude / Cursor / DeepSeek skill

Copy `zcode/` to your agent's skills directory:

```bash
cp -r zcode/ ~/.zcode/skills/eval_ms_pipeline/
```

Or configure `agent/tool_manifest.json` for DeepSeek / OpenAI function calling (see [agent/deepseek_guide.md](agent/deepseek_guide.md)).

#### 3. Standalone CLI

```bash
python eval_ms_pipeline.py <dataset_name>
```

### Supported engines

| Engine | Input | Auto-detect | Cleavage QC | FWHM |
|--------|-------|:-----------:|:-----------:|:----:|
| pFind 3.x | `pFind-Filtered.spectra` | ✅ | ✅ native | .ms1 or rawdump |
| MaxQuant | `msms.txt` | ✅ | ✅ MC column | rawdump |
| Comet | `pep.txt` | ❌ | ✅ FASTA | rawdump |
| MSFragger | `.tsv` | ❌ | ✅ FASTA | rawdump |
| Sage | `results.sage.tsv` | ✅ | ✅ FASTA | rawdump |
| MetaMorpheus | `AllPeptides.psmtsv` | ✅ | ✅ MC column | rawdump |
| Mascot | `.csv` | ❌ | ✅ FASTA | rawdump |
| PEAKS | `.csv` | ❌ | ✅ FASTA | rawdump |
| pNovo | via isoPSV | ❌ | ✅ FASTA | rawdump |
| X!Tandem | via isoPSV | ❌ | ✅ FASTA | rawdump |
| isoPSV unified | adapter `.tsv` | ✅ | ✅ FASTA | rawdump |

### Key features

| Feature | Method | Verified on |
|---------|--------|-------------|
| Cleavage QC from FASTA | KR_N / KR_C rules, Met-cleavage aware | 99.71% specificity / 99.99% MC match vs pFind |
| Peptide FWHM (no .ms1) | `rawdump --xic` RAW direct-read | M. gastri, NTM (no .ms1 files) |
| MIT distribution | Per-CV histogram + saturation | NTM (93% saturation at MIT 22ms), M. gastri R2 (12.5% at 80ms) |
| Bilingual reports | Auto-detect from config text or `lang` field | M. gastri (zh + en) |
| Engine auto-detect | Column-fingerprint matching | 4 datasets, 13 groups, all correct |

### Documentation

| Document | Description |
|----------|-------------|
| [SKILL.md](SKILL.md) | MSHub skill card (agent-facing) |
| [docs/guide_en.md](docs/guide_en.md) | Detailed user guide (10 sections) |
| [docs/guide_zh.md](docs/guide_zh.md) | 中文详细使用指南 |
| [docs/configuration.md](docs/configuration.md) | Configuration reference |
| [docs/troubleshooting.md](docs/troubleshooting.md) | Troubleshooting |
| [plugin.yaml](plugin.yaml) | MSHub capability pack manifest |
| [schemas/](schemas/) | Input/output JSON Schemas |

### Related projects

- [MSHub](https://github.com/AI4MSOmics/MSHub) — Agent-native capability hub for MS proteomics
- [isoPSV](https://github.com/Songhao-Jiang/isoPSV) — Multi-engine competitive peptide spectrum matching

---

## 中文说明

**MSHub 能力包** — 质谱采集参数评估流水线。
隶属于 [AI4MSOmics](https://github.com/AI4MSOmics) 生态。
主仓规范见 [MSHub](https://github.com/AI4MSOmics/MSHub)。

配置驱动的评估流水线：输入 Thermo `.raw` 文件和 **11 种搜索引擎**的搜库结果，自动输出含 raw 内嵌方法参数、逐馏分质控、MIT 分布、酶切质控（特异性/漏切）、肽段半峰宽、酶自切肽标注的双语 Word 评估报告。

### 安装

```bash
git clone https://github.com/AI4MSOmics/eval_ms_pipeline_repo.git
cd eval_ms_pipeline_repo
bash install.sh
```

### 三种使用方式

#### 1. MSHub 能力包

本仓库遵循 [MSHub 插件规范](https://github.com/AI4MSOmics/MSHub/blob/main/docs/03-plugin-spec.md)。根目录的 [SKILL.md](SKILL.md) 为 MSHub 格式技能卡。

#### 2. ZCode / Claude / Cursor / DeepSeek 技能

```bash
cp -r zcode/ ~/.zcode/skills/eval_ms_pipeline/
```

或配置 `agent/tool_manifest.json` 接入 DeepSeek / OpenAI function calling（详见 [agent/deepseek_guide.md](agent/deepseek_guide.md)）。

#### 3. 命令行直接运行

```bash
python eval_ms_pipeline.py <数据集名>
```

### 支持的搜索引擎

| 引擎 | 结果文件 | 自动检测 | 酶切质控 | 半峰宽 |
|------|---------|:-------:|:-------:|:------:|
| pFind 3.x | `pFind-Filtered.spectra` | ✅ | ✅ 原生列 | .ms1 或 rawdump |
| MaxQuant | `msms.txt` | ✅ | ✅ 漏切列 | rawdump |
| Comet | `pep.txt` | ❌ | ✅ FASTA 补算 | rawdump |
| MSFragger | `.tsv` | ❌ | ✅ FASTA 补算 | rawdump |
| Sage | `results.sage.tsv` | ✅ | ✅ FASTA 补算 | rawdump |
| MetaMorpheus | `AllPeptides.psmtsv` | ✅ | ✅ 漏切列 | rawdump |
| Mascot | `.csv` | ❌ | ✅ FASTA 补算 | rawdump |
| PEAKS | `.csv` | ❌ | ✅ FASTA 补算 | rawdump |
| pNovo | 经 isoPSV 转换 | ❌ | ✅ FASTA 补算 | rawdump |
| X!Tandem | 经 isoPSV 转换 | ❌ | ✅ FASTA 补算 | rawdump |
| isoPSV 统一格式 | 适配器 `.tsv` | ✅ | ✅ FASTA 补算 | rawdump |

### 核心功能

| 功能 | 方法 | 验证结果 |
|------|------|---------|
| FASTA 补算酶切质控 | KR_N / KR_C 规则（含 Met 剪切位） | 特异性 99.71% / 漏切 99.99% 与 pFind 匹配 |
| 无 .ms1 文件时半峰宽 | `rawdump --xic` RAW 直读 | 胃分枝杆菌、NTM（均无 .ms1） |
| MIT 分布图 | 逐 CV 直方图 + 触顶率标注 | NTM 触顶 93%（MIT 22ms）、胃分枝杆菌 R2 仅 12.5%（80ms） |
| 中英文双语报告 | 从配置文字自动检测或 `lang` 字段指定 | 胃分枝杆菌（中英双版） |
| 引擎自动检测 | 列名指纹匹配 | 4 数据集 13 组全部正确 |

### 说明文档

| 文档 | 说明 |
|------|------|
| [SKILL.md](SKILL.md) | MSHub 技能卡（英文，面向 AI Agent） |
| [docs/guide_zh.md](docs/guide_zh.md) | 中文详细使用指南（10 节） |
| [docs/guide_en.md](docs/guide_en.md) | English detailed user guide |
| [docs/configuration.md](docs/configuration.md) | 配置参考（全部字段+正则模式） |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 排错指南（15 条常见问题） |
| [plugin.yaml](plugin.yaml) | MSHub 能力包清单 |
| [schemas/](schemas/) | 输入/输出 JSON Schema |

### 相关项目

- [MSHub](https://github.com/AI4MSOmics/MSHub) — 面向质谱蛋白质组学的 Agent 原生能力中枢
- [isoPSV](https://github.com/Songhao-Jiang/isoPSV) — 多引擎竞争性肽段谱图匹配平台

---

## License / 许可证

Apache-2.0. See [LICENSE](LICENSE).
