# Troubleshooting

## rawdump issues

### `Invalid_fastapath_Path` / `Cannot find the label: None`

**Cause**: Searcher.exe not run from its own directory.

**Fix**: Always `cd` to pFind bin before invoking:
```bash
cd /d/Bioinformatics/pFind3.1/bin
./Searcher.exe "E:\path\to\param\pFind.cfg"
```

### rawdump produces empty output (scans=0)

**Cause**: Raw filenames don't match the CV-suffix regex.

**Fix**: Add `dump_all=True` to the group config, or verify filenames contain `_45V`, `_65V` etc. suffixes.

### `--xic` mode fails with "no GetCentroidStream"

**Cause**: ThermoFisher RawFileReader DLL version too old (< 4.0).

**Fix**: Update the DLL. The `GetCentroidStream(int, bool)` method is needed for centroid data access.

## pFind issues

### Enzyme mini-DB search hangs

**Cause**: Either concurrent Searcher instances, or a corrupted MGF file.

**Fix**: 
1. Check no other Searcher/PSSearcher is running (`tasklist | grep -i searcher`)
2. Try removing suspicious MGF files from the datalist
3. Reduce thread count (`thread=4`) to lower resource contention

### `msmsnum` mismatch

**Cause**: `msmsnum` in `[datalist]` section doesn't match the actual number of `msmspath*` entries.

**Fix**: Count and match exactly.

### `aapath` missing

**Cause**: Inherited cfg from another machine.

**Fix**: Add `aapath=D:\Bioinformatics\pFind3.1\bin\aa.ini` (or your local path).

## Pipeline issues

### `frac_pat` produces NaN

**Cause**: Raw filename stem doesn't match the regex.

**Fix**: 
- Test: `re.match(pat, stem)` — `frac_pat` operates on the filename **without extension**
- Don't include `\.raw$` in the pattern
- For single-injection data, set `frac_pat=None, id_pat=None`

### MIT distribution figure missing

**Cause**: `mit_map(G)` returned empty — method_segs may be empty or lack MS2 IT.

**Fix**: Check `方法提取_<group>.tsv` — the method text should contain `CV-45:...:MS2_IT22:...` segments. QE XML methods use `Max_inject_time` instead.

### Identification rate 0% for some fractions

**Cause**: `id_pat` groups don't match File_Name in spectra.

**Fix**: Test with `re.search(pat, File_Name)` on a few actual File_Name values. Group 1 must be an integer, group 2 must be numeric (CV value without 'V').

### BPC autolysis annotation missing

**Cause**: 
1. No enzyme proteins in the reference proteome (common for non-model organisms)
2. `autol_pat` doesn't match any Proteins entries

**Fix**: 
1. Check: `grep -c "CON_LysargiNase" reference.fasta` — if 0, need enzyme mini-DB search
2. Run a separate pFind search against a mini enzyme DB, then add the result via `enz_extra`

## Data issues

### `.ms1` RetTime is wrong (linear drift)

**Known issue**: Some xtract versions produce incorrect RetTime in ms1 headers.

**Fix**: The pipeline already uses rawdump trailer `rt_map[scan_no]` for all RT mapping, not ms1 headers.

### Same-name rerun injections

**Cause**: Multiple raw files with the same fraction number from different batch dates.

**Fix**: The pipeline handles this automatically by extracting batch date from filename (`_YYYYMMDD_NNNNNNNN_`) and assigning run labels `F1`, `F1r1` etc.
