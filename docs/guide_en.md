# eval_ms_pipeline English User Guide

## Table of Contents

1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Configuration Reference](#4-configuration-reference)
5. [Search Engines](#5-search-engines)
6. [Cleavage QC](#6-cleavage-qc)
7. [Peak Width (FWHM)](#7-peak-width-fwhm)
8. [Bilingual Output](#8-bilingual-output)
9. [Output Description](#9-output-description)
10. [FAQ](#10-faq)

---

## 1. Overview

eval_ms_pipeline is a configuration-driven mass spectrometry acquisition parameter evaluation pipeline. Given Thermo raw files and search results (from 11 supported engines), it produces Word reports containing:

- **Raw-embedded method parameters**: resolution, AGC target, MIT, cycle time, NCE, FAIMS CV
- **Per-fraction QC**: TopN, AGC Fill, injection time, rank distribution (main elution window 25%–90%)
- **MS2 injection time (MIT) distribution**: per-CV histogram with saturation annotation
- **Identification QC**: cleavage specificity, fully-cleaved fraction, missed-cleavage distribution (PSM & peptide level)
- **Peptide peak width (FWHM)**: via `.ms1` XIC or `rawdump --xic` RAW direct-read (same calibration)
- **Enzyme autolysis BPC annotation**: XIC apex positioning
- **Cross-group summary**: comparative TSV

## 2. Installation

### 2.1 Python Dependencies

```bash
pip install numpy pandas matplotlib python-docx
```

### 2.2 Prebuilt Tools

`rawdump_bin/` and `rawmethod_tool/` contain prebuilt Windows x64 binaries. No additional installation needed.

To rebuild rawdump from source (includes `--xic` mode):

```bash
cd rawdump
dotnet build rawdump.csproj -c Debug
```

Requires .NET Core 3.1 runtime and ThermoFisher RawFileReader DLL.

### 2.3 Quick Install (from source directory)

```bash
bash setup.sh /path/to/analysis_scripts
```

## 3. Quick Start

### 3.1 Add Dataset Configuration

Add an entry to the `DATASETS` dict in `eval_ms_pipeline.py`:

```python
DATASETS['mydata'] = dict(
    out=r'E:\test\mydata\output',
    groups={
        'mygroup': dict(
            label='mygroup (sample description)',  # shown in report title
            enz='Trypsin (KR_C)',                  # enzyme description
            color='tab:blue',                      # matplotlib color
            cv_colors={'45V': 'tab:red', '65V': 'tab:orange'},  # CV colors
            cv_off={'45V': -1, '65V': 1},          # CV plot offsets
            datadir=r'E:\test\mydata\raw',           # raw file directory
            result=r'E:\test\mydata\pfind\result',   # search results
            frac_pat=r'_F(\d+)_90min',              # fraction number regex
            id_pat=r'_F(\d+)_90min',                # ID matching regex
            autol_pat='TRYP_PIG|TRY1_BOVIN',        # enzyme protein pattern
            autol_cn='enzyme autolysis peptides',    # autolysis label
        ),
    })
```

### 3.2 Run

```bash
python eval_ms_pipeline.py mydata
```

### 3.3 View Output

Output in the `DATASETS['mydata']['out']` directory:

```
output/
├── mygroup_ms_parameter_report.docx   # main report
├── method_mygroup.tsv                 # raw method parameters
├── identification_per_fraction_mygroup.tsv
├── group_summary.tsv                  # cross-group summary
├── figs_frac/                         # per-fraction 4-panel figures
├── figs_summary/                      # summary figures (TopN/AGC/FWHM/MIT)
└── figs_BPC/                          # BPC with autolysis annotation
```

## 4. Configuration Reference

### 4.1 Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `label` | str | Group label (shown in report title); Chinese→Chinese report | `'Mga_LL (M. gastri)'` |
| `enz` | str | Enzyme description | `'LysargiNase+LysN mixed digestion'` |
| `color` | str | Group primary color | `'tab:red'` |
| `datadir` | str | Raw file directory (absolute path) | `r'E:\test\mydata\raw'` |
| `result` | str | Search results (file or directory) | `r'E:\test\mydata\result'` |
| `frac_pat` | str | Fraction regex (on raw filename stem) | `r'_F(\d+)_90min'` |
| `id_pat` | str | ID matching regex (on File_Name) | `r'_F(\d+)_(\d+)V'` |
| `autol_pat` | str | Enzyme protein ID regex | `'CON_LysargiNase'` |
| `autol_cn` | str | Autolysis label | `'LysargiNase autolysis'` |
| `cv_colors` | dict | CV→color mapping | `{'45V': 'tab:red'}` |
| `cv_off` | dict | CV→offset mapping | `{'45V': -1, '65V': 1}` |

### 4.2 Optional Fields

| Field | Default | Description |
|-------|---------|-------------|
| `engine` | `'pfind'` | Search engine (see Section 5) |
| `lang` | auto | `'zh'` or `'en'` (see Section 8) |
| `has_ms1` | `False` | `True` enables .ms1 XIC for FWHM |
| `dump_all` | `False` | `True` processes all .raw in dir |
| `instrument` | `'Orbitrap Exploris 480'` | Instrument description |
| `eval_date` | `'2026-10-17'` | Evaluation date |
| `fasta` | None | Protein database (triggers cleavage QC computation) |
| `enz_rule` | auto | `'KR_N'` or `'KR_C'` |
| `main_win` | `(0.25, 0.90)` | Main elution window (% of run) |
| `conclusion_ms` | default | Custom conclusion paragraph |
| `enz_extra` | None | Enzyme mini-DB search result paths |
| `raw_filter` | None | Raw filename substring filter (single-needle mode) |
| `topn_cap` | 25 | TopN figure rank limit |

### 4.3 Regex Pattern Reference

**`frac_pat`** — extract fraction number from raw filename (group 1 must be integer):

| Naming | Example filename | `frac_pat` | Extracts |
|--------|-----------------|-----------|----------|
| Mixture_N | `..._Mixture_3_45V` | `r'_Mixture_(\d+)'` | 3 |
| F number | `..._F05_90min` | `r'_F(\d+)_90min'` | 5 |
| R number | `..._R1_45V` | `r'_R(\d)_(\d+)V'` | 1 |
| QE single | `..._Mab_ELU` | `None` (single-needle) | — |

**`id_pat`** — extract (fraction, CV) from File_Name:

| Naming | File_Name example | `id_pat` | Extracts |
|--------|-------------------|---------|----------|
| NTM | `..._Mixture_3_45V.12345...` | `r'_Mixture_(\d+)_(\d+)V'` | (3, '45') |
| 913 | `..._F05_90min.12345...` | `r'_F(\d+)_90min'` | (5) — single CV |
| Mga | `..._R1_45V.24045...` | `r'_R(\d)_(\d+)V'` | (1, '45') |

## 5. Search Engines

### 5.1 Supported Engines

| Engine | Result file | Auto-detect | Specificity | Missed clv | m/z source |
|--------|------------|-------------|-------------|------------|------------|
| **pFind** | `pFind-Filtered.spectra` | ✅ | ✅ Native | ✅ Native | Calc.MH+ |
| **MaxQuant** | `msms.txt` | ✅ | — | ✅ Missed cleavages | m/z×z |
| **Comet** | `pep.txt` | ❌ | ✅ Via FASTA | ✅ Via FASTA | Sequence |
| **MSFragger** | `.tsv` | ❌ | ✅ Via FASTA | ✅ Via FASTA | Sequence |
| **Sage** | `results.sage.tsv` | ✅ | ✅ Via FASTA | ✅ Via FASTA | Sequence |
| **MetaMorpheus** | `AllPeptides.psmtsv` | ✅ | — | ✅ Native | Sequence |
| **Mascot** | `.csv` | ❌ | ✅ Via FASTA | ✅ Via FASTA | Sequence |
| **PEAKS** | `.csv` | ❌ | ✅ Via FASTA | ✅ Via FASTA | Sequence |
| **pNovo** | `.res` (via isoPSV) | ❌ | ✅ Via FASTA | ✅ Via FASTA | — |
| **X!Tandem** | XML (via isoPSV) | ❌ | ✅ Via FASTA | ✅ Via FASTA | — |
| **isoPSV unified** | adapter `.tsv` | ✅ | ✅ Via FASTA | ✅ Via FASTA | Sequence |

### 5.2 Configuration

```python
# Option 1: auto-detect (recommended for engines with standard headers)
result=r'E:\test\mydata\result'  # directory or file

# Option 2: explicit engine
engine='sage'
result=r'E:\test\mydata\results.sage.tsv'

# Option 3: isoPSV adapter output
engine='isopsv'
result=r'E:\test\mydata\adapter_output.tsv'
```

### 5.3 Non-pFind Engine Differences

| Item | pFind | Other engines |
|------|-------|---------------|
| ID rate | pFind.summary (search engine denominator) | rawdump denominator (ID MS2 / total MS2) |
| Specificity | Specificity column | FASTA computation or "—" |
| Missed cleavages | Miss.Clv.Sites column | FASTA computation or engine native |
| Autolysis | Proteins column matching autol_pat | Same (unified format) |

## 6. Cleavage QC

### 6.1 FASTA Computation (Recommended)

When the engine doesn't provide specificity/missed-cleavage columns, configure a protein database for automatic computation:

```python
'fasta': r'E:\test\mydata\protein.fasta',  # protein database
'enz_rule': 'KR_N',                        # LysargiNase/Lys-N
# or 'KR_C'                                # Trypsin/Lys-C
```

**Computation rules**:

| Rule | KR_N (LysargiNase) | KR_C (Trypsin) |
|------|--------------------|--------------------|
| N-term specific | First residue K/R, or protein N-term (incl. Met cleavage) | Preceding residue K/R, or protein N-term |
| C-term specific | Next residue K/R, or protein C-term | Last residue K/R, or protein C-term |
| Missed cleavages | K/R count in peptide[1:] | K/R count in peptide[:-1] |

**Validation accuracy** (M. gastri 28,504 PSM vs pFind ground truth):
- Specificity match: **99.71%**
- Missed cleavage match: **99.99%**

### 6.2 Enzyme Mini-DB Search (When Reference Lacks Enzyme Entries)

For species whose reference proteome lacks enzyme protein entries:

```python
# 1. Create a mini FASTA with only enzyme sequences
# 2. Search with pFind against this mini database
# 3. Merge results
'enz_extra': [r'E:\test\mydata\enzyme_search\result\pFind-Filtered.spectra']
```

## 7. Peak Width (FWHM)

| Condition | Method | Source label |
|-----------|--------|-------------|
| `has_ms1=True` | `.ms1` file XIC streaming | `ms1` |
| `has_ms1=False` (default) | `rawdump --xic` RAW direct-read | `rawdump-xic` |

Both methods use identical calibration:
- ±0.02 Da mass window, max peak within window
- Half-max linear interpolation for FWHM
- 4–240 s validity gate (excludes noise and ultra-wide peaks)
- ±2.5 min search window

**rawdump --xic advantage**: no preprocessing needed (no xtract .ms1 extraction), reads RAW files directly, works with any Thermo data.

## 8. Bilingual Output

### 8.1 Auto-detection

The system scans `label`, `enz`, `autol_cn`, and `instrument` fields:
- Any field contains Chinese characters → Chinese report
- All fields pure English → English report

### 8.2 Explicit Override

```python
'lang': 'zh'  # force Chinese
'lang': 'en'  # force English
```

### 8.3 Output Differences

| Item | Chinese | English |
|------|---------|---------|
| Filename | `_质谱参数评估报告.docx` | `_ms_parameter_report.docx` |
| Title | 质谱参数评估报告 | MS Parameter Evaluation Report |
| Sections | 一、raw 内嵌方法参数 | 1. Raw-Embedded Method Parameters |
| Table headers | 馏分/PSM 数/肽段数 | Fraction/PSM Count/Peptide Count |
| QC table | 完全特异性/全酶切 | Fully Specific/Fully Cleaved |

### 8.4 Important Note

Default `instrument` and `autol_cn` values contain Chinese. For English datasets, either:
1. Explicitly set `'lang': 'en'` (most reliable), or
2. Change `instrument` and `autol_cn` to English text

## 9. Output Description

### 9.1 Report Structure (5 sections)

| Section | Content |
|---------|---------|
| 1 | Raw-embedded method parameters (Resolution/AGC/MIT/Cycle/NCE/CV) |
| 2 | Per-fraction QC table (TopN/ID rate/IT saturation/Fill median) |
| 3 | Identification results + QC (Specificity/MC/per-CV) |
| 4 | Conclusions (auto-generated or custom `conclusion_ms`) |
| 5 | Summary figures (TopN/AGC/FWHM/MIT distribution) |

### 9.2 Summary Figures

| Figure | Filename pattern | Description |
|--------|-----------------|-------------|
| TopN ID Rate | `*_fig_TopN_rate_summary.png` | Per-fraction thin + merged bold |
| AGC Fill | `*_fig_AGC_Fill_summary.png` | rank×CV boxplot |
| ID Rate vs RT | `*_fig_rate_vs_RT_summary.png` | 5 min bins, by CV |
| MIT Distribution | `*_fig_MIT_dist.png` | Per-CV IT histogram + MIT line |
| FWHM Summary | `*_fig_FWHM_summary.png` | Combined distribution + per-fraction median |

### 9.3 Group Summary TSV Columns

| Column | Description |
|--------|-------------|
| Group | Group label |
| Fractions | Number of fractions/injections |
| TopN_mean@CV | Per-CV mean TopN |
| ID_rate_range@CV | Per-CV ID rate range |
| IT_sat_mean%@CV | Per-CV IT saturation percentage |
| PSM/Peptide/Protein | Identification counts |
| Overall_ID_rate% | Overall spectrum ID rate |
| Fully_specific% | PSM-level specificity |
| Fully_cleaved% | PSM-level 0-MC fraction |

## 10. FAQ

**Q: Multiple raw files in directory but only one fraction?**

A: Set `frac_pat=None, id_pat=None` (single-needle mode). All raws merge as F1.

**Q: ID rate shows 0%?**

A: Check `id_pat` regex matches File_Name. Test with Python:
```python
import re; print(re.search(pat, File_Name_example))
```

**Q: No enzyme autolysis annotation?**

A: Two possible causes:
1. Reference proteome lacks enzyme entries → run mini-DB search, merge via `enz_extra`
2. `autol_pat` doesn't match → check protein ID format

**Q: MIT distribution figure missing?**

A: Check method extraction output for `CV-45:...:MS2_IT22:...` segments. QE XML methods use `Max_inject_time`.

**Q: English report still shows Chinese?**

A: `instrument` or `autol_cn` fields may contain Chinese characters. Explicitly set `'lang': 'en'`.

---

> For technical details, see [configuration.md](configuration.md) (configuration reference) and [troubleshooting.md](troubleshooting.md) (troubleshooting guide).
