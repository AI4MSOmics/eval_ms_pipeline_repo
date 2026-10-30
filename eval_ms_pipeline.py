# -*- coding: utf-8 -*-
"""通用质谱数据评估流程（固化自耳念 913 评估，2026-10-17）

用法: python eval_ms_pipeline.py <数据集名>     （数据集定义在 DATASETS）
     python eval_ms_pipeline.py NTM            # 脓肿/龟分枝杆菌 四组
     python eval_ms_pipeline.py 913            # 耳念 双组（重跑可刷新全部产出）

流程（每组独立）:
  0) raw_scan_agc.tsv 缺失时自动调用同目录 rawdump.exe <datadir>（新列 cv/master_scan/ft_res）
  1) 方法提取 tsv 缺失时调用 rawmethod.exe（ExportInstrumentMethod），解析 480 key=value 模板方法段
  2) 逐馏分 QC：rank 按 (master_scan, FAIMS CV) 分组（老 tsv 无 cv 列则顺序计数）；cycle/IT/触顶/Fill
  3) 鉴定统计：pFind.summary（Overall + 逐 mgf ID Rate）+ Filtered（REV_/CON_ 剔除）PSM/肽段/蛋白
  4) 逐馏分四联图（TopN 解析率按 rank×CV、AGC Fill 按 rank×CV 箱线、解析率随 RT 分 CV、半峰宽[仅当有 ms1]）
  5) 汇总图（各馏分细线 + 合并粗线；半峰宽汇总仅 has_ms1）
  6) 逐馏分 MS1 BPC + 蛋白酶自切肽标注（有 ms1→XIC apex；无 ms1→PSM RT 回退；库内无酶蛋白→注明）
  7) 每组 docx 报告（raw 内嵌方法参数=修改参数初始条件）+ 组级汇总 tsv

注意: xtract ms1 的 RetTime 字段可能是错的（耳念实测 scan 69490→5398 min），
      XIC/BPC 的 RT 轴一律用 rawdump trailer 的 rt_map[scan_no]。
      CV 键统一归一化为 '45V'/'65V'（取绝对值），无 CV 数据统一为 'CV'。
"""
import os
import re
import sys
import subprocess
import fnmatch
import numpy as np
import pandas as pd
import xic_raw

# ---------------- 中英文双语（根据用户配置文字自动检测） ----------------

LANG = {
    'zh': {
        'report_title': '质谱参数评估报告',
        'eval_date': '评估日期',
        'data_dir': '数据',
        'instrument': '仪器',
        'digestion': '酶切',
        'search_engine': '搜库',
        'search_desc': '既有搜库（1% FDR，REV_/CON_ 剔除）',
        'sec1': '一、raw 内嵌方法参数（修改参数的初始条件）',
        'sec1_desc': '以下为 raw 文件内自带仪器方法（ExportInstrumentMethod 提取）中的设定值，即本组数据的初始采集条件。',
        'sec2': '二、逐馏分质控',
        'sec2_desc': '口径：TopN、AGC Fill、注入时间与 rank 维度统计均限主洗脱段',
        'sec3': '三、鉴定结果（既有搜库，1% FDR）',
        'sec4': '四、结论',
        'sec5': '五、逐馏分补充图（汇总）',
        'sec5_desc': '每馏分四联图见 figs_逐馏分；BPC 见 figs_BPC；以下为合并汇总图。',
        # 表头
        'fraction': '馏分', 'ms1_count': 'MS1 数', 'ms2_count': 'MS2 数',
        'cycle_median': 'cycle 中位 s',
        'id_rate': '解析率', 'it_saturation': '触顶%',
        'it_med_max': 'IT 中位/实测', 'fill_median': 'Fill 中位',
        'psm_count': 'PSM 数', 'peptide_count': '肽段数', 'protein_count': '蛋白数',
        'level': '级别', 'count': '数量',
        'fully_specific': '完全特异性', 'fully_cleaved': '全酶切（0 漏切）',
        'mc1': '1 个漏切', 'mc2': '≥2 个漏切', 'spec_mc0': '特异性+0 漏切',
        'group_total': '组级合计', 'overall_rate': '谱图解析率 Overall',
        'per_frac_desc': '逐馏分鉴定数量（馏分内合并两 CV；同一馏分多批 raw 的鉴定合并计）：',
        'qc_desc': '鉴定质控（酶切特异性与漏切，剔 REV_/CON_ 口径；漏切=肽段内部残留酶切位点数）：',
        'per_cv': '逐 CV（PSM 级）：',
        'psm_level': 'PSM 级', 'peptide_level': '肽段级',
        # 图
        'fig_topn_rate': 'TopN 解析率（按 rank，主洗脱段）',
        'fig_agc_fill': 'AGC Fill 分布（按 rank×CV，主洗脱段）',
        'fig_rate_rt': '谱图解析率随 RT（5 min 箱，分 CV）',
        'fig_fwhm': '肽段半峰宽分布',
        'fig_quad': '逐馏分四联图',
        'fig_rel_intensity': '相对强度 (%)',
        'fig_ms2_count': '主洗脱段 MS2 计数',
        'fig_ms2_it': 'MS2 注入时间 (ms)',
        'fig_fwhm_s': '半峰宽 (s)',
        'fig_peak_count': '峰数',
        'fig_fwhm_median': '半峰宽中位 (s)',
        'fig_id_rate': '解析率 %',
        'fig_rt_min': 'RT (min)',
        'fig_rank': 'rank',
        'fig_merged': '合并',
        'fig_all_merged': '全部馏分合并分布',
        'fig_per_frac_median': '逐馏分半峰宽中位',
        'fig_topn_summary': 'TopN 解析率汇总',
        'fig_agc_summary': 'AGC Fill 按 rank×CV 汇总',
        'fig_rate_rt_summary': '谱图解析率随 RT 汇总',
        'fig_mit_dist': 'MS2 注入时间（IT）分布',
        'fig_fwhm_summary': '肽段半峰宽汇总',
        'fig_mit_line': 'MS2 注入时间分布（主洗脱段；虚线=方法 MIT）',
        'fig_xic_source': 'XIC 来源',
        # 文件名
        'fn_report': '_质谱参数评估报告.docx',
        'fn_method': '方法提取_',
        'fn_id_detail': '鉴定明细_逐馏分_',
        'fn_summary': '组级汇总.tsv',
        'dir_figs_frac': 'figs_逐馏分',
        'dir_figs_sum': 'figs_汇总',
        'dir_figs_bpc': 'figs_BPC',
        # 组级汇总列名
        'col_group': '组', 'col_frac_count': '馏分数',
        'col_topn': 'TopN均值', 'col_rate': '解析率范围',
        'col_sat': '触顶均值%', 'col_psm': 'PSM', 'col_pep': '肽段',
        'col_prot': '蛋白', 'col_overall': 'Overall解析率%',
        'col_spec': '完全特异性%', 'col_mc0': '全酶切%',
        # 结论
        'conclusion_default': ('（2）主洗脱段内各 rank 解析率基本持平（TopN/AGC Fill/注入时间统计均限主洗脱段，头尾段不参与）：'
                               'MS2 预算被 MIT 封顶、各 rank 相当，解析率对前体强度不敏感，加深 TopN 几乎无损失。'
                               'MS2 AGC Fill 普遍偏低、注入时间触顶比例高，离子量受 MIT 限制——放大 MIT 是参数修改收益最直接的一项；'
                               '梯度起始段 rank1–5 多为盐簇/聚合物等高丰度背景（不纳入 rank 统计），rank1 另受共隔离干扰。'),
        'conclusion_rate': '（1）逐（馏分×CV）解析率范围',
        'conclusion_cycle': '组内馏分采集节律一致（cycle 中位',
        # 其他
        'no_xic': '无 XIC 数据，半峰宽跳过',
        'method_note': '注：扫描范围 300–1400 m/z；480 FAIMS 方法无固定 TopN 档（Data Dependent Mode = Cycle Time），'
                       '逐 CV 实测 TopN 见第二节；全馏分 cycle 实测中位',
        'search_note': '搜库：既有搜库（1% FDR，REV_/CON_ 剔除）',
        'enzyme_autolysis': '酶自切肽',
        'bpc_title': 'BPC 与酶自切肽标注',
        'saved': '已保存',
    },
    'en': {
        'report_title': 'MS Parameter Evaluation Report',
        'eval_date': 'Evaluation date',
        'data_dir': 'Data',
        'instrument': 'Instrument',
        'digestion': 'Digestion',
        'search_engine': 'Search',
        'search_desc': 'Existing search (1% FDR, REV_/CON_ excluded)',
        'sec1': '1. Raw-Embedded Method Parameters (Initial Conditions)',
        'sec1_desc': 'Values from the instrument method embedded in the raw files (ExportInstrumentMethod), i.e. the initial acquisition conditions for this group.',
        'sec2': '2. Per-Fraction Quality Control',
        'sec2_desc': 'Scope: TopN, AGC Fill, injection time and rank statistics are restricted to the main elution window',
        'sec3': '3. Identification Results (1% FDR)',
        'sec4': '4. Conclusions',
        'sec5': '5. Supplementary Figures (Summary)',
        'sec5_desc': 'Per-fraction 4-panel figures in figs_frac; BPC in figs_BPC; summary figures below.',
        'fraction': 'Fraction', 'ms1_count': 'MS1 Count', 'ms2_count': 'MS2 Count',
        'cycle_median': 'Cycle Median s',
        'id_rate': 'ID Rate', 'it_saturation': 'IT Sat%',
        'it_med_max': 'IT Med/Max', 'fill_median': 'Fill Median',
        'psm_count': 'PSM Count', 'peptide_count': 'Peptide Count', 'protein_count': 'Protein Count',
        'level': 'Level', 'count': 'Count',
        'fully_specific': 'Fully Specific', 'fully_cleaved': 'Fully Cleaved (0 MC)',
        'mc1': '1 Missed Cleavage', 'mc2': '≥2 Missed Cleavages', 'spec_mc0': 'Specific + 0 MC',
        'group_total': 'Group total', 'overall_rate': 'Overall spectrum ID rate',
        'per_frac_desc': 'Per-fraction identification counts (CVs merged within fraction; multi-batch raw merged):',
        'qc_desc': 'Identification QC (cleavage specificity and missed cleavages, REV_/CON_ excluded):',
        'per_cv': 'Per CV (PSM level):',
        'psm_level': 'PSM level', 'peptide_level': 'Peptide level',
        'fig_topn_rate': 'TopN ID Rate (by rank, main elution)',
        'fig_agc_fill': 'AGC Fill Distribution (by rank×CV, main elution)',
        'fig_rate_rt': 'Spectrum ID Rate vs RT (5 min bins, by CV)',
        'fig_fwhm': 'Peptide FWHM Distribution',
        'fig_quad': 'Per-Fraction 4-Panel',
        'fig_rel_intensity': 'Relative Intensity (%)',
        'fig_ms2_count': 'Main Elution MS2 Count',
        'fig_ms2_it': 'MS2 Injection Time (ms)',
        'fig_fwhm_s': 'FWHM (s)',
        'fig_peak_count': 'Peak Count',
        'fig_fwhm_median': 'Median FWHM (s)',
        'fig_id_rate': 'ID Rate %',
        'fig_rt_min': 'RT (min)',
        'fig_rank': 'rank',
        'fig_merged': 'Merged',
        'fig_all_merged': 'All Fractions Combined',
        'fig_per_frac_median': 'Per-Fraction Median FWHM',
        'fig_topn_summary': 'TopN ID Rate Summary',
        'fig_agc_summary': 'AGC Fill by rank×CV Summary',
        'fig_rate_rt_summary': 'Spectrum ID Rate vs RT Summary',
        'fig_mit_dist': 'MS2 Injection Time (IT) Distribution',
        'fig_fwhm_summary': 'Peptide FWHM Summary',
        'fig_mit_line': 'MS2 IT Distribution (main elution; dashed=method MIT)',
        'fig_xic_source': 'XIC source',
        'fn_report': '_ms_parameter_report.docx',
        'fn_method': 'method_',
        'fn_id_detail': 'identification_per_fraction_',
        'fn_summary': 'group_summary.tsv',
        'dir_figs_frac': 'figs_frac',
        'dir_figs_sum': 'figs_summary',
        'dir_figs_bpc': 'figs_BPC',
        'col_group': 'Group', 'col_frac_count': 'Fractions',
        'col_topn': 'TopN_mean', 'col_rate': 'ID_rate_range',
        'col_sat': 'IT_sat_mean%', 'col_psm': 'PSM', 'col_pep': 'Peptide',
        'col_prot': 'Protein', 'col_overall': 'Overall_ID_rate%',
        'col_spec': 'Fully_specific%', 'col_mc0': 'Fully_cleaved%',
        'conclusion_default': ('(2) Within the main elution window, ID rates are flat across ranks '
                               '(TopN/AGC Fill/injection time statistics restricted to main elution): '
                               'MS2 budget is MIT-capped, ranks are equivalent, ID rate is insensitive to precursor intensity, '
                               'deepening TopN yields minimal gain. MS2 AGC Fill is generally low, injection time saturation is high—'
                               'ion budget is MIT-limited, so increasing MIT is the most direct parameter improvement. '
                               'Gradient start rank1–5 are predominantly salt cluster/polymer background (excluded from rank statistics), '
                               'rank1 additionally suffers from co-isolation interference.'),
        'conclusion_rate': '(1) Per (fraction×CV) ID rate range',
        'conclusion_cycle': 'Acquisition rhythm consistent across fractions (cycle median',
        'no_xic': 'No XIC data, FWHM skipped',
        'method_note': 'Note: Scan range 300–1400 m/z; 480 FAIMS methods have no fixed TopN '
                       '(Data Dependent Mode = Cycle Time), per-CV TopN in Section 2; all-fraction cycle median',
        'search_note': 'Search: existing (1% FDR, REV_/CON_ excluded)',
        'enzyme_autolysis': 'enzyme autolysis peptides',
        'bpc_title': 'BPC with Enzyme Autolysis Annotation',
        'saved': 'Saved',
    },
}


