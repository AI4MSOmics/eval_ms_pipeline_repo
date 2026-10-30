# Configuration Reference

## DATASETS schema

```python
DATASETS['<name>'] = dict(
    out='<output directory>',
    groups={
        '<group_key>': {
            # --- required ---
            'label':       str,   # display label (shown in report title, e.g. "Mab_LL（脓肿分枝杆菌 LL）")
            'enz':         str,   # enzyme description (e.g. "LysargiNase+LysN 混合酶切（R29_KR_N）")
            'color':       str,   # matplotlib color for this group
            'datadir':     str,   # directory containing .raw files
            'result':      str,   # pFind result dir OR msms.txt path (see engine)
            'frac_pat':    str,   # regex on raw filename stem → fraction number (group 1)
            'id_pat':      str,   # regex on spectra File_Name → (frac, CV) (groups 1,2)
            'autol_pat':   str,   # regex pattern for enzyme protein IDs in Proteins column
            'autol_cn':    str,   # Chinese label for autolysis peptides

            # --- FAIMS CV colors (required for FAIMS data) ---
            'cv_colors':   dict,  # {'45V': 'tab:red', '65V': 'tab:orange'}
            'cv_off':      dict,  # {'45V': -1, '65V': 1} — offset for plotting

            # --- optional ---
            'engine':      'pfind'|'maxquant',  # default 'pfind'
            'has_ms1':     bool,  # default False; True enables .ms1 XIC for FWHM
            'dump_all':    bool,  # default False; True processes all .raw (not just _CV-suffixed)
            'instrument':  str,   # default 'Orbitrap Exploris 480（FAIMS 双 CV）'
            'eval_date':   str,   # default '2026-10-17'
            'conclusion_ms': str,  # custom conclusion paragraph (2)
            'main_win':    tuple, # default (0.25, 0.90) — main elution window fraction
            'enz_extra':   list,  # paths to enzyme mini-DB pFind-Filtered.spectra files
            'raw_filter':  str,   # substring filter for raw filenames (single-needle mode)
        },
    })
```

## Key patterns

### `frac_pat` — fraction number from raw filename stem

Applied to raw filename **without extension** (stem). Must capture the fraction/injection number as an integer in group 1.

| Data type | Example filename | `frac_pat` | Captures |
|-----------|-----------------|-----------|----------|
| NTM (Mixture) | `..._Mixture_3_45V` | `r'_Mixture_(\d+)'` | 3 |
| 913 (F number) | `..._F05_90min` | `r'_F(\d+)_90min'` | 5 |
| Mga (R number) | `..._R1_45V` | `r'_R(\d)_(\d+)V'` | 1 |
| QE single | `..._Mab_LL_ELU` | `None` (single-needle) | — |

### `id_pat` — fraction + CV from spectra File_Name

Applied to pFind `File_Name` or synthesized MaxQuant filename. Must capture (fraction, CV) as groups 1,2.

| Data type | Example File_Name | `id_pat` | Captures |
|-----------|------------------|---------|----------|
| NTM | `..._Mixture_3_45V.12345.12345.2.0.dta` | `r'_Mixture_(\d+)_(\d+)V'` | (3, '45') |
| 913 | `..._F05_90min.12345...` | `r'_F(\d+)_90min'` | (5) — single CV |
| Mga | `..._R1_45V.24045...` | `r'_R(\d)_(\d+)V'` | (1, '45') |

### `autol_pat` — enzyme protein ID pattern

Regex applied to the `Proteins` column. Common patterns:

| Enzyme group | Pattern |
|-------------|---------|
| LysargiNase/Lys-N | `'CON_SL_LysN\|CON_LysargiNase'` |
| Trypsin/Lys-C | `'TRYP_PIG\|TRY1_BOVIN\|IPI00011694\|LYSC_LYSEN'` |
| With LysargiNase contaminant | add `\|XP_028892624` |

## Engine: MaxQuant

When `engine='maxquant'`:
- `result` should point to `msms.txt` (or its parent directory)
- The pipeline reads columns: `Raw file`, `Scan number`, `Sequence`, `Charge`, `m/z`, `Retention time`, `Proteins`, `Reverse`, `Potential contaminant`, `Missed cleavages`
- Reverse (`+`) and Potential contaminant (`+`) entries are auto-filtered
- `File_Name` is synthesized as `<raw_stem>.<scan>.<scan>.<charge>.0.dta` to maintain id_pat compatibility
- `Calc.MH+` is computed from `m/z` and `Charge`
- Identification rate uses rawdump denominator (identified MS2 / total MS2 per CV), not pFind summary
- Cleavage specificity shows "—" (MaxQuant doesn't output a Specificity column)

## FWHM: has_ms1 vs rawdump-xic

| Setting | Method | Pros | Cons |
|---------|--------|------|------|
| `has_ms1=True` | `.ms1` text file streaming | Fast for many targets | Requires xtract `.ms1` files |
| `has_ms1=False` (default) | `rawdump --xic` RAW direct-read | Works on any raw, no preprocessing needed | Slower (~1 min per raw for 250 targets) |

Both use identical calibration: ±0.02 Da window, max peak in window, half-max linear interpolation, FWHM 4–240 s gate, ±2.5 min search window.

## Single-needle mode (`frac_pat=None, id_pat=None`)

For single-injection data with no fraction numbering:
- All spectra assigned to fraction 1
- All raws assigned to run F1
- Identification rate uses the `Overall` line from pFind summary
- Set `raw_filter` to select a subset of raws from a shared directory
