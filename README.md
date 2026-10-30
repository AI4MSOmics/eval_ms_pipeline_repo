# eval_ms_pipeline

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![MSHub Plugin](https://img.shields.io/badge/MSHub-ms.s1.acquisition--eval-teal)](plugin.yaml)

> **MSHub capability pack** for mass spectrometry acquisition parameter evaluation.
> Part of the [AI4MSOmics](https://github.com/AI4MSOmics) ecosystem.
> See [MSHub](https://github.com/AI4MSOmics/MSHub) for the hub specification.

A configuration-driven pipeline that reads Thermo `.raw` files and search results from **11 engines**, producing per-group bilingual evaluation reports with method parameters, per-fraction QC, MIT distribution, cleavage QC, peptide FWHM, and enzyme autolysis annotation.

## Installation

```bash
git clone https://github.com/AI4MSOmics/eval_ms_pipeline_repo.git
cd eval_ms_pipeline_repo
bash install.sh
```

## Usage — three integration paths

### 1. MSHub skill card

This repository follows the [MSHub plugin specification](https://github.com/AI4MSOmics/MSHub/blob/main/docs/03-plugin-spec.md). The [SKILL.md](SKILL.md) at the root is the MSHub-format skill card.

### 2. ZCode / Claude / Cursor / DeepSeek skill

Copy `zcode/` to your agent's skills directory:

```bash
cp -r zcode/ ~/.zcode/skills/eval_ms_pipeline/
```

Or configure `agent/tool_manifest.json` for DeepSeek / OpenAI function calling (see [agent/deepseek_guide.md](agent/deepseek_guide.md)).

### 3. Standalone CLI

```bash
python eval_ms_pipeline.py <dataset_name>
```

## Supported engines

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

## Key features

| Feature | Method | Verified on |
|---------|--------|-------------|
| Cleavage QC from FASTA | KR_N / KR_C rules, Met-cleavage aware | 99.71% specificity / 99.99% MC match vs pFind |
| Peptide FWHM (no .ms1) | `rawdump --xic` RAW direct-read | M. gastri, NTM (no .ms1 files) |
| MIT distribution | Per-CV histogram + saturation | NTM (93% saturation at MIT 22ms), M. gastri R2 (12.5% at 80ms) |
| Bilingual reports | Auto-detect from config text or `lang` field | M. gastri (zh + en) |
| Engine auto-detect | Column-fingerprint matching | 4 datasets, 13 groups, all correct |

## Documentation

| Document | Language | Description |
|----------|----------|-------------|
| [SKILL.md](SKILL.md) | English | MSHub skill card (agent-facing) |
| [docs/guide_zh.md](docs/guide_zh.md) | 中文 | 详细使用指南（10 节） |
| [docs/guide_en.md](docs/guide_en.md) | English | Detailed user guide (10 sections) |
| [docs/configuration.md](docs/configuration.md) | 双语 | Configuration reference |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 双语 | Troubleshooting |
| [plugin.yaml](plugin.yaml) | YAML | MSHub capability pack manifest |
| [schemas/](schemas/) | JSON | Input/output JSON Schemas |

## Related projects

- [MSHub](https://github.com/AI4MSOmics/MSHub) — Agent-native capability hub for MS proteomics
- [isoPSV](https://github.com/Songhao-Jiang/isoPSV) — Multi-engine competitive peptide spectrum matching

## License

Apache-2.0. See [LICENSE](LICENSE).
