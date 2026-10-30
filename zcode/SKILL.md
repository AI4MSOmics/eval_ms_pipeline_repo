---
name: eval_ms_pipeline
description: Mass spectrometry acquisition parameter evaluation pipeline. Supports 11 search engines (pFind, MaxQuant, Comet, MSFragger, Sage, MetaMorpheus, Mascot, PEAKS, pNovo, X!Tandem, isoPSV), Thermo raw files (FAIMS & conventional), bilingual reports (zh/en), cleavage QC from FASTA, FWHM via .ms1 or RAW direct-read. Configuration-driven: add DATASETS entry and run one command.
---

# eval_ms_pipeline — ZCode Skill

## When to use this skill

Use this skill when the user asks to:
- Evaluate mass spectrometry acquisition parameters (评估质谱参数)
- Compare acquisition methods (比较采集方法, e.g., MIT 22ms vs 80ms)
- Check identification quality (鉴定质控: specificity, missed cleavages)
- Analyze TopN / AGC Fill / injection time distributions
- Evaluate chromatographic peak width (FWHM / 半峰宽)
- Annotate enzyme autolysis on BPC chromatograms
- Process Thermo raw files with search results from any engine

## How to use

### Step 1: Check if a dataset is already configured

```python
# In eval_ms_pipeline.py, check DATASETS for existing entries
python -c "from eval_ms_pipeline import DATASETS; print(list(DATASETS.keys()))"
```

### Step 2: Add configuration if needed

The user must provide:
1. **Raw file directory** (Thermo .raw files)
2. **Search results** (pFind result dir, MaxQuant msms.txt, etc.)
3. **Optional**: protein FASTA (for cleavage QC), enzyme info

Create a DATASETS entry:

```python
DATASETS['<name>'] = dict(
    out=r'<output directory>',
    groups={
        '<group>': dict(
            label='<label with Chinese chars → Chinese report>',
            enz='<enzyme description>',
            color='tab:red',
            cv_colors={'45V': 'tab:red', '65V': 'tab:orange'},
            cv_off={'45V': -1, '65V': 1},
            datadir=r'<raw directory>',
            result=r'<search results path>',
            frac_pat=r'<fraction regex>',
            id_pat=r'<ID matching regex>',
            autol_pat='<enzyme protein regex>',
            autol_cn='<autolysis label>',
            # Optional:
            # engine='maxquant',  # auto-detect if omitted
            # fasta='<protein.fasta>',  # enables cleavage QC computation
            # enz_rule='KR_N',  # KR_N (LysargiNase) or KR_C (Trypsin)
            # lang='zh',  # or 'en'
            # has_ms1=True,  # enables .ms1 XIC (default: rawdump-xic)
        ),
    })
```

### Step 3: Run

```bash
python eval_ms_pipeline.py <dataset_name>
```

### Step 4: Report results

Output in `DATASETS[name]['out']`:
- `<group>_<report_name>.docx` — 5-section Word report
- `group_summary.tsv` — cross-group comparison
- `figs_summary/` — TopN, AGC Fill, FWHM, MIT distribution figures
- `figs_BPC/` — BPC with autolysis annotation

## Key parameters to check

| Parameter | What it controls | Common mistakes |
|-----------|-----------------|-----------------|
| `frac_pat` | Fraction number from raw filename | Don't include `\.raw$`; operates on filename stem |
| `id_pat` | (fraction, CV) from File_Name | Must capture integer in group 1 |
| `engine` | Search engine selection | Omit for auto-detect |
| `fasta` | Protein database for cleavage QC | Include for non-pFind engines |
| `enz_rule` | Enzyme cleavage rule | `KR_N` for LysargiNase, `KR_C` for Trypsin |
| `lang` | Report language | Auto-detect may fail if instrument/autol_cn has Chinese |

## Engine auto-detection

The pipeline auto-detects engines by column fingerprints:
- pFind: `Sequence` + `Calc.MH+` + `Raw_Score`
- MaxQuant: `Raw file` + `Scan number` + `m/z`
- Sage: `peptide` + `scannr` + `label` + `rank`
- MetaMorpheus: `Full Sequence` + `Protein Accession` + `QValue`
- isoPSV unified: `File_Name` + `Sequence` + `Modification`

For headerless formats (Comet, MSFragger), specify `engine` explicitly.

## Output interpretation

| Metric | Meaning | Good/Bad |
|--------|---------|----------|
| Overall ID rate | % of MS2 spectra identified | Higher is better |
| IT saturation % | % of MS2 at MIT cap | High = MIT-limited (increase MIT) |
| AGC Fill median | Median fill level | Low + high IT sat = MIT bottleneck |
| Fully specific % | % fully enzyme-specific peptides | >95% typical |
| Fully cleaved % | % peptides with 0 missed cleavages | >85% good digestion |
| FWHM median | Chromatographic peak width | 8-15s typical for 75min gradient |
| TopN | MS2 per MS1 cycle | Consistent across fractions = good |