def detect_lang(G):
    """从组配置文字自动判断中英文：label/enz 等用户输入含中文→'zh'，否则→'en'。
    可通过 G['lang']='zh'|'en' 显式覆盖。"""
    if G.get('lang') in ('zh', 'en'):
        return G['lang']
    for k in ('label', 'enz', 'autol_cn', 'instrument'):
        v = G.get(k, '')
        if v and any('\u4e00' <= c <= '\u9fff' for c in str(v)):
            return 'zh'
    return 'en'


def _make_l(G):
    """创建翻译查找函数 _(key) → 当前语言的字符串。"""
    lang = detect_lang(G)
    d = LANG[lang]
    return lambda key: d.get(key, key), lang
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml.ns import qn

plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

HERE = os.path.dirname(os.path.abspath(__file__))
RAWDUMP = os.path.join(HERE, 'rawdump', 'bin', 'Debug', 'netcoreapp3.1', 'rawdump.exe')
RAWMETHOD = os.path.join(HERE, 'rawmethod', 'bin', 'Debug', 'netcoreapp3.1', 'rawmethod.exe')

XIC_TOL = 0.02
XIC_HALFWIN = 3.0
N_TARGET = 250
RT_BIN = 5.0


def sort_runs(per):
    import re as _re
    return sorted(per.items(), key=lambda kv: (int(_re.match(r'F(\d+)', kv[0]).group(1)), kv[0]))


def log(m):
    print(m, flush=True)


def norm_cv(x):
    """'−45.000'/'45'/'-45' → '45V'；None/空/非数字 → 'CV'"""
    if x is None:
        return 'CV'
    s = str(x).strip()
    if not re.fullmatch(r'-?\d+(\.\d+)?', s):
        return 'CV'
    return f'{abs(int(float(s)))}V'


# ---------------- ms1 XIC（RT 轴 = trailer rt_map，勿信 ms1 自带 RetTime） ----------------

def xic_stream(ms1file, targets, rt_map, want_apex=True):
    """targets: [(mz, rt, i)] → {i: dict(apex=(rt,int)[, fwhm=…])}"""
    acc = {i: ([], []) for _, _, i in targets}
    tmz = np.array([t[0] for t in targets])
    trt = np.array([t[1] for t in targets])
    order = np.argsort(tmz)
    tmz_s = tmz[order]
    lo_all, hi_all = trt.min() - XIC_HALFWIN, trt.max() + XIC_HALFWIN
    try:
        data = open(ms1file, 'rb').read()
    except OSError:
        return {}
    for chunk in data.split(b'\nS\t')[1:]:
        nl = chunk.find(b'\n')
        try:
            scan_no = int(chunk[:nl].split(b'\t')[0])
        except ValueError:
            continue
        rt = rt_map.get(scan_no)
        if rt is None or rt < lo_all or rt > hi_all:
            continue
        lines = chunk.split(b'\n')[1:]
        pk = b'\n'.join(ln for ln in lines if ln[:1].isdigit())
        if not pk:
            continue
        try:
            v = list(map(float, pk.split()))
            if len(v) % 2:
                v = v[:-1]
            arr = np.array(v, dtype=np.float64).reshape(-1, 2)
        except ValueError:
            continue
        mz, it = arr[:, 0], arr[:, 1]
        j = np.searchsorted(tmz_s, mz)
        best = {}
        for shift in (0, -1):
            pos = j + shift
            ok = (pos >= 0) & (pos < len(tmz_s))
            if not ok.any():
                continue
            p = pos[ok]
            near = np.abs(tmz_s[p] - mz[ok]) <= XIC_TOL
            if not near.any():
                continue
            tis = order[p[near]]
            ints = it[ok][near]
            keep = np.abs(trt[tis] - rt) <= XIC_HALFWIN
            for ti, iv in zip(tis[keep].tolist(), ints[keep].tolist()):
                if ti not in best or iv > best[ti]:
                    best[ti] = iv
        for ti, iv in best.items():
            rl, il = acc[ti]
            rl.append(rt)
            il.append(iv)
    out = {}
    for ti, (rl, il) in acc.items():
        if len(rl) < 4:
            continue
        rl = np.array(rl)
        il = np.array(il)
        o = np.argsort(rl)
        rl, il = rl[o], il[o]
        ur, idx = np.unique(rl, return_index=True)
        ui = np.maximum.reduceat(il, idx)
        a = int(np.argmax(ui))
        d = dict(apex=(float(ur[a]), float(ui[a])))
        if want_apex:
            out[ti] = d
            continue
        imax = ui[a]
        half = imax / 2.0
        li_ = a
        while li_ > 0 and ui[li_] > half:
            li_ -= 1
        ri_ = a
        while ri_ < len(ui) - 1 and ui[ri_] > half:
            ri_ += 1

        def cross(x0, y0, x1, y1):
            if y1 == y0:
                return x1
            return x0 + (half - y0) * (x1 - x0) / (y1 - y0)
        rtl = cross(ur[li_], ui[li_], ur[li_ + 1], ui[li_ + 1]) if ui[li_] <= half else ur[li_]
        rtr = cross(ur[ri_], ui[ri_], ur[ri_ - 1], ui[ri_ - 1]) if ui[ri_] <= half else ur[ri_]
        w = (rtr - rtl) * 60.0
        if 4.0 <= w <= 240.0:
            d['fwhm'] = w
            out[ti] = d
    return out


# ---------------- 多引擎结果加载（auto-detect） ----------------
# 支持 pFind/Comet/Mascot/MaxQuant/MetaMorpheus/MSFragger/PEAKS/pNovo/Sage/X!Tandem/isoPSV-unified
# 所有引擎映射到统一内部格式：Sequence/Proteins/File_Name/Scan_No/Charge/Calc.MH+[/Miss.Clv.Sites]
# 参考：https://github.com/Songhao-Jiang/isoPSV（多引擎适配器源码）

# 各引擎的指纹列名（用于 auto-detect）
ENGINE_FINGERPRINTS = {
    'pfind':       ['Sequence', 'Proteins', 'File_Name', 'Scan_No', 'Calc.MH+', 'Raw_Score'],
    'maxquant':    ['Raw file', 'Scan number', 'Sequence', 'Charge', 'm/z', 'Proteins'],
    'comet':       [],   # 无表头（skip=2），由文件名/调用者指定
    'msfragger':   [],   # 无表头（skip=1），由调用者指定
    'sage':        ['peptide', 'proteins', 'scannr', 'charge', 'label', 'rank'],
    'metamorpheus': ['Full Sequence', 'Base Sequence', 'Protein Accession',
                     'Precursor Charge', 'Scan Number', 'QValue'],
    'mascot':      ['pep_seq', 'pep_scan_title', 'pep_exp_z', 'pep_score'],
    'peaks':       ['Peptide', 'Source File', 'Scan', 'z', '-10lgP'],
    'pnovo':       [],   # 固定列位（无标准表头），由调用者指定
    'xtandem':     [],   # XML 解析，由调用者指定
    'isopsv':      ['File_Name', 'Sequence', 'Modification', 'Proteins', 'Charge'],
}

# 各引擎结果文件的发现模式（result 为目录时自动查找）
ENGINE_FILE_PATTERNS = {
    'pfind':       'pFind-Filtered.spectra',
    'maxquant':    'msms.txt',
    'sage':        'results.sage.tsv',
    'metamorpheus': 'AllPeptides.psmtsv',
    'mascot':      '*.csv',
    'peaks':       '*.csv',
    'comet':       '*.txt',
    'msfragger':   '*.tsv',
    'isopsv':      '*.tsv',
}


def detect_engine(path):
    """从结果文件列名自动判断搜索引擎。返回引擎名或 None。"""
    if not os.path.isfile(path):
        return None
    try:
        head = pd.read_csv(path, sep='\t', nrows=2, low_memory=False,
                           encoding='utf-8', errors='replace')
        cols = set(head.columns)
        for eng, fps in ENGINE_FINGERPRINTS.items():
            if fps and all(c in cols for c in fps):
                return eng
    except Exception:
        pass
    return None


def find_result_file(G):
    """result 可以是文件或目录；目录内按引擎模式发现结果文件。"""
    r = G['result']
    if os.path.isfile(r):
        return r
    if os.path.isdir(r):
        eng = G.get('engine')
        # 先按指定引擎的模式找
        if eng and eng in ENGINE_FILE_PATTERNS:
            pat = ENGINE_FILE_PATTERNS[eng]
            hits = [f for f in os.listdir(r) if fnmatch.fnmatch(f, pat)]
            if hits:
                return os.path.join(r, sorted(hits)[-1])
        # 再按已知文件名直接找（pFind 最常见）
        for known in ('pFind-Filtered.spectra', 'msms.txt', 'results.sage.tsv',
                      'AllPeptides.psmtsv'):
            p = os.path.join(r, known)
            if os.path.isfile(p):
                return p
        # 最后按通配找 tsv/csv/txt
        for pat in ('*.tsv', '*.csv', '*.txt'):
            hits = [f for f in os.listdir(r) if fnmatch.fnmatch(f, pat)]
            if hits:
                return os.path.join(r, sorted(hits)[-1])
    return r


def _strip_mods(seq):
    """剥除修饰标记：PEAKS 'PEPmods(…)'、MetaMorpheus '[mod on X]'、通用 [xx]。"""
    return re.sub(r'\([^)]*\)|\[[^\]]*\]', '', str(seq))


def _calc_mh_from_seq(seq, mods_str=''):
    """从序列计算 MH+（氨基酸和 + H2O + H，不含修饰）。"""
    AA_MASS = {'G': 57.02146, 'A': 71.03711, 'S': 87.03203, 'P': 97.05276,
               'V': 99.06841, 'T': 101.04768, 'C': 103.00919 + 57.02146,
               'L': 113.08406, 'I': 113.08406, 'N': 114.04293, 'D': 115.02694,
               'Q': 128.05858, 'K': 128.09496, 'E': 129.04259, 'M': 131.04049,
               'H': 137.05891, 'F': 147.06841, 'R': 156.10111, 'Y': 163.06333,
               'W': 186.07931}
    try:
        mass = sum(AA_MASS.get(a, 0.0) for a in seq) + 18.010565 + 1.007276
        return mass
    except Exception:
        return np.nan


