# eval_ms_pipeline 中文使用指南

## 目录

1. [概述](#1-概述)
2. [安装](#2-安装)
3. [快速开始](#3-快速开始)
4. [配置详解](#4-配置详解)
5. [搜索引擎](#5-搜索引擎)
6. [酶切质控](#6-酶切质控)
7. [半峰宽计算](#7-半峰宽计算)
8. [中英文双语](#8-中英文双语)
9. [输出说明](#9-输出说明)
10. [常见问题](#10-常见问题)

---

## 1. 概述

eval_ms_pipeline 是一套配置驱动的质谱采集参数评估流水线，输入 Thermo raw 文件和搜库结果（支持 11 种搜索引擎），输出含以下内容的 Word 报告：

- **raw 内嵌方法参数**：分辨率、AGC 目标、MIT、cycle time、NCE、FAIMS CV
- **逐馏分质控**：TopN、AGC Fill、注入时间、rank 分布（限主洗脱段 25%–90%）
- **MS2 注入时间（MIT）分布**：逐 CV 直方图 + 触顶率标注
- **鉴定质控**：酶切特异性、全酶切比例、漏切分布（PSM 与肽段两级）
- **肽段半峰宽（FWHM）**：.ms1 XIC 或 rawdump RAW 直读（口径一致）
- **酶自切肽 BPC 标注**：XIC apex 精确定位
- **组级汇总**：跨组对比 TSV

## 2. 安装

### 2.1 Python 依赖

```bash
pip install numpy pandas matplotlib python-docx
```

### 2.2 预编译工具

`rawdump_bin/` 和 `rawmethod_tool/` 目录已包含预编译的 Windows x64 二进制，无需额外安装。

如需从源码编译 rawdump（添加了 `--xic` 模式）：

```bash
cd rawdump
dotnet build rawdump.csproj -c Debug
```

依赖 .NET Core 3.1 runtime 和 ThermoFisher RawFileReader DLL。

### 2.3 快速安装（从源码目录）

```bash
bash setup.sh /path/to/analysis_scripts
```

## 3. 快速开始

### 3.1 添加数据集配置

在 `eval_ms_pipeline.py` 的 `DATASETS` 字典中添加条目：

```python
DATASETS['mydata'] = dict(
    out=r'E:\test\mydata\评估产出',
    groups={
        'mygroup': dict(
            label='mygroup（样品描述）',          # 报告标题中显示
            enz='Trypsin（KR_C）',               # 酶描述
            color='tab:blue',                    # matplotlib 颜色
            cv_colors={'45V': 'tab:red', '65V': 'tab:orange'},  # CV 颜色
            cv_off={'45V': -1, '65V': 1},        # CV 绘图偏移
            datadir=r'E:\test\mydata\raw',        # raw 文件目录
            result=r'E:\test\mydata\pfind\result', # 搜库结果目录
            frac_pat=r'_F(\d+)_90min',           # 馏分号提取正则
            id_pat=r'_F(\d+)_90min',             # 鉴定结果匹配正则
            autol_pat='TRYP_PIG|TRY1_BOVIN',     # 酶蛋白 ID 模式
            autol_cn='蛋白酶自切肽',               # 自切肽中文标签
        ),
    })
```

### 3.2 运行

```bash
python eval_ms_pipeline.py mydata
```

### 3.3 查看输出

输出在 `DATASETS['mydata']['out']` 指定的目录：

```
评估产出/
├── mygroup_质谱参数评估报告.docx     # 主报告
├── 方法提取_mygroup.tsv              # raw 内嵌方法参数
├── 鉴定明细_逐馏分_mygroup.tsv       # 逐馏分鉴定量
├── 组级汇总.tsv                     # 跨组汇总
├── figs_逐馏分/                     # 逐馏分四联图
├── figs_汇总/                       # 汇总图（TopN/AGC/FWHM/MIT）
└── figs_BPC/                        # BPC 自切肽标注
```

## 4. 配置详解

### 4.1 必填字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `label` | str | 组标签（显示在报告标题），含中文→中文报告 | `'Mga_LL（胃分枝杆菌）'` |
| `enz` | str | 酶切描述 | `'LysargiNase+LysN 混合酶切'` |
| `color` | str | 组主色 | `'tab:red'` |
| `datadir` | str | raw 文件目录（绝对路径） | `r'E:\test\mydata\raw'` |
| `result` | str | 搜库结果（文件或目录） | `r'E:\test\mydata\result'` |
| `frac_pat` | str | 馏分号正则（作用于 raw 文件名去扩展名） | `r'_F(\d+)_90min'` |
| `id_pat` | str | 鉴定匹配正则（作用于 File_Name） | `r'_F(\d+)_(\d+)V'` |
| `autol_pat` | str | 酶蛋白 ID 正则 | `'CON_LysargiNase'` |
| `autol_cn` | str | 自切肽中文标签 | `'LysargiNase 酶自切肽'` |
| `cv_colors` | dict | CV→颜色映射 | `{'45V': 'tab:red'}` |
| `cv_off` | dict | CV→偏移映射 | `{'45V': -1, '65V': 1}` |

### 4.2 可选字段

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `engine` | `'pfind'` | 搜索引擎（见第 5 节） |
| `lang` | 自动检测 | `'zh'` 或 `'en'`（见第 8 节） |
| `has_ms1` | `False` | `True` 启用 .ms1 XIC 半峰宽 |
| `dump_all` | `False` | `True` 处理目录内全部 raw（不限 CV 后缀） |
| `instrument` | `'Orbitrap Exploris 480'` | 仪器描述 |
| `eval_date` | `'2026-10-17'` | 评估日期 |
| `fasta` | 无 | 蛋白库 FASTA（触发酶切质控补算） |
| `enz_rule` | 自动推断 | `'KR_N'` 或 `'KR_C'` |
| `main_win` | `(0.25, 0.90)` | 主洗脱段窗口（运行时长百分比） |
| `conclusion_ms` | 默认结论 | 自定义结论段落 |
| `enz_extra` | 无 | 酶小库搜库结果路径列表 |
| `raw_filter` | 无 | raw 文件名子串过滤（单针模式） |
| `topn_cap` | 25 | TopN 图 rank 上限 |

### 4.3 正则模式速查

**`frac_pat`**——从 raw 文件名提取馏分编号（第 1 组须为整数）：

| 数据命名 | 文件名示例 | `frac_pat` | 提取 |
|----------|-----------|-----------|------|
| Mixture_N | `..._Mixture_3_45V` | `r'_Mixture_(\d+)'` | 3 |
| F 编号 | `..._F05_90min` | `r'_F(\d+)_90min'` | 5 |
| R 编号 | `..._R1_45V` | `r'_R(\d)_(\d+)V'` | 1 |
| QE 单针 | `..._Mab_ELU` | `None`（单针模式） | — |

**`id_pat`**——从 File_Name 提取（馏分号, CV 值）：

| 数据命名 | File_Name 示例 | `id_pat` | 提取 |
|----------|---------------|---------|------|
| NTM | `..._Mixture_3_45V.12345...` | `r'_Mixture_(\d+)_(\d+)V'` | (3, '45') |
| 913 | `..._F05_90min.12345...` | `r'_F(\d+)_90min'` | (5)——单 CV |
| Mga | `..._R1_45V.24045...` | `r'_R(\d)_(\d+)V'` | (1, '45') |

## 5. 搜索引擎

### 5.1 引擎列表

| 引擎 | 结果文件 | 自动检测 | 特异性 | 漏切 | m/z 来源 |
|------|---------|---------|--------|------|---------|
| **pFind** | `pFind-Filtered.spectra` | ✅ | ✅ 原生列 | ✅ 原生列 | Calc.MH+ 直读 |
| **MaxQuant** | `msms.txt` | ✅ | — | ✅ Missed cleavages | m/z×z 反算 |
| **Comet** | `pep.txt` | ❌ | ✅ FASTA 补算 | ✅ FASTA | 序列计算 |
| **MSFragger** | `.tsv` | ❌ | ✅ FASTA | ✅ FASTA | 序列计算 |
| **Sage** | `results.sage.tsv` | ✅ | ✅ FASTA | ✅ FASTA | 序列计算 |
| **MetaMorpheus** | `AllPeptides.psmtsv` | ✅ | — | ✅ 原生列 | 序列计算 |
| **Mascot** | `.csv` | ❌ | ✅ FASTA | ✅ FASTA | 序列计算 |
| **PEAKS** | `.csv` | ❌ | ✅ FASTA | ✅ FASTA | 序列计算 |
| **pNovo** | `.res` | ❌ | ✅ FASTA | ✅ FASTA | — |
| **X!Tandem** | XML | ❌ | ✅ FASTA | ✅ FASTA | — |
| **isoPSV unified** | 适配器 `.tsv` | ✅ | ✅ FASTA | ✅ FASTA | 序列计算 |

### 5.2 配置方式

```python
# 方式 1：自动检测（推荐，引擎结果有标准表头时）
result=r'E:\test\mydata\result'  # 目录或文件

# 方式 2：手动指定
engine='sage'
result=r'E:\test\mydata\results.sage.tsv'

# 方式 3：isoPSV 适配器输出
engine='isopsv'
result=r'E:\test\mydata\adapter_output.tsv'
```

### 5.3 非 pFind 引擎的差异

| 项目 | pFind | 其他引擎 |
|------|-------|---------|
| 解析率 | pFind.summary（搜库引擎口径） | rawdump 整针口径（鉴定 MS2/全部 MS2） |
| 特异性 | Specificity 列直读 | FASTA 补算或显示"—" |
| 漏切 | Miss.Clv.Sites 列直读 | FASTA 补算或引擎原生列 |
| 酶自切 | Proteins 列匹配 autol_pat | 同左（格式统一后兼容） |

## 6. 酶切质控

### 6.1 从 FASTA 补算（推荐）

当引擎不提供特异性/漏切列时（Comet/MSFragger/Sage/Mascot/PEAKS），配置蛋白库即可自动补算：

```python
'fasta': r'E:\test\mydata\protein.fasta',  # 蛋白库
'enz_rule': 'KR_N',                        # LysargiNase/Lys-N
# 或 'KR_C'                                # Trypsin/Lys-C
```

**计算规则**：

| 规则 | KR_N（LysargiNase） | KR_C（Trypsin） |
|------|--------------------|--------------------|
| N 端特异性 | 肽段首残基 K/R，或蛋白 N 端（含 Met 剪切） | 前一残基 K/R，或蛋白 N 端 |
| C 端特异性 | 后一残基 K/R，或蛋白 C 端 | 肽段末残基 K/R，或蛋白 C 端 |
| 漏切 | peptide[1:] 中 K/R 数 | peptide[:-1] 中 K/R 数 |

**验证精度**（M. gastri 28,504 PSM 对照 pFind 真值）：
- 特异性匹配率 **99.71%**
- 漏切匹配率 **99.99%**

### 6.2 酶小库搜库（库内无酶条目时）

参考 proteome 缺少酶蛋白条目的物种（如非模式生物），需用酶小库单独搜库：

```python
# 1. 创建仅含酶序列的 FASTA（如 Sl_LysN_LysargiNase.fasta）
# 2. pFind 搜库（datalist 指向 mgf 文件）
# 3. 配置合并
'enz_extra': [r'E:\test\mydata\enzyme_search\result\pFind-Filtered.spectra']
```

## 7. 半峰宽计算

| 条件 | 方法 | 来源标签 |
|------|------|---------|
| `has_ms1=True` | `.ms1` 文件 XIC 流式读取 | `ms1` |
| `has_ms1=False`（默认） | `rawdump --xic` RAW 直读 | `rawdump-xic` |

两种方法口径完全一致：
- ±0.02 Da 质量窗口，取窗内最强峰
- 半高线性插值计算 FWHM
- 4–240 s 有效门（排除噪声和超宽峰）
- 搜索窗口 ±2.5 min

**rawdump --xic 的优势**：无需预处理（xtract 提取 .ms1），直接读 RAW 原文件，任何 Thermo 数据通用。

## 8. 中英文双语

### 8.1 自动检测

系统扫描组条目的 `label`、`enz`、`autol_cn`、`instrument` 四个字段：
- 任一字段含中文字符 → 输出中文报告
- 全部纯英文 → 输出英文报告

### 8.2 显式指定

```python
'lang': 'zh'  # 强制中文
'lang': 'en'  # 强制英文
```

### 8.3 输出差异

| 项目 | 中文版 | 英文版 |
|------|--------|--------|
| 文件名 | `_质谱参数评估报告.docx` | `_ms_parameter_report.docx` |
| 标题 | 质谱参数评估报告 | MS Parameter Evaluation Report |
| 章节 | 一、raw 内嵌方法参数 | 1. Raw-Embedded Method Parameters |
| 表头 | 馏分/PSM 数/肽段数 | Fraction/PSM Count/Peptide Count |
| 质控表 | 完全特异性/全酶切 | Fully Specific/Fully Cleaved |

### 8.4 注意事项

`instrument` 和 `autol_cn` 字段的默认值含中文（如 `'480（FAIMS 双 CV）'`），英文数据集需：
1. 显式设 `'lang': 'en'`（最可靠），或
2. 将 `instrument` 和 `autol_cn` 也改为英文

## 9. 输出说明

### 9.1 报告结构（5 节）

| 节 | 内容 |
|----|------|
| 一 | raw 内嵌方法参数（分辨率/AGC/MIT/Cycle/NCE/CV） |
| 二 | 逐馏分质控表（TopN/解析率/IT 触顶/Fill 中位） |
| 三 | 鉴定结果 + 鉴定质控（特异性/漏切/逐 CV） |
| 四 | 结论（自动生成或 `conclusion_ms` 自定义） |
| 五 | 汇总图（TopN/AGC/FWHM/MIT 分布） |

### 9.2 汇总图列表

| 图名 | 文件名模式 | 说明 |
|------|-----------|------|
| TopN 解析率汇总 | `*_fig_TopN解析率汇总.png` | 各馏分细线 + 合并粗线 |
| AGC Fill 汇总 | `*_fig_AGC_Fill汇总.png` | rank×CV 箱线图 |
| 解析率随 RT | `*_fig_解析率随RT汇总.png` | 5 min 箱，分 CV |
| MIT 分布 | `*_fig_MIT分布.png` | 逐 CV IT 直方图 + MIT 线 |
| 半峰宽汇总 | `*_fig_半峰宽汇总.png` | 合并分布 + 逐馏分中位 |

### 9.3 组级汇总 TSV 列

| 列名 | 说明 |
|------|------|
| 组 | 组标签 |
| 馏分数 | 馏分/进样数量 |
| TopN均值@CV | 逐 CV TopN 均值 |
| 解析率范围@CV | 逐 CV 解析率范围 |
| 触顶均值%@CV | 逐 CV IT 触顶比例 |
| PSM/肽段/蛋白 | 鉴定量 |
| Overall解析率% | 全谱解析率 |
| 完全特异性% | PSM 级特异性 |
| 全酶切% | PSM 级 0 漏切比例 |

## 10. 常见问题

**Q: raw 文件目录内有多个 raw，但只有一个馏分，怎么配？**

A: 设 `frac_pat=None, id_pat=None`（单针模式），所有 raw 合并为 F1。

**Q: 解析率显示 0%？**

A: 检查 `id_pat` 正则是否匹配 File_Name。用 Python 测试：
```python
import re; print(re.search(pat, File_Name_example))
```

**Q: 酶自切肽没有标注？**

A: 两个可能原因：
1. 蛋白库无酶条目 → 需酶小库搜库，通过 `enz_extra` 合并
2. `autol_pat` 不匹配 → 检查蛋白 ID 格式

**Q: MIT 分布图没有显示？**

A: 检查方法提取结果是否含 `CV-45:...:MS2_IT22:...` 段。QE XML 方法用 `Max_inject_time`。

**Q: 英文报告还是中文？**

A: `instrument` 或 `autol_cn` 字段可能含中文字符。显式设 `'lang': 'en'`。

---

> 更多技术细节见 [configuration.md](configuration.md)（配置参考）和 [troubleshooting.md](troubleshooting.md)（排错指南）。
