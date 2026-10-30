---
name: acquisition-eval
description: Use for evaluating mass spectrometry acquisition parameters from Thermo raw files — TopN, AGC Fill, injection time (MIT) distribution, identification rate, cleavage specificity, missed cleavages, peptide FWHM, and enzyme autolysis. Triggers on "evaluate parameters", "compare acquisition methods", "check acquisition quality", "MIT distribution", "FWHM", "cleavage QC", or paths to .raw directories with search results.
user-invocable: true
argument-hint: "[raw directory] [search result path] [options]"
---

# MS acquisition parameter evaluation

## When to use

- A set of Thermo `.raw` files and search results must be evaluated for acquisition quality.
- Two or more acquisition methods (e.g., MIT 22 ms vs 80 ms) must be compared.
- Cleavage specificity, missed-cleavage distribution, or digestion quality must be checked.
- Chromatographic peak width (FWHM), MIT distribution, or TopN/AGC Fill statistics are needed.
- Enzyme autolysis contamination must be assessed and annotated on BPC.

## When not to use

- The user wants a full proteomics identification pipeline (use `ms.s2.*` search capabilities).
- The data is not from a Thermo instrument (rawdump requires ThermoFisher RawFileReader).
- The user needs quantitative analysis (LFQ, isobaric, SILAC — use `ms.s4.*`).
- No search results exist yet (run a search engine first, then evaluate).

## Preconditions & evidence

| Requirement | Evidence source |
|---|---|
| Thermo `.raw` files | Directory containing raw files with FAIMS CV suffix (`_45V`) or without |
| Search results | pFind `pFind-Filtered.spectra`, MaxQuant `msms.txt`, or any of 11 supported formats |
| Protein FASTA | Required for cleavage QC when engine is not pFind; optional otherwise |
| Enzyme rule | User must specify: `KR_C` (Trypsin) or `KR_N` (LysargiNase) |

Probe once:
1. Do `.raw` files exist in the directory? Check filenames for CV suffixes.
2. What is the result file format? Use `detect_engine` or inspect column names.
3. Does a protein FASTA exist? If not and engine ≠ pFind, ask user to provide one.

## Workflow

1. **Configure the dataset.** Add an entry to `DATASETS` with paths, regex patterns, enzyme info, and optional fields. See `docs/configuration.md` for the complete schema.
2. **Auto-detect engine.** Omit `engine` for column-fingerprint detection, or specify explicitly. Verify with `detect_engine`.
3. **Run evaluation.** `python eval_ms_pipeline.py <dataset_name>`.
4. **Read the group summary.** `group_summary.tsv` contains cross-group metrics for quick comparison.
5. **Review the report.** Per-group `.docx` files contain 5 sections with embedded figures.

## Decision rules

| Decision | Rule | Evidence |
|---|---|---|
| Engine auto-detect | Match column fingerprints; fallback to pFind | Column names in result file |
| Report language | Chinese if any config field contains CJK; English otherwise. Override with `lang` | `label`, `enz`, `instrument`, `autol_cn` fields |
| FWHM method | `.ms1` XIC if `has_ms1=True`; `rawdump --xic` otherwise | Presence of `.ms1` files |
| Cleavage QC source | Engine native column if available; FASTA computation if `fasta` provided; "—" if neither | `Specificity` / `Miss.Clv.Sites` columns or `fasta` + `enz_rule` |
| ID rate denominator | pFind: from `pFind.summary`; other engines: rawdump scan count | Engine type |

## Validation gates

- After step 3: check that `group_summary.tsv` has non-zero PSM counts for all groups.
- After step 3: verify report `.docx` files exist in the output directory.
- After step 4: flag any group with Overall ID rate < 5% (likely configuration error).
- After step 4: flag any group with IT saturation > 95% and AGC Fill < 0.1 (MIT severely limiting).

## Failure modes & recovery

| Failure | Detection | Recovery |
|---|---|---|
| ID rate 0% | `group_summary.tsv` shows 0 | Check `id_pat` regex matches File_Name; test with `re.search()` |
| No autolysis annotation | Report has no BPC annotations | Check if reference proteome has enzyme entries; run mini-DB search; add `enz_extra` |
| No FWHM figures | `figs_summary/` missing FWHM files | Check `tools/rawdump.exe` exists; check `.ms1` files if `has_ms1=True` |
| English report still Chinese | Report file name contains Chinese characters | Set `lang: "en"` explicitly |
| rawdump PermissionError | Pipeline exits with file path error | Ensure `result` is a file path, not directory; check file permissions |
| Comet/MSFragger not detected | Engine defaults to pfind incorrectly | Specify `engine: "comet"` or `engine: "msfragger"` explicitly |

## Output contract

| Artifact | Format | Schema | Description |
|---|---|---|---|
| `evaluation_report` | `.docx` | — | 5-section bilingual Word report with embedded figures |
| `method_parameters` | `.tsv` | — | Raw-embedded instrument settings (resolution, AGC, MIT, cycle, NCE, CV) |
| `group_summary` | `.tsv` | `schemas/output.json` | Cross-group metrics (ID rate, specificity, FWHM, TopN, etc.) |
| `figures` | `.png` | — | TopN/AGC/FWHM/MIT/BPC summary figures |
| `identification_detail` | `.tsv` | — | Per-fraction PSM/peptide/protein counts |

All outputs are written to `DATASETS[name]['out']`. File names use Chinese or English suffix based on report language.

## Safety & approvals

- **Network**: none. All computation is local.
- **Filesystem**: read-write (writes reports and figures to output directory). Does not modify input raw files or search results.
- **Secrets**: none required.
- **Destructive**: no. Overwrites previous outputs in the same directory.

## References

- [Configuration reference](docs/configuration.md) — all DATASETS fields with examples
- [English user guide](docs/guide_en.md) / [中文使用指南](docs/guide_zh.md)
- [Troubleshooting](docs/troubleshooting.md) — 15 common issues
- [MSHub plugin specification](https://github.com/AI4MSOmics/MSHub/blob/main/docs/03-plugin-spec.md)
- [isoPSV multi-engine platform](https://github.com/Songhao-Jiang/isoPSV) — source of search engine adapters

## Examples

### Example 1: FAIMS dual-CV, pFind results

```python
DATASETS['mydata'] = dict(
    out=r'E:\test\output',
    groups={
        'sample1': dict(
            label='Sample1 (M. gastri)',
            enz='LysargiNase+LysN (R29_KR_N)',
            datadir=r'E:\test\raw',
            result=r'E:\test\pfind\result',
            frac_pat=r'_R(\d)_(\d+)V',
            id_pat=r'_R(\d)_(\d+)V',
            fasta=r'E:\test\protein.fasta',
            enz_rule='KR_N',
        ),
    })
```

### Example 2: QE HF, MaxQuant results, single injection

```python
DATASETS['mq'] = dict(
    out=r'E:\test\output_en',
    groups={
        'mq_group': dict(
            label='MaxQuant group (Trypsin)',
            enz='Trypsin (KR_C)',
            engine='maxquant',
            datadir=r'E:\test\raw',
            result=r'E:\test\mq\msms.txt',
            frac_pat=None, id_pat=None,
            fasta=r'E:\test\uniprot.fasta',
            enz_rule='KR_C',
            lang='en',
        ),
    })
```