# ---- 酶切特异性与漏切：从序列 + 蛋白库直接计算（缺列时自动补） ----

def load_fasta(fasta_path):
    """读 FASTA → {protein_id: sequence}。"""
    prots = {}
    pid = None
    buf = []
    with open(fasta_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if pid is not None:
                    prots[pid] = ''.join(buf)
                pid = line[1:].split()[0].rstrip(';')
                buf = []
            elif line:
                buf.append(line)
    if pid is not None:
        prots[pid] = ''.join(buf)
    return prots


def _check_cleavage_kr_n(peptide, protein_seq, pep_start):
    """KR_N（LysargiNase/Lys-N：切割于 K/R 之前）的特异性判定与漏切计数。
    返回 (specificity_code, missed_cleavages)。"""
    if pep_start < 0 or pep_start + len(peptide) > len(protein_seq):
        return 0, 0
    pep_end = pep_start + len(peptide)
    # N 端：肽段首残基为 K/R，或肽段起始于蛋白 N 端
    # （含 Met 剪切位：起始密码子 M 后第一位也算蛋白 N 端）
    n_ok = (peptide[0] in 'KR') or (pep_start == 0) or \
           (pep_start == 1 and protein_seq[0] == 'M')
    # C 端：肽段后一个残基为 K/R，或肽段终止于蛋白 C 端
    c_ok = (pep_end >= len(protein_seq)) or (protein_seq[pep_end] in 'KR')
    spec = 3 if (n_ok and c_ok) else (2 if n_ok else (1 if c_ok else 0))
    # 漏切：肽段内部（首残基之后）的 K/R 数
    mc = sum(1 for a in peptide[1:] if a in 'KR')
    return spec, mc


def _check_cleavage_kr_c(peptide, protein_seq, pep_start):
    """KR_C（Trypsin/Lys-C：切割于 K/R 之后）的特异性判定与漏切计数。"""
    if pep_start < 0 or pep_start + len(peptide) > len(protein_seq):
        return 0, 0
    pep_end = pep_start + len(peptide)
    # C 端：肽段末残基为 K/R，或肽段终止于蛋白 C 端
    c_ok = (peptide[-1] in 'KR') or (pep_end == len(protein_seq))
    # N 端：肽段前一个残基为 K/R，或肽段起始于蛋白 N 端
    n_ok = (pep_start == 0) or (protein_seq[pep_start - 1] in 'KR')
    spec = 3 if (n_ok and c_ok) else (2 if n_ok else (1 if c_ok else 0))
    # 漏切：肽段内部（末残基之前）的 K/R 数
    mc = sum(1 for a in peptide[:-1] if a in 'KR')
    return spec, mc


def compute_cleavage_from_db(d, fasta_path, enz_rule='KR_N'):
    """从蛋白库序列直接计算酶切特异性与漏切（当引擎不提供这些列时）。

    d: DataFrame 含 Sequence 和 Proteins 列
    fasta_path: 蛋白库 FASTA 路径
    enz_rule: 'KR_N'（LysargiNase/Lys-N）或 'KR_C'（Trypsin/Lys-C）

    就地添加 Specificity 和 Miss.Clv.Sites 列。
    """
    prots = load_fasta(fasta_path)
    checker = _check_cleavage_kr_n if enz_rule.upper() == 'KR_N' else _check_cleavage_kr_c
    # 预建肽段→(start) 索引（每蛋白一次 find，避免 O(n²)）
    _pep_cache = {}

    specs = np.zeros(len(d), dtype=int)
    mcs = np.zeros(len(d), dtype=int)
    seqs = d['Sequence'].fillna('').astype(str).values
    prots_col = d['Proteins'].fillna('').astype(str).values
    for i in range(len(d)):
        pep = seqs[i]
        if not pep or len(pep) < 4:
            continue
        prot_id = prots_col[i].split('/')[0].strip() if prots_col[i] else ''
        if not prot_id or prot_id not in prots:
            continue
        ps = prots[prot_id]
        # 缓存 (pep, prot_id) → start
        ck = (pep, prot_id)
        if ck in _pep_cache:
            pos = _pep_cache[ck]
        else:
            pos = ps.find(pep)
            _pep_cache[ck] = pos
        if pos < 0:
            continue
        specs[i], mcs[i] = checker(pep, ps, pos)
    d['Specificity'] = specs
    d['Miss.Clv.Sites'] = mcs
    log(f'  酶切质控从序列+蛋白库计算完成（{enz_rule}，{len(prots)} 蛋白，'
        f'命中 {(specs > 0).sum()}/{len(d)} PSM）')
    return d


def load_result_multi(G):
    """多引擎结果加载入口。auto-detect 或按 G['engine'] 指定。
    返回 (d DataFrame, engine_str)；d 列：Sequence/Proteins/File_Name/Scan_No/Charge/Calc.MH+。"""
    path = find_result_file(G)
    engine = G.get('engine')
    if not engine or engine == 'auto':
        engine = detect_engine(path) or 'pfind'  # 默认回退 pFind
    log(f'  引擎：{engine}，结果文件：{os.path.basename(str(path))}')

    if engine == 'pfind':
        return _load_pfind(path), engine
    elif engine == 'maxquant':
        return _load_maxquant(path), engine
    elif engine == 'sage':
        return _load_sage(path), engine
    elif engine == 'metamorpheus':
        return _load_metamorpheus(path), engine
    elif engine in ('mascot', 'peaks'):
        return _load_csv_generic(path, engine), engine
    elif engine in ('comet', 'msfragger'):
        return _load_headerless_tsv(path, engine), engine
    elif engine == 'isopsv':
        return _load_isopsv_unified(path), engine
    elif engine in ('pnovo', 'xtandem'):
        log(f'  {engine} 需经 isoPSV 适配器转换后使用（unified 格式）')
        return _load_isopsv_unified(path), engine
    else:
        raise ValueError(f'未知引擎：{engine}（支持 pfind/maxquant/sage/metamorpheus/'
                         'mascot/peaks/comet/msfragger/pnovo/xtandem/isopsv）')


def _find_map_file(G):
    """isoPSV 的 map 文件（new_scan↔original_title），同目录 scan_map*.tsv。"""
    d = os.path.dirname(str(G['result']))
    for f in os.listdir(d):
        if 'map' in f.lower() and f.endswith('.tsv'):
            return os.path.join(d, f)
    return None


def _load_pfind(path):
    """pFind 原生：pFind-Filtered.spectra。"""
    cols = ['Sequence', 'Proteins', 'File_Name', 'Scan_No', 'Charge', 'Calc.MH+']
    try:
        d = pd.read_csv(path, sep='\t', low_memory=False,
                        usecols=cols + ['Specificity', 'Miss.Clv.Sites'])
    except ValueError:
        d = pd.read_csv(path, sep='\t', low_memory=False, usecols=cols)
    return d


def _load_maxquant(path):
    """MaxQuant msms.txt。"""
    d = pd.read_csv(path, sep='\t', low_memory=False)
    d = d[d.get('Reverse', pd.Series('', index=d.index)).astype(str) != '+']
    if 'Potential contaminant' in d.columns:
        d = d[d['Potential contaminant'].astype(str) != '+']
    d = d[d['Sequence'].fillna('').astype(str).str.len() > 0]
    stem0 = d['Raw file'].astype(str).str.replace(r'\.raw$', '', regex=True)
    scan0 = d['Scan number'].astype(int)
    chg0 = d['Charge'].astype(float)
    mz0 = pd.to_numeric(d['m/z'], errors='coerce')
    out = pd.DataFrame({
        'Sequence': d['Sequence'].astype(str),
        'Proteins': d['Proteins'].fillna('').astype(str).str.replace(';', '/', regex=False),
        'File_Name': stem0 + '.' + scan0.astype(str) + '.' + scan0.astype(str)
                     + '.' + chg0.astype(int).astype(str) + '.0.dta',
        'Scan_No': scan0, 'Charge': chg0.astype(int),
        'Calc.MH+': mz0 * chg0 - (chg0 - 1) * 1.007276,
    })
    if 'Missed cleavages' in d.columns:
        out['Miss.Clv.Sites'] = pd.to_numeric(
            d['Missed cleavages'], errors='coerce').fillna(0).astype(int)
    return out


def _load_sage(path):
    """Sage results.sage.tsv。"""
    d = pd.read_csv(path, sep='\t', low_memory=False)
    d = d[d['label'].astype(str) != '-1']  # 去诱饵
    d = d[d['rank'].astype(str) == '1']     # top-1
    # Sage scannr 格式 "scan=N" 或裸数字
    scan = d['scannr'].astype(str).str.replace(r'^[^=]*=\s*', '', regex=True)
    scan_num = pd.to_numeric(scan, errors='coerce')
    d = d.dropna(subset=[scan_num.name if scan_num.name else 'scannr'])
    seqs = d['peptide'].astype(str).str.replace(r'\[[^\]]*\]', '', regex=True)
    prots = d['proteins'].astype(str).apply(
        lambda s: '/'.join(x.strip().split()[0] for x in s.split(';') if x.strip()) + '/')
    chg = pd.to_numeric(d['charge'], errors='coerce').fillna(2).astype(int)
    # 从序列算 MH+（Sage 不提供 m/z）
    mh = seqs.apply(_calc_mh_from_seq)
    out = pd.DataFrame({
        'Sequence': seqs, 'Proteins': prots,
        'File_Name': '',  # 需要 map 文件还原原始 title
        'Scan_No': scan_num.astype(int), 'Charge': chg, 'Calc.MH+': mh,
    })
    return out


def _load_metamorpheus(path):
    """MetaMorpheus AllPeptides.psmtsv。"""
    d = pd.read_csv(path, sep='\t', low_memory=False)
    d = d[d['Decoy/Contaminant/Target'].astype(str) == 'T']  # 仅 target
    d = d[pd.to_numeric(d.get('QValue', 1), errors='coerce') <= 0.01]
    seqs = d['Base Sequence'].astype(str)
    chg = pd.to_numeric(d['Precursor Charge'], errors='coerce').fillna(2).astype(int)
    scan = pd.to_numeric(d['Scan Number'], errors='coerce')
    fn = d['File Name'].astype(str) + '.' + scan.astype(str) + '.' + scan.astype(str) \
         + '.' + chg.astype(str) + '.0.dta'
    prots = d['Protein Accession'].fillna('').astype(str).apply(
        lambda s: '/'.join(x.strip() for x in s.split(';') if x.strip()) + '/')
    mh = seqs.apply(_calc_mh_from_seq)
    out = pd.DataFrame({
        'Sequence': seqs, 'Proteins': prots, 'File_Name': fn,
        'Scan_No': scan, 'Charge': chg, 'Calc.MH+': mh,
    })
    if 'Missed Cleavages' in d.columns:
        out['Miss.Clv.Sites'] = pd.to_numeric(
            d['Missed Cleavages'], errors='coerce').fillna(0).astype(int)
    return out


def _load_csv_generic(path, engine):
    """Mascot / PEAKS CSV 导出。"""
    d = pd.read_csv(path, low_memory=False)
    if engine == 'mascot':
        seqs = d['pep_seq'].astype(str)
        chg = pd.to_numeric(d.get('pep_exp_z', 2), errors='coerce').fillna(2).astype(int)
        fn = d['pep_scan_title'].astype(str)
        prots = d.get('pep_proteins', '').astype(str).apply(
            lambda s: '/'.join(x.strip().split()[0] for x in s.split(';') if x.strip()) + '/')
        # top-1 去重
        d = d[~d['pep_scan_title'].duplicated()]
    elif engine == 'peaks':
        seqs = d['Peptide'].astype(str).apply(_strip_mods)
        chg = pd.to_numeric(d.get('z', 2), errors='coerce').fillna(2).astype(int)
        scan = pd.to_numeric(d['Scan'], errors='coerce')
        fn = d['Source File'].astype(str) + '.' + scan.astype(str) + '.' \
             + scan.astype(str) + '.' + chg.astype(str) + '.0.dta'
        prots = d.get('Accession', '').astype(str).apply(
            lambda s: '/'.join(x.strip() for x in s.split(';') if x.strip()) + '/')
        # 按 -10lgP 取最佳每谱
        if '-10lgP' in d.columns:
            d = d.sort_values('-10lgP', ascending=False).drop_duplicates(
                subset=['Source File', 'Scan'] if 'Source File' in d.columns else None,
                keep='first')
    mh = seqs.apply(_calc_mh_from_seq)
    # Scan_No 从 File_Name 解析（title.scan.scan.z.i.dta）
    scan_no = fn.str.extract(r'\.(\d+)\.\d+\.\d+\.')[0]
    scan_no = pd.to_numeric(scan_no, errors='coerce')
    out = pd.DataFrame({
        'Sequence': seqs.values, 'Proteins': prots.values, 'File_Name': fn.values,
        'Scan_No': scan_no.values, 'Charge': chg.values, 'Calc.MH+': mh.values,
    })
    return out


def _load_headerless_tsv(path, engine):
    """Comet pep.txt / MSFragger _renum.tsv：无表头，按固定位取。"""
    skip = 2 if engine == 'comet' else 1
    if engine == 'comet':
        col_map = {0: 'scan', 2: 'charge', 11: 'seq', 15: 'proteins'}
    else:  # msfragger
        col_map = {0: 'scannum', 3: 'charge', 7: 'peptide', 10: 'proteins'}
    d = pd.read_csv(path, sep='\t', low_memory=False, header=None, skiprows=skip)
    for idx, name in col_map.items():
        if idx < d.shape[1]:
            d[name] = d.iloc[:, idx]
    # 去重每谱 top-1
    scan_col = 'scan' if engine == 'comet' else 'scannum'
    d = d.drop_duplicates(subset=[scan_col], keep='first')
    seqs = d.get('seq', d.get('peptide', pd.Series())).astype(str)
    seqs = seqs.apply(_strip_mods)
    chg = pd.to_numeric(d.get('charge', 2), errors='coerce').fillna(2).astype(int)
    prots = d.get('proteins', '').astype(str).apply(
        lambda s: '/'.join(x.strip().split()[0] for x in s.split(';') if x.strip()) + '/')
    mh = seqs.apply(_calc_mh_from_seq)
    scan_no = pd.to_numeric(d[scan_col], errors='coerce')
    # File_Name 无法还原（需 map 文件），暂用 scan 拼
    fn = scan_no.astype(str) + '.0.dta'
    out = pd.DataFrame({
        'Sequence': seqs.values, 'Proteins': prots.values, 'File_Name': fn.values,
        'Scan_No': scan_no.values, 'Charge': chg.values, 'Calc.MH+': mh.values,
    })
    return out


def _load_isopsv_unified(path):
    """isoPSV 统一适配器输出格式（File_Name/Sequence/Modification/Proteins/Charge）。"""
    d = pd.read_csv(path, sep='\t', low_memory=False)
    seqs = d['Sequence'].astype(str)
    chg = pd.to_numeric(d.get('Charge', 2), errors='coerce').fillna(2).astype(int)
    fn = d['File_Name'].astype(str)
    prots = d.get('Proteins', '').astype(str)
    # Scan_No 从 File_Name 解析
    scan_no = pd.to_numeric(fn.str.extract(r'\.(\d+)\.\d+\.\d+\.[dt]')[0], errors='coerce')
    mh = seqs.apply(_calc_mh_from_seq)
    out = pd.DataFrame({
        'Sequence': seqs.values, 'Proteins': prots.values, 'File_Name': fn.values,
        'Scan_No': scan_no.values, 'Charge': chg.values, 'Calc.MH+': mh.values,
    })
    return out

def ensure_agc(G):
    t = os.path.join(G['datadir'], 'raw_scan_agc.tsv')
    if not os.path.exists(t):
        log(f'  rawdump → {G["datadir"]}' + (' (--all)' if G.get('dump_all') else ''))
        subprocess.run([RAWDUMP, G['datadir']] + (['--all'] if G.get('dump_all') else []), check=False)
    try:
        empty = len(pd.read_csv(t, sep='\t')) == 0
    except Exception:
        empty = True
    if empty:
        log('  rawdump 结果为空（文件名无 CV 后缀？）→ 自动改用 --all 重跑')
        subprocess.run([RAWDUMP, G['datadir'], '--all'], check=False)
    return t


def ensure_method(G, OUT):
    t = os.path.join(OUT, f'方法提取_{G["key"]}.tsv')
    if not os.path.exists(t):
        log(f'  rawmethod → {G["datadir"]}')
        subprocess.run([RAWMETHOD, G['datadir'], t], check=False)
    segs = []
    try:
        import csv as _csv
        _csv.field_size_limit(2**31 - 1)
        row = list(_csv.reader(open(t, encoding='utf-8'), delimiter='\t'))[1]
        text = row[8].replace('\\n', '\n')
        seg_pat = re.compile(r'CV(-?\d+):res(\d+)/(\d+):MS1_IT(\d+):MS2_IT(\d+):cyc([\d.]+)s:nce([\d.]+)')
        for m in seg_pat.finditer(row[7] or ''):
            segs.append(dict(tag=f'CV {m.group(1)}', cv=int(m.group(1)), res1=int(m.group(2)), res2=int(m.group(3)),
                             mit1=int(m.group(4)), mit2=int(m.group(5)),
                             cyc=float(m.group(6)), nce=float(m.group(7))))
        if not segs:
            ev_pat = re.compile(r'<ScanEvent [^>]*id="(\d+)" FullInternalName="([^"]+)"[^>]*>(.*?)</ScanEvent>', re.S)

            def _grab(body, key):
                mm = re.search(r'<' + key + r'[^>]*>([^<]+)</' + key + r'>', body)
                return mm.group(1) if mm else ''
            for k2, m2_ in enumerate(ev_pat.finditer(text)):
                _, name, body = m2_.groups()
                tag = 'MS1' if k2 == 0 else 'MS2'
                res = _grab(body, 'Resolution')
                if not res:
                    continue
                segs.append(dict(tag=tag, res1=int(res), res2=None,
                                 agc1=_grab(body, 'AGC_target'), agc2='',
                                 mit1=int(float(_grab(body, 'Max_inject_time') or 0)),
                                 mit2='', cyc=None,
                                 nce=float(_grab(body, 'Fragmentation_HCD') or 0) if k2 else 0))
            rc = re.search(r'<Repeat_count>(\d+)<', text)
            if segs and rc:
                segs[-1]['topn'] = int(rc.group(1))
        agcs = re.findall(r'Normalised AGC Target \(%\)= (\d+)', text)
        for i, s in enumerate(segs):
            s['agc1'] = agcs[2 * i] if 2 * i < len(agcs) else ''
            s['agc2'] = agcs[2 * i + 1] if 2 * i + 1 < len(agcs) else ''
        mdate = re.search(r'Last Modified: ([0-9/]+)', text)
        G['method_date'] = mdate.group(1) if mdate else ''
    except Exception as e:
        log(f'  方法解析失败: {e}')
    G['method_segs'] = segs
    return t


# ---------------- 数据装载 ----------------

def load_group(G):
    t = ensure_agc(G)
    agc = pd.read_csv(t, sep='\t')
    agc['stem'] = agc['file'].str.replace(r'\.raw$', '', regex=True)
    if G.get('raw_filter'):
        agc = agc[agc['stem'].str.contains(G['raw_filter'], regex=False)].copy()
    if G.get('frac_pat'):
        agc['frac'] = agc['stem'].str.extract(G['frac_pat'])[0].astype(int)
        agc['batch'] = agc['stem'].str.extract(r'_(\d{8})_\d{8}_')[0].fillna('')
        agc = agc.sort_values(['stem', 'scan'])
        runs = {}
        for frac, g in agc.groupby('frac'):
            for i, b in enumerate(sorted(g['batch'].unique())):
                runs[(frac, b)] = f'F{frac}' if i == 0 else f'F{frac}r{i}'
        agc['run'] = [runs[(f_, b_)] for f_, b_ in zip(agc['frac'], agc['batch'])]
    else:
        agc['frac'] = 1  # 单针数据（无馏分编号）
        agc['batch'] = ''
        agc = agc.sort_values(['stem', 'scan'])
        agc['run'] = 'F1'
    if 'cv' in agc.columns and agc['cv'].astype(str).str.strip().replace('nan', '').ne('').any():
        agc['cvk'] = agc['cv'].map(norm_cv)
    else:
        agc['cvk'] = 'CV'
    rank = np.zeros(len(agc), dtype=int)
    m2mask = (agc['msorder'] == 2).values
    if 'master_scan' in agc.columns and agc['master_scan'].max() > 0:
        grp = agc.loc[m2mask].groupby(['master_scan', 'cvk'], sort=False).cumcount()
        rank[m2mask] = (grp + 1).values
    else:
        r = 0
        for i, mo in enumerate(agc['msorder'].values):
            r = 0 if mo == 1 else r + 1
            rank[i] = r
    agc['rank'] = rank

    # ---- 多引擎结果加载（auto-detect 或 G['engine'] 指定） ----
    d, _engine_used = load_result_multi(G)
    log(f'  {len(d)} PSM 载入（引擎 {_engine_used}）')

    # ---- 酶切特异性与漏切：缺列时从蛋白库序列计算 ----
    _fasta = G.get('fasta')
    if _fasta and os.path.isfile(_fasta):
        _need_spec = 'Specificity' not in d.columns
        _need_mc = 'Miss.Clv.Sites' not in d.columns
        if _need_spec or _need_mc:
            _enz_rule = G.get('enz_rule', 'KR_N' if 'LysargiNase' in G.get('enz', '')
                              else 'KR_C')
            d = compute_cleavage_from_db(d, _fasta, _enz_rule)
    d = d[~d['Proteins'].fillna('').astype(str).str.startswith('REV_')]
    if G.get('autol_pat'):
        enz = d[d['Proteins'].fillna('').astype(str).str.contains(G['autol_pat'], regex=True)].copy()
    else:
        enz = d.iloc[0:0].copy()
    d = d[~d['Proteins'].fillna('').astype(str).str.contains('CON_')]
    d = d[d['Sequence'].fillna('').astype(str).str.len() > 0]
    if G.get('id_pat'):
        ext = d['File_Name'].astype(str).str.extract(G['id_pat'])
        d['frac'] = ext[0].astype(int)
        d['cvk'] = ext[1].map(norm_cv) if ext.shape[1] > 1 else 'CV'
    else:
        d['frac'] = 1
        d['cvk'] = 'CV'
    if G.get('id_pat'):
        ext2 = enz['File_Name'].astype(str).str.extract(G['id_pat'])
        enz['frac'] = ext2[0].astype(int)
    else:
        enz['frac'] = 1
    for extra in G.get('enz_extra', []):
        try:
            de = pd.read_csv(extra, sep='\t', low_memory=False,
                             usecols=['Sequence', 'Proteins', 'File_Name', 'Scan_No', 'Charge', 'Calc.MH+'])
            de = de[~de['Proteins'].fillna('').astype(str).str.startswith('REV_')]
            if len(de):
                ex2 = de['File_Name'].astype(str).str.extract(G['id_pat'])
                de['frac'] = ex2[0].astype(int)
                enz = pd.concat([enz, de], ignore_index=True)
                log(f'  enz_extra 并入 {len(de)} 条酶肽 PSM：{extra}')
        except Exception as e:
            log(f'  enz_extra 读取失败 {extra}: {e}')
    G['enz_df'] = enz
    id_by = {}
    for (f, c), g in d.groupby(['frac', 'cvk']):
        id_by[(f, c)] = set(g['Scan_No'].astype(int))
    rates, overall, summary_lines = {}, None, []
    if _engine_used != 'pfind':
        # 非 pFind 引擎：解析率 = 鉴定 MS2 / 全部 MS2（rawdump 整针，逐 CV）
        m2 = agc[agc.msorder == 2]
        for (frac, cv), g in m2.groupby(['frac', 'cvk']):
            ids = id_by.get((int(frac), cv), set())
            nid = int(g['scan'].astype(int).isin(ids).sum())
            G['rates'][(f'F{int(frac)}', cv)] = (nid, round(100.0 * nid / max(len(g), 1), 2))
        tn = sum(v[0] for v in G['rates'].values())
        tt = int(len(m2))
        G['overall'] = (int(tn), tt, round(100.0 * tn / max(tt, 1), 2))
        rates, overall = G['rates'], G['overall']
    else:
        for line in open(os.path.join(G['result'], 'pFind.summary'), encoding='utf-8', errors='ignore'):
            m = re.match(r'^(\S+?)\s+(\d+)\s*/\s*(\d+)\s*=\s*([\d.]+)%', line.strip())
            if not m:
                continue
            if m.group(1) == 'Overall':
                overall = (int(m.group(2)), int(m.group(3)), float(m.group(4)))
                continue
            fm = re.search(G['id_pat'], m.group(1)) if G.get('id_pat') else None
            if fm:
                summary_lines.append((int(fm.group(1)), norm_cv(fm.group(2) if fm.lastindex >= 2 else None),
                                      int(m.group(2)), float(m.group(4))))
    # 与 cfg datalist 顺序 zip → 区分同名重跑针
    run_of = {}
    try:
        cfgp = os.path.join(os.path.dirname(G['result']), 'param', 'pFind.cfg')
        paths = re.findall(r'msmspath\d+=(.+)',
                           open(cfgp, encoding='gbk', errors='ignore').read().replace('\r\n', '\n'))
        if len(paths) == len(summary_lines):
            for p, (frac, cv, n, r) in zip(paths, summary_lines):
                stem = os.path.basename(p.strip()).replace('.pf2', '')
                mb = re.search(r'_(\d{8})_\d{8}_', stem)
                batch = mb.group(1) if mb else ''
                run_of[(frac, cv)] = runs.get((frac, batch), f'F{frac}')
    except Exception as e:
        log(f'  datalist 映射失败（{e}），重跑针解析率并入首针')
    for frac, cv, n, r in summary_lines:
        rates[(run_of.get((frac, cv), f'F{frac}'), cv)] = (n, r)
    if not G.get('id_pat') and overall:
        rates[('F1', 'CV')] = (overall[0], overall[2])
    G['rates'] = rates
    G['overall'] = overall
    prots = set()
    for p in d['Proteins'].fillna('').astype(str):
        prots.update(x for x in p.split('/') if x)
    G['totals'] = dict(PSM=len(d), 肽段=d['Sequence'].nunique(), 蛋白=len(prots))
    per_fid = {}
    for f, g in d.groupby('frac'):
        pr = set()
        for pp in g['Proteins'].fillna('').astype(str):
            pr.update(x for x in pp.split('/') if x)
        per_fid[int(f)] = dict(PSM=len(g), 肽段=g['Sequence'].nunique(), 蛋白=len(pr))
    G['per_frac_id'] = per_fid

    # 鉴定质控：酶切特异性 / 全酶切 / 漏切（剔 REV_/CON_ 口径；PSM 与肽段两级）
    # pFind 提供 Specificity+Miss.Clv.Sites；MaxQuant 等仅 Missed cleavages（spec=None）
    G['cleavage_qc'] = None
    _has_spec = 'Specificity' in d.columns
    _has_mc = 'Miss.Clv.Sites' in d.columns
    if _has_spec or _has_mc:

        def _clv_stats(df):
            n = len(df)
            if not n:
                return None
            spec = (100 * (df['Specificity'] == 3).mean()
                    if _has_spec else None)
            mc0 = (100 * (df['Miss.Clv.Sites'] == 0).mean() if _has_mc else None)
            mc1 = (100 * (df['Miss.Clv.Sites'] == 1).mean() if _has_mc else None)
            mc2 = (100 * (df['Miss.Clv.Sites'] >= 2).mean() if _has_mc else None)
            strict = (100 * ((df['Specificity'] == 3) &
                             (df['Miss.Clv.Sites'] == 0)).mean()
                      if (_has_spec and _has_mc) else None)
            return dict(n=n, spec=spec, mc0=mc0, mc1=mc1, mc2=mc2, strict=strict)

        qc_psm = _clv_stats(d)
        qc_pep = _clv_stats(d.drop_duplicates('Sequence'))
        qc_cv = {}
        if G.get('id_pat'):
            for cv, g2 in d.groupby('cvk'):
                qc_cv[cv] = _clv_stats(g2)
        G['cleavage_qc'] = dict(psm=qc_psm, pep=qc_pep, cv=qc_cv)
    return agc, d, id_by


# ---------------- 逐馏分统计 ----------------

def per_fraction_stats(G, agc, id_by):
    per = {}
    run_end_g = float(agc['rt_min'].max())
    mw_f = G.get('main_win', (0.25, 0.90))
    for run, g in agc.groupby('run'):
        frac = int(re.match(r'F(\d+)', run).group(1))
        m1 = g[g.msorder == 1].sort_values('scan')
        m2 = g[g.msorder == 2]
        iv = np.diff(m1['rt_min'].values) * 60
        run_end = float(g['rt_min'].max())
        lo, hi = mw_f[0] * run_end, mw_f[1] * run_end
        cvstat = {}
        for c in sorted(m2['cvk'].unique()):
            mc = m2[m2.cvk == c].copy()
            mc['_id'] = mc['scan'].isin(id_by.get((frac, c), set()))
            # TopN/rank/IT/Fill 一律用主洗脱段（头尾段不参与）
            w = mc[(mc.rt_min >= lo) & (mc.rt_min <= hi)].copy()
            cyc_ms1 = m1[(m1.rt_min >= lo) & (m1.rt_min <= hi)]
            topn = float(len(w) / max(len(cyc_ms1), 1)) if len(cyc_ms1) else np.nan
            itmax = float(w['it_ms'].max()) if len(w) else np.nan
            rr = w[w['rank'] <= G['topn_cap']].groupby('rank')['_id'].agg(['mean', 'size'])
            bins = np.arange(0, run_end_g + RT_BIN, RT_BIN)
            mc['_b'] = np.digitize(mc['rt_min'], bins) - 1
            rtr = mc.groupby('_b')['_id'].agg(['mean', 'size'])  # RT 轮廓保留全程
            rtr = rtr[rtr['size'] >= 20]  # 每箱 ≥20 MS2，防单人箱假 100%
            cvstat[c] = dict(topn=topn,
                             it_med=float(w['it_ms'].median()) if len(w) else np.nan,
                             it_max=itmax,
                             top_pct=float(100 * (w['it_ms'] >= itmax - 0.5).mean()) if len(w) else np.nan,
                             fill_med=float(w['agc_fill'].median()) if w['agc_fill'].notna().any() else np.nan,
                             rate=G['rates'].get((run, c), (None, None))[1],
                             rr=rr, rtr=rtr,
                             fill_by_rank=[w.loc[w['rank'] == k, 'agc_fill'].dropna().values
                                           for k in range(1, G['topn_cap'] + 1)],
                             mc2=w[['rt_min', 'rank', 'agc_fill', 'it_ms', '_id', 'cvk']].copy())
        per[run] = dict(frac=frac, ms1=len(m1), ms2=len(m2), cyc=float(np.median(iv)) if len(iv) else np.nan,
                         tic=float(m1['tic'].median()) / 1e9, cvstat=cvstat,
                         m1s=m1, bp=m1['basepeak'].values.astype(float),
                         rt_map=dict(zip(g['scan'].astype(int), g['rt_min'])))
    return per


# ---------------- 图 ----------------

def cvar(G, c):
    return G['cv_colors'].get(c, None), G['cv_off'].get(c, 0)


def frac_quad(G, run, pf, FIG_FRAC):
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.5))
    for c, st in pf['cvstat'].items():
        col, off = cvar(G, c)
        rr = st['rr']
        axes[0, 0].plot(rr.index, rr['mean'] * 100, 'o-', ms=3, color=col, label=f'CV {c}')
        fb = [(k + 1, v) for k, v in enumerate(st['fill_by_rank']) if len(v)]
        if fb:
            axes[0, 1].boxplot([v for _, v in fb], positions=[k + 0.22 * off for k, _ in fb],
                               widths=0.35, showfliers=False, manage_ticks=False)
        rtr = st['rtr']
        ctr = np.array([RT_BIN * (i + 0.5) for i in rtr.index])
        axes[1, 0].plot(ctr, rtr['mean'] * 100, '-', color=col, label=f'CV {c}')
    axes[0, 1].axhline(1.0, ls='--', c='gray', lw=0.8)
    axes[0, 0].set_xticks(range(1, G['topn_cap'] + 1))
    axes[0, 0].set_title('TopN 解析率（按 rank，主洗脱段）')
    axes[0, 0].set_xlabel('rank'); axes[0, 0].set_ylabel('解析率 %'); axes[0, 0].legend(fontsize=7)
    axes[0, 1].set_xticks(range(1, G['topn_cap'] + 1))
    axes[0, 1].set_xlim(0.3, G['topn_cap'] + 0.7)
    axes[0, 1].tick_params(axis='x', labelsize=7)
    axes[0, 1].set_title('AGC Fill 分布（按 rank×CV，主洗脱段）')
    axes[0, 1].set_xlabel('rank'); axes[0, 1].set_ylabel('AGC Fill')
    axes[1, 0].set_title('谱图解析率随 RT（5 min 箱，分 CV）')
    axes[1, 0].set_xlabel('RT (min)'); axes[1, 0].set_ylabel('解析率 %'); axes[1, 0].legend(fontsize=7)
    if len(pf.get('fwhm', [])):
        fw = pf['fwhm']
        axes[1, 1].hist(fw, bins=np.arange(0, 121, 3), color=G['color'], alpha=0.75)
        axes[1, 1].axvline(np.median(fw), c='k', ls='--', lw=1)
        axes[1, 1].set_title(f'肽段半峰宽分布（n={len(fw)}，中位 {np.median(fw):.1f} s）')
    else:
        axes[1, 1].text(0.5, 0.5, '无 XIC 数据，半峰宽跳过', ha='center', va='center', fontsize=10)
        axes[1, 1].set_title('肽段半峰宽分布')
    axes[1, 1].set_xlabel('半峰宽 (s)'); axes[1, 1].set_ylabel('峰数')
    for ax in axes.ravel():
        ax.grid(alpha=0.3)
    fig.suptitle(f'{G["label"]} {run}（逐馏分四联图）', fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(os.path.join(FIG_FRAC, f'{G["key"]}_{run}.png'), dpi=130)
    plt.close(fig)


def mit_map(G):
    """cvk → MS2 MIT（ms），来自方法段；QE XML 段用 mit1。"""
    out = {}
    for s in G.get('method_segs') or []:
        tag = str(s.get('tag', ''))
        if tag.startswith('CV') and s.get('cv') is not None:
            out[f'{abs(int(s["cv"]))}V'] = float(s.get('mit2') or 0)
        elif tag == 'MS2' and s.get('mit1'):
            out['CV'] = float(s['mit1'])
    return out


def mit_dist_fig(G, per, FIG_SUM):
    """MIT（MS2 注入时间）分布图：每 run 一面板，逐 CV 直方图 + MIT 虚线。"""
    runs = list(sort_runs(per))
    if not runs:
        return
    mits = mit_map(G)
    ncol = min(3, len(runs))
    nrow = int(np.ceil(len(runs) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.2 * ncol, 3.9 * nrow),
                             squeeze=False)
    for i, (run, pf) in enumerate(runs):
        ax = axes[i // ncol][i % ncol]
        for c in sorted(pf['cvstat']):
            st = pf['cvstat'][c]
            it = pd.to_numeric(st['mc2']['it_ms'], errors='coerce').dropna()
            if not len(it):
                continue
            mit = mits.get(c) or float(it.max())
            col, _ = cvar(G, c)
            ax.hist(it, bins=60, range=(0, mit * 1.15), histtype='step',
                    lw=1.8, color=col or 'gray',
                    label='%s（n=%d，触顶 %.1f%%）' % (c, len(it), st['top_pct']))
            ax.axvline(mit, color='k', ls='--', lw=1.0)
            ax.text(mit, ax.get_ylim()[1] * 0.95, ' MIT=%.0f ms' % mit,
                    ha='left', va='top', fontsize=8.5)
        ax.set_title(run, fontsize=11)
        ax.set_xlabel('MS2 注入时间 (ms)', fontsize=9.5)
        ax.set_ylabel('主洗脱段 MS2 计数', fontsize=9.5)
        ax.legend(fontsize=8.5, frameon=False)
        ax.tick_params(labelsize=8.5)
    for j in range(len(runs), nrow * ncol):
        axes[j // ncol][j % ncol].axis('off')
    fig.suptitle(f'{G["label"]} MS2 注入时间（IT）分布（主洗脱段；虚线=方法 MIT）', fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = os.path.join(FIG_SUM, f'{G["key"]}_fig_MIT分布.png')
    fig.savefig(out, dpi=150)
    plt.close(fig)


def summary_figs(G, per, FIG_SUM):
    cvs = sorted({c for pf in per.values() for c in pf['cvstat']})
    allm2 = pd.concat([st['mc2'] for pf in per.values() for st in pf['cvstat'].values()],
                      ignore_index=True)
    topn_cap = G['topn_cap']

    fig, ax = plt.subplots(figsize=(8.5, 5))
    for c in cvs:
        col, _ = cvar(G, c)
        for frac, pf in sorted(per.items()):
            if c not in pf['cvstat']:
                continue
            rr = pf['cvstat'][c]['rr']
            ax.plot(rr.index, rr['mean'] * 100, '-', color=col, alpha=0.2, lw=0.8)
        sub = allm2[(allm2.cvk == c) & (allm2['rank'] <= topn_cap)]
        if len(sub):
            pooled = sub.groupby('rank')['_id'].mean()
            ax.plot(pooled.index, pooled.values * 100, 'o-', color=col, lw=2.2, label=f'CV {c} 合并')
    ax.set_xticks(range(1, topn_cap + 1))
    ax.tick_params(axis='x', labelsize=8)
    ax.set_xlabel('rank'); ax.set_ylabel('解析率 %'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title(f'{G["label"]} TopN 解析率汇总（主洗脱段；细线=各馏分，粗线=合并）')
    fig.tight_layout(); fig.savefig(os.path.join(FIG_SUM, f'{G["key"]}_fig_TopN解析率汇总.png'), dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 5))
    for c in cvs:
        col, off = cvar(G, c)
        pos, data, mids = [], [], []
        for k in range(1, topn_cap + 1):
            vals = np.concatenate([pf['cvstat'][c]['fill_by_rank'][k - 1] for pf in per.values()
                                   if c in pf['cvstat'] and len(pf['cvstat'][c]['fill_by_rank'][k - 1])]) \
                if any(c in pf['cvstat'] and len(pf['cvstat'][c]['fill_by_rank'][k - 1]) for pf in per.values()) else []
            if len(vals):
                pos.append(k + 0.22 * off); data.append(vals); mids.append((k, float(np.median(vals))))
        if data:
            ax.boxplot(data, positions=pos, widths=0.35, showfliers=False, manage_ticks=False)
            ax.plot([m[0] + 0.22 * off for m in mids], [m[1] for m in mids],
                    'o-', color=col, lw=1.6, label=f'CV {c} 合并中位')
    ax.axhline(1.0, ls='--', c='gray', lw=0.8)
    ax.set_xticks(range(1, topn_cap + 1))
    ax.set_xlim(0.3, topn_cap + 0.7)
    ax.tick_params(axis='x', labelsize=8)
    ax.set_xlabel('rank'); ax.set_ylabel('AGC Fill'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title(f'{G["label"]} AGC Fill 按 rank×CV 汇总（主洗脱段，全部馏分合并）')
    fig.tight_layout(); fig.savefig(os.path.join(FIG_SUM, f'{G["key"]}_fig_AGC_Fill汇总.png'), dpi=150); plt.close(fig)

    run_end = float(allm2['rt_min'].max())
    bins = np.arange(0, run_end + RT_BIN, RT_BIN)
    fig, ax = plt.subplots(figsize=(9.5, 5))
    for c in cvs:
        col, _ = cvar(G, c)
        for frac, pf in sorted(per.items()):
            if c not in pf['cvstat']:
                continue
            rtr = pf['cvstat'][c]['rtr']
            ctr = np.array([RT_BIN * (i + 0.5) for i in rtr.index])
            ax.plot(ctr, rtr['mean'] * 100, '-', color=col, alpha=0.2, lw=0.8)
        sub = allm2[allm2.cvk == c].copy()
        sub['_b'] = np.digitize(sub['rt_min'], bins) - 1
        gid = sub.groupby('_b')['_id'].mean()
        ax.plot([RT_BIN * (i + 0.5) for i in gid.index], gid.values * 100, 'o-',
                color=col, lw=2.2, label=f'CV {c} 合并')
    ax.set_xlabel('RT (min)'); ax.set_ylabel('解析率 %'); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    ax.set_title(f'{G["label"]} 谱图解析率随 RT 汇总（全程；细线=各馏分，粗线=合并）')
    fig.tight_layout(); fig.savefig(os.path.join(FIG_SUM, f'{G["key"]}_fig_解析率随RT汇总.png'), dpi=150); plt.close(fig)

    if any(len(pf.get('fwhm', [])) for pf in per.values()):
        fw_all = [v for pf in per.values() for v in [pf.get('fwhm', np.array([]))] if len(v)]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
        if fw_all:
            fa = np.concatenate(fw_all)
            axes[0].hist(fa, bins=np.arange(0, 121, 3), color=G['color'], alpha=0.75)
            axes[0].axvline(np.median(fa), c='k', ls='--', lw=1.2, label=f'中位 {np.median(fa):.1f} s')
            axes[0].legend(fontsize=9)
        else:
            axes[0].text(0.5, 0.5, '无有效峰', ha='center', va='center')
        axes[0].set_xlabel('半峰宽 (s)'); axes[0].set_ylabel('峰数'); axes[0].grid(alpha=0.3)
        axes[0].set_title('全部馏分合并分布')
        frs = sorted(per)
        axes[1].plot(frs, [np.median(per[f]['fwhm']) if len(per[f].get('fwhm', [])) else np.nan for f in frs],
                     'o-', color=G['color'])
        axes[1].set_xlabel('馏分'); axes[1].set_ylabel('半峰宽中位 (s)'); axes[1].grid(alpha=0.3)
        axes[1].set_title('逐馏分半峰宽中位')
        fig.suptitle(f'{G["label"]} 肽段半峰宽汇总（XIC 来源：{G.get("fwhm_src", "ms1")}）', fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.93])
        fig.savefig(os.path.join(FIG_SUM, f'{G["key"]}_fig_半峰宽汇总.png'), dpi=150); plt.close(fig)
    return cvs


def bpc_fig(G, run, pf, ann, FIG_BPC):
    rt = pf['m1s']['rt_min'].values
    bp = pf['bp']
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.plot(rt, bp, '-', color=G['color'], lw=0.8)
    ax.set_xlim(0, max(80, rt.max() + 2))
    ax.set_ylim(0, bp.max() * 1.15 if len(bp) else 1)
    ax.set_xlabel('RT (min)'); ax.set_ylabel('MS1 Base Peak Intensity')
    ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    ax.grid(alpha=0.3)
    span = bp.max() * 1.15 if len(bp) else 1
    levels = [0.06, 0.13, 0.20, 0.27]
    last_lv = [-99] * len(levels)
    for a in ann:
        x, y = a['rt'], a['int']
        lv = next((li for li in range(len(levels)) if x - last_lv[li] >= 5.0),
                  int(np.argmax([x - last_lv[li] for li in range(len(levels))])))
        last_lv[lv] = x
        yt = y + levels[lv] * span
        ax.vlines(x, y, yt, color='crimson', lw=0.7, alpha=0.8)
        ax.plot([x], [y], 'v', color='crimson', ms=4)
        ax.text(x, yt, f'{a["seq"]} ({a["chg"]}+)', rotation=90, ha='center', va='bottom',
                fontsize=6.2, color='crimson')
    note = f'标注{G["autol_cn"]} {len(ann)} 条' if ann else \
        ('该组无酶自切肽鉴定' if G.get('autol_pat') else '未指定自切源')
    ax.set_title(f'{G["label"]} {run} MS1 Base Peak 色谱图（{note}）', fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG_BPC, f'{G["key"]}_{run}_BPC.png'), dpi=130)
    plt.close(fig)


# ---------------- docx 报告 ----------------

def gen_report(G, per, OUT, FIG_SUM):
    _, lang = _make_l(G)   # _(key) → 当前语言字符串
    doc = Document()
    st = doc.styles['Normal']
    st.font.name = 'Calibri'; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体' if lang == 'zh' else 'Calibri')

    def H(t, lv=1):
        doc.add_heading(t, level=lv)

    def P(t, bold=False):
        p = doc.add_paragraph()
        p.add_run(t).bold = bold

    def T(rows, cols):
        tt = doc.add_table(rows=len(rows) + 1, cols=len(cols))
        tt.style = 'Light Grid Accent 1'
        for j, c in enumerate(cols):
            tt.rows[0].cells[j].text = str(c)
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                tt.rows[i + 1].cells[j].text = str(v)

    H(f'{G["label"]} {_("report_title")}', 0)
    P(f'{_("eval_date")}：{G.get("eval_date", "2026-10-17")} ｜ '
      f'{_("data_dir")}：{G["datadir"]} ｜ '
      f'{_("instrument")}：{G.get("instrument", "Orbitrap Exploris 480（FAIMS dual CV）")}｜ '
      f'{_("digestion")}：{G["enz"]}｜ {_("search_note")}')

    H(_('sec1'), 1)
    P(_('sec1_desc'))
    segs = G.get('method_segs') or []
    if segs and segs[0].get('tag', '').startswith('CV'):
        rows = []
        for s in segs:
            rows.append([s['tag'], f'{s["res1"]:,} / {s["res2"]:,}',
                         f'{s["agc1"]}% / {s["agc2"]}%' if s.get('agc1') else '',
                         f'{s["mit1"]} / {s["mit2"]} ms', f'{s["cyc"]} s', f'{s["nce"]:.0f}'])
        T(rows, ['FAIMS CV', f'MS1/MS2 {"分辨率" if lang=="zh" else "Resolution"}',
                 'AGC MS1/MS2', 'MIT MS1/MS2',
                 f'Cycle ({"设定" if lang=="zh" else "Method"})', 'NCE'])
    elif segs:
        rows = []
        for s in segs:
            agc_ = int(s['agc1']) if s.get('agc1') else 0
            rows.append([s['tag'], f'{s["res1"]:,}',
                         f'{agc_:,} charges' if agc_ else '',
                         f'{s["mit1"]} ms', s.get('nce', 0)])
        T(rows, [_('fraction') if False else ('扫描事件' if lang=='zh' else 'Scan Event'),
                 ('分辨率' if lang=='zh' else 'Resolution'), 'AGC target', 'Max IT', 'NCE'])
        if segs[-1].get('topn'):
            P(f'TopN ({"方法设定" if lang=="zh" else "method"}) = {segs[-1]["topn"]}')
    else:
        P(f'({"方法解析不可用" if lang=="zh" else "Method parsing unavailable"})')
    cyc = np.median([pf['cyc'] for pf in per.values() if np.isfinite(pf['cyc'])])
    P(f'{_("method_note")} {cyc:.2f} s.')

    H(_('sec2'), 1)
    P(f'{_("sec2_desc")} ({int(G.get("main_win", (0.25, 0.90))[0] * 100)}–{int(G.get("main_win", (0.25, 0.90))[1] * 100)}%)')
    cvs = sorted({c for pf in per.values() for c in pf['cvstat']})
    qc_rows = []
    for run, pf in sort_runs(per):
        row = [run, pf['ms1'], pf['ms2'], f"{pf['cyc']:.2f}"]
        for c in cvs:
            stc = pf['cvstat'][c]
            row += [f"{stc['topn']:.1f}", f"{stc['rate']:.2f}%" if stc['rate'] else '-',
                    f"{stc['it_med']:.0f}/{stc['it_max']:.0f}", f"{stc['top_pct']:.1f}%",
                    f"{stc['fill_med']:.2f}"]
        qc_rows.append(row)
    cols = [_('fraction'), _('ms1_count'), _('ms2_count'), _('cycle_median')]
    for c in cvs:
        cols += [f'TopN@{c}', f'{_("id_rate")}@{c}', f'{_("it_med_max")}@{c}',
                 f'{_("it_saturation")}@{c}', f'{_("fill_median")}@{c}']
    T(qc_rows, cols)

    H(_('sec3'), 1)
    tot = G['totals']
    ov = G.get('overall')
    msg = f'{_("group_total")}：PSM {tot["PSM"]:,}；{_("col_pep")} {tot["肽段"]:,}；{_("col_prot")} {tot["蛋白"]:,}。'
    if ov:
        msg += f' {_("overall_rate")} {ov[2]:.2f}% ({ov[0]:,}/{ov[1]:,}).'
    P(msg)
    pf_rows = []
    for f in sorted(G.get('per_frac_id', {})):
        r = G['per_frac_id'][f]
        pf_rows.append([f'F{f}', f"{r['PSM']:,}", f"{r['肽段']:,}", f"{r['蛋白']:,}"])
    if pf_rows:
        P(_('per_frac_desc'))
        T(pf_rows, [_('fraction'), _('psm_count'), _('peptide_count'), _('protein_count')])
    qc = G.get('cleavage_qc')
    if qc and qc.get('psm'):
        _fmt = lambda v: '—' if v is None else f'{v:.2f}%'  # noqa: E731
        P(_('qc_desc'))
        rows = []
        for lv, q in ((_('psm_level'), qc['psm']), (_('peptide_level'), qc['pep'])):
            rows.append([lv, f"{q['n']:,}", _fmt(q['spec']), _fmt(q['mc0']),
                         _fmt(q['mc1']), _fmt(q['mc2']), _fmt(q['strict'])])
        T(rows, [_('level'), _('count'), _('fully_specific'), _('fully_cleaved'),
                 _('mc1'), _('mc2'), _('spec_mc0')])
        if qc.get('cv'):
            cv_rows = [[c, f"{q['n']:,}", _fmt(q['spec']), _fmt(q['mc0'])]
                       for c, q in sorted(qc['cv'].items()) if q]
            P(_('per_cv'))
            T(cv_rows, ['CV', _('psm_count'), _('fully_specific'), _('fully_cleaved')])

    H(_('sec4'), 1)
    rates = [stc['rate'] for pf in per.values() for stc in pf['cvstat'].values() if stc['rate']]
    if rates:
        P(f'{_("conclusion_rate")} {min(rates):.2f}–{max(rates):.2f}%；'
          f'{_("conclusion_cycle")} {cyc:.2f} s).')
    P(G.get('conclusion_ms', _('conclusion_default')))
    H(_('sec5'), 1)
    P(_('sec5_desc'))
    figs = [(_('fig_topn_summary'), f'{G["key"]}_fig_TopN{"解析率" if lang=="zh" else "_rate"}{"汇总" if lang=="zh" else "_summary"}.png'),
            (_('fig_agc_summary'), f'{G["key"]}_fig_AGC_Fill{"汇总" if lang=="zh" else "_summary"}.png'),
            (_('fig_rate_rt_summary'), f'{G["key"]}_fig_{"解析率随RT汇总" if lang=="zh" else "rate_vs_RT_summary"}.png'),
            (_('fig_mit_dist'), f'{G["key"]}_fig_MIT{"分布" if lang=="zh" else "_dist"}.png')]
    if any(len(pf.get('fwhm', [])) for pf in per.values()):
        figs.append((_('fig_fwhm_summary'), f'{G["key"]}_fig_{"半峰宽汇总" if lang=="zh" else "FWHM_summary"}.png'))
    for cap, fn in figs:
        p_ = os.path.join(FIG_SUM, fn)
        if os.path.exists(p_):
            doc.add_picture(p_, width=Inches(6.3))
            doc.add_paragraph(cap)

    out = os.path.join(OUT, f'{G["key"]}{_("fn_report")}')
    doc.save(out)
    print(f'{_("saved")}: {out}', flush=True)


# ---------------- 主流程 ----------------

def run_dataset(name):
    DS = DATASETS[name]
    OUT = DS['out']
    FIG_FRAC = os.path.join(OUT, 'figs_逐馏分')
    FIG_SUM = os.path.join(OUT, 'figs_汇总')
    FIG_BPC = os.path.join(OUT, 'figs_BPC')
    for d_ in (OUT, FIG_FRAC, FIG_SUM, FIG_BPC):
        os.makedirs(d_, exist_ok=True)
    sum_rows = []
    for gkey, G in DS['groups'].items():
        G = dict(G)
        G['key'] = gkey
        log(f'== {gkey} ==')
        ensure_method(G, OUT)
        agc, d, id_by = load_group(G)
        G['topn_cap'] = int(min(G.get('topn_cap', 25),
                                max(int(agc.loc[agc.msorder == 2, 'rank'].max() or 20), 10)))
        per = per_fraction_stats(G, agc, id_by)
        # 半峰宽（仅 has_ms1）
        if G.get('has_ms1'):
            for run, pf in per.items():
                stem = agc[agc.run == run]['stem'].iloc[0]
                gsub = d[d.frac == pf['frac']]
                rt_map = pf['rt_map']
                gg = gsub.assign(_rt=gsub['Scan_No'].map(rt_map)).dropna(subset=['_rt'])
                if not len(gg):
                    pf['fwhm'] = np.array([])
                    continue
                key = gg[['Sequence', 'Charge', 'Calc.MH+', '_rt']].drop_duplicates(['Sequence', 'Charge'])
                n = min(N_TARGET, len(key))
                key = key.sort_values('_rt').iloc[np.linspace(0, len(key) - 1, n).astype(int)]
                z = key['Charge'].clip(lower=1).values
                pmz = (key['Calc.MH+'].values + (z - 1) * 1.007276) / z
                tg = list(zip(pmz, key['_rt'].values, range(len(key))))
                ms1 = os.path.join(G['datadir'], stem + '.ms1')
                res = xic_stream(ms1, tg, rt_map, want_apex=False) if os.path.exists(ms1) else {}
                pf['fwhm'] = np.array([v['fwhm'] for v in res.values() if 'fwhm' in v])
        # 无 ms1 数据集：rawdump --xic RAW 直读补半峰宽（口径与 .ms1 xic_stream 一致）
        if not G.get('has_ms1'):
            G['fwhm_src'] = 'rawdump-xic'
            for run, pf in per.items():
                stem = agc[agc.run == run]['stem'].iloc[0]
                gsub = d[d.frac == pf['frac']]
                rt_map = pf['rt_map']
                gg = gsub.assign(_rt=gsub['Scan_No'].map(rt_map)).dropna(subset=['_rt'])
                if not len(gg):
                    pf['fwhm'] = np.array([])
                    continue
                key = gg[['Sequence', 'Charge', 'Calc.MH+', '_rt']].drop_duplicates(['Sequence', 'Charge'])
                n = min(N_TARGET, len(key))
                key = key.sort_values('_rt').iloc[np.linspace(0, len(key) - 1, n).astype(int)]
                z = key['Charge'].clip(lower=1).values
                pmz = (key['Calc.MH+'].values + (z - 1) * 1.007276) / z
                tg = [(float(m), float(r), i, int(zz))
                      for i, (m, r, zz) in enumerate(zip(pmz, key['_rt'].values, z))]
                res = xic_raw.xic(G['datadir'], stem, tg)
                pf['fwhm'] = np.array([v['fwhm'] for v in res.values() if 'fwhm' in v])
        else:
            G['fwhm_src'] = 'ms1'
        # 自切肽标注
        per_ann = {}
        if G.get('autol_pat'):
            enz = G['enz_df']
            for run, pf in per.items():
                rt_map = pf['rt_map']
                rt = pf['m1s']['rt_min'].values
                bp = pf['bp']
                ann = []
                sub = enz[enz.frac == pf['frac']]
                for (seq, chg), gg in sub.groupby(['Sequence', 'Charge']):
                    rts = gg['Scan_No'].map(lambda s: rt_map.get(int(s))).dropna()
                    if not len(rts):
                        continue
                    x = float(rts.median())
                    mh = float(gg['Calc.MH+'].iloc[0])
                    ann.append(dict(seq=seq, chg=int(chg), rt=x, int=float(np.interp(x, rt, bp)),
                                    mh=mh, n=len(gg)))
                if G.get('has_ms1') and ann:
                    ms1f = os.path.join(G['datadir'], agc[agc.run == run]['stem'].iloc[0] + '.ms1')
                    if os.path.exists(ms1f):
                        tg = []
                        for i2, a in enumerate(ann):
                            z2 = max(int(a['chg']), 1)
                            tg.append(((a['mh'] + (z2 - 1) * 1.007276) / z2, a['rt'], i2))
                        ap = xic_stream(ms1f, tg, rt_map, want_apex=True)
                        for i2, a in enumerate(ann):
                            if i2 in ap:
                                a['rt'], a['int'] = ap[i2]['apex']
                elif ann:
                    # 无 ms1：rawdump --xic RAW 直读取 apex（替代 PSM RT 回退）
                    _stem = agc[agc.run == run]['stem'].iloc[0]
                    _tg = []
                    for i2, a in enumerate(ann):
                        z2 = max(int(a['chg']), 1)
                        _tg.append(((a['mh'] + (z2 - 1) * 1.007276) / z2,
                                    a['rt'], i2, z2))
                    _ap = xic_raw.xic(G['datadir'], _stem, _tg)
                    for i2, a in enumerate(ann):
                        if i2 in _ap:
                            a['rt'], a['int'] = _ap[i2]['apex']
                per_ann[run] = sorted(ann, key=lambda a: a['rt'])
        for run, pf in sort_runs(per):
            frac_quad(G, run, pf, FIG_FRAC)
            bpc_fig(G, run, pf, per_ann.get(run, []), FIG_BPC)
        cvs = summary_figs(G, per, FIG_SUM)
        mit_dist_fig(G, per, FIG_SUM)
        gen_report(G, per, OUT, FIG_SUM)
        pd.DataFrame([dict(馏分=f'F{f}', **G['per_frac_id'][f])
                      for f in sorted(G.get('per_frac_id', {}))]).to_csv(
            os.path.join(OUT, f'鉴定明细_逐馏分_{gkey}.tsv'), sep='	', index=False)
        row = dict(组=G['label'], 馏分数=len(per))
        for c in cvs:
            stcs = [pf['cvstat'][c] for pf in per.values() if c in pf['cvstat']]
            row[f'TopN均值@{c}'] = round(float(np.mean([s['topn'] for s in stcs])), 2)
            rr_ = [s['rate'] for s in stcs if s['rate']]
            row[f'解析率范围@{c}'] = f'{min(rr_):.2f}-{max(rr_):.2f}%' if rr_ else ''
            row[f'触顶均值%@{c}'] = round(float(np.mean([s['top_pct'] for s in stcs])), 1)
        row.update(PSM=G['totals']['PSM'], 肽段=G['totals']['肽段'], 蛋白=G['totals']['蛋白'])
        if G.get('overall'):
            row['Overall解析率%'] = G['overall'][2]
        _qc = (G.get('cleavage_qc') or {}).get('psm')
        if _qc:
            row['完全特异性%'] = round(_qc['spec'], 2)
            row['全酶切%'] = round(_qc['mc0'], 2)
        sum_rows.append(row)
        log(f'{gkey} 完成')
    pd.DataFrame(sum_rows).to_csv(os.path.join(OUT, '组级汇总.tsv'), sep='\t', index=False)
    log('数据集完成 → ' + OUT)


# ---------------- 数据集定义（新增数据集照此加条目） ----------------
# 组条目通用键：datadir（raw 目录）/ result / frac_pat / id_pat / autol_pat / autol_cn
# 引擎：默认 pFind（result=pFind 任务 result 目录）；
#   engine='maxquant' 时 result=msms.txt（或其所在目录），解析率改用 rawdump 整针口径，
#   Reverse/污染物自动剔除，漏切取 Missed cleavages（特异性列 MaxQuant 无，表内显示 —）。

def _ntm_group(label, enz, color, datadir, result, autol_pat, autol_cn, frac_pat, id_pat):
    return dict(label=label, enz=enz, color=color,
                cv_colors={'45V': color, '65V': 'tab:orange' if color == 'tab:red' else 'tab:cyan'},
                cv_off={'45V': -1, '65V': 1},
                datadir=datadir, result=result,
                frac_pat=frac_pat, id_pat=id_pat,
                autol_pat=autol_pat, autol_cn=autol_cn, dump_all=True)


DATASETS = {
    'NTM': dict(
        out=r'E:\test\NTM\评估产出',
        groups={
            'Mab_LL': _ntm_group('Mab_LL（脓肿分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                                 r'E:\test\NTM\Mab\TCL\LL\original',
                                 r'E:\test\NTM\pFind_results\20260914_Mab_TCL_LL_ALL_ncbi\result',
                                 'CON_SL_LysN|CON_LysargiNase', 'LysargiNase/Lys-N 酶自切肽', r'_Mixture_(\d+)', r'_Mixture_(\d+)_(\d+)V'),
            'Mab_TL': _ntm_group('Mab_TL（脓肿分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                                 r'E:\test\NTM\Mab\TCL\TL\original',
                                 r'E:\test\NTM\pFind_results\20260915_Mab_TCL_TL_ALL_ncbi\result',
                                 r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN', '蛋白酶自切肽',
                                 r'_Mixture_(\d+)', r'_Mixture_(\d+)_(\d+)V'),
            'Mch_LL': _ntm_group('Mch_LL（龟分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                                 r'E:\test\NTM\Mch\TCL\LL\original',
                                 r'E:\test\NTM\pFind_results\20260915_Mch_TCL_LL_ALL_ncbi\result',
                                 'CON_SL_LysN|CON_LysargiNase', 'LysargiNase/Lys-N 酶自切肽', r'_M(\d+)$', r'_M(\d+)_(\d+)V'),
            'Mch_TL': _ntm_group('Mch_TL（龟分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                                 r'E:\test\NTM\Mch\TCL\TL\original',
                                 r'E:\test\NTM\pFind_results\20260915_Mch_TCL_TL_ALL_ncbi\result',
                                 r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN', '蛋白酶自切肽',
                                 r'_M(\d+)$', r'_M(\d+)_(\d+)V'),
        }),
    '913': dict(
        out=r'E:\test\评估产出',
        groups={
            '913T': dict(label='913T（Trypsin 酶切）', enz='Trypsin（KR_C）', color='tab:blue',
                         cv_colors={'CV': 'tab:blue'}, cv_off={'CV': 0}, has_ms1=True,
                         instrument='Q Exactive HF 2号（HF02）', eval_date='2026-10-17',
                         conclusion_ms='（2）913 数据 MS2 注入时间触顶约 50%（T MIT 60 ms / R MIT 120 ms），'
                                       '离子量部分受 MIT 限制；主洗脱段各 rank 解析率基本持平，'
                                       'rank1–2 因 AGC 提前打满、注入偏短而略低。',
                         datadir=r'E:\test\913T', result=r'E:\test\913T\913T\result',
                         frac_pat=r'_F(\d+)_90min', id_pat=r'_F(\d+)_90min',
                         autol_pat=r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN|XP_028892624', autol_cn='酶自切肽'),
            '913R': dict(label='913R（LysargiNase 酶切）', enz='LysargiNase（R29_KR_N）', color='tab:red',
                         cv_colors={'CV': 'tab:red'}, cv_off={'CV': 0}, has_ms1=True,
                         instrument='Q Exactive HF 2号（HF02）', eval_date='2026-10-17',
                         conclusion_ms='（2）913 数据 MS2 注入时间触顶约 50%（T MIT 60 ms / R MIT 120 ms），'
                                       '离子量部分受 MIT 限制；主洗脱段各 rank 解析率基本持平，'
                                       'rank1–2 因 AGC 提前打满、注入偏短而略低。',
                         datadir=r'E:\test\913R', result=r'E:\test\913R\913R\result',
                         frac_pat=r'_F(\d+)_90min', id_pat=r'_F(\d+)_90min',
                         autol_pat=r'CON_SL_LysN|CON_LysargiNase|XP_028892624', autol_cn='LysargiNase/Lys-N 酶自切肽'),
        }),
}

# NTM LL: enzyme mini-DB search results merged into autolysis annotation
DATASETS['NTM']['groups']['Mab_LL']['enz_extra'] = [
    r'E:\test\NTM\enzyme_search\Mab_LL_enz\result\pFind-Filtered.spectra']
DATASETS['NTM']['groups']['Mch_LL']['enz_extra'] = [
    r'E:\test\NTM\enzyme_search\Mch_LL_enz\result\pFind-Filtered.spectra']

# 胃分枝杆菌 M. gastri LL（2026-10-30）：两针（R1 −45/−65V，R2 −45/−60V），
# pFind 主搜结果随数据自带（LLR1/LLR2 任务）；酶小库 Mga_LL_enz 补自切标注
def _mga_group(label, cv2, datadir, result):
    return dict(label=label, enz='LysargiNase+LysN 混合酶切（R29_KR_N）', color='tab:red',
                cv_colors={'45V': 'tab:red', cv2: 'tab:orange'},
                cv_off={'45V': -1, cv2: 1},
                instrument='Orbitrap Exploris 480（FAIMS 双 CV）', eval_date='2026-10-30',
                datadir=datadir, result=result,
                frac_pat=r'_R(\d)_(\d+)V', id_pat=r'_R(\d)_(\d+)V',
                autol_pat='CON_SL_LysN|CON_LysargiNase',
                autol_cn='LysargiNase/Lys-N 酶自切肽',
                fasta=r'E:\test\Mga_LL_20261030\MGastri_protein_ncbi_con.fasta',
                enz_rule='KR_N')


DATASETS['Mga'] = dict(
    out=r'E:\test\Mga_LL_20261030\评估产出',
    groups={
        'Mga_LL_R1': _mga_group('Mga_LL_R1（胃分枝杆菌 LL 第1针 −45/−65V）', '65V',
                                r'E:\test\Mga_LL_20261030\raw\R1',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR1\result'),
        'Mga_LL_R2': _mga_group('Mga_LL_R2（胃分枝杆菌 LL 第2针 −45/−60V）', '60V',
                                r'E:\test\Mga_LL_20261030\raw\R2',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR2\result'),
    })
DATASETS['Mga']['groups']['Mga_LL_R1']['enz_extra'] = [
    r'E:\test\Mga_LL_20261030\enzyme_search\Mga_LL_enz\result\pFind-Filtered.spectra']
DATASETS['Mga']['groups']['Mga_LL_R2']['enz_extra'] = [
    r'E:\test\Mga_LL_20261030\enzyme_search\Mga_LL_enz\result\pFind-Filtered.spectra']

# English version for testing (same data, English labels → auto-detect 'en')
DATASETS['MgaEN'] = dict(
    out=r'E:\test\Mga_LL_20261030\评估产出_EN',
    groups={
        'Mga_LL_R1': _mga_group('Mga_LL_R1 (M. gastri, injection 1, -45/-65V)', '65V',
                                r'E:\test\Mga_LL_20261030\raw\R1',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR1\result'),
        'Mga_LL_R2': _mga_group('Mga_LL_R2 (M. gastri, injection 2, -45/-60V)', '60V',
                                r'E:\test\Mga_LL_20261030\raw\R2',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR2\result'),
    })
DATASETS['MgaEN']['groups']['Mga_LL_R1']['enz'] = 'LysargiNase+LysN mixed digestion (R29_KR_N)'
DATASETS['MgaEN']['groups']['Mga_LL_R2']['enz'] = 'LysargiNase+LysN mixed digestion (R29_KR_N)'
DATASETS['MgaEN']['groups']['Mga_LL_R1']['instrument'] = 'Orbitrap Exploris 480 (FAIMS dual CV)'
DATASETS['MgaEN']['groups']['Mga_LL_R2']['instrument'] = 'Orbitrap Exploris 480 (FAIMS dual CV)'
DATASETS['MgaEN']['groups']['Mga_LL_R1']['lang'] = 'en'
DATASETS['MgaEN']['groups']['Mga_LL_R2']['lang'] = 'en'
DATASETS['MgaEN']['groups']['Mga_LL_R1']['enz_extra'] = DATASETS['Mga']['groups']['Mga_LL_R1']['enz_extra']
DATASETS['MgaEN']['groups']['Mga_LL_R2']['enz_extra'] = DATASETS['Mga']['groups']['Mga_LL_R2']['enz_extra']

# QE 消化效率检测（2026-10-19）：三物种 TCL 消化物 QE 单针 ×LL/TL；Mga_TL 无 raw 不配置
def _qe_group(label, enz, color, datadir, result, raw_filter=None):
    return dict(label=label, enz=enz, color=color,
                cv_colors={'CV': color}, cv_off={'CV': 0},
                datadir=datadir, result=result,
                frac_pat=None, id_pat=None, raw_filter=raw_filter,
                autol_pat=None, autol_cn='', has_ms1=False,
                instrument='Q Exactive（单针，无 FAIMS）', eval_date='2026-10-19',
                conclusion_ms='（2）QE 单针数据采集健康：AGC Fill 中位 1.0、注入时间触顶比例低'
                              '（0.3–15.1%），离子预算由 AGC 目标决定（非 MIT 受限）；'
                              '主洗脱段各 rank 解析率平稳，谱图质量对前体强度不敏感。')


DATASETS['QEXH'] = dict(
    out=r'E:\test\2026.10.19_QE消化效率检测\评估产出\参数评估',
    groups={
        'QE_Mab_LL': _qe_group('QE_Mab_LL（脓肿分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                               r'E:\test\2026.10.19_QE消化效率检测\Mab',
                               r'E:\test\2026.10.19_QE消化效率检测\Mab\20260929_Mab_TCL_LL_Elu\result',
                               'LL_ELU'),
        'QE_Mab_TL': _qe_group('QE_Mab_TL（脓肿分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                               r'E:\test\2026.10.19_QE消化效率检测\Mab',
                               r'E:\test\2026.10.19_QE消化效率检测\Mab\20260929_Mab_TCL_TL_test\result',
                               'Mab_TL_test'),
        'QE_Mch_LL': _qe_group('QE_Mch_LL（龟分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                               r'E:\test\2026.10.19_QE消化效率检测\Mch',
                               r'E:\test\2026.10.19_QE消化效率检测\Mch\mchlltest\result',
                               'Mch_LL_test'),
        'QE_Mch_TL': _qe_group('QE_Mch_TL（龟分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                               r'E:\test\2026.10.19_QE消化效率检测\Mch',
                               r'E:\test\2026.10.19_QE消化效率检测\Mch\MCH-tltest\result',
                               'Mch_TL_test'),
        'QE_Mga_LL': _qe_group('QE_Mga_LL（胃分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                               r'E:\test\2026.10.19_QE消化效率检测\Mga',
                               r'E:\test\2026.10.19_QE消化效率检测\Mga\20261003_Mgastri_TCL_LL_test\result',
                               None),
    })

if __name__ == '__main__':
    run_dataset(sys.argv[1] if len(sys.argv) > 1 else 'NTM')
