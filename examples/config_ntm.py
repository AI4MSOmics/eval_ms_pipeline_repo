# 示例配置：NTM 四组（脓肿 Mab/龟 Mch × LL/TL，FAIMS −45/−65V，6 馏分）
# 酶小库搜库结果经 enz_extra 并入（LL 组库内无酶条目）
# 注意：NTM 数据无 ms1 文件 → 半峰宽自动走 rawdump-xic

def _ntm_group(label, enz, color, datadir, result, autol_pat, autol_cn):
    return dict(label=label, enz=enz, color=color,
                cv_colors={'45V': color, '65V': 'tab:orange' if color == 'tab:red' else 'tab:cyan'},
                cv_off={'45V': -1, '65V': 1},
                datadir=datadir, result=result,
                frac_pat=r'_Mixture_(\d+)', id_pat=r'_Mixture_(\d+)_(\d+)V',
                autol_pat=autol_pat, autol_cn=autol_cn, dump_all=True)

DATASETS['NTM'] = dict(
    out=r'E:\test\NTM\评估产出',
    groups={
        'Mab_LL': _ntm_group('Mab_LL（脓肿分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                             r'E:\test\NTM\Mab\TCL\LL\original',
                             r'E:\test\NTM\pFind_results\20260914_Mab_TCL_LL_ALL_ncbi\result',
                             'CON_SL_LysN|CON_LysargiNase', 'LysargiNase/Lys-N 酶自切肽'),
        'Mab_TL': _ntm_group('Mab_TL（脓肿分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                             r'E:\test\NTM\Mab\TCL\TL\original',
                             r'E:\test\NTM\pFind_results\20260915_Mab_TCL_TL_ALL_ncbi\result',
                             r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN', '蛋白酶自切肽'),
        'Mch_LL': _ntm_group('Mch_LL（龟分枝杆菌 LL）', 'LysargiNase+LysN 混合酶切', 'tab:red',
                             r'E:\test\NTM\Mch\TCL\LL\original',
                             r'E:\test\NTM\pFind_results\20260915_Mch_TCL_LL_ALL_ncbi\result',
                             'CON_SL_LysN|CON_LysargiNase', 'LysargiNase/Lys-N 酶自切肽'),
        'Mch_TL': _ntm_group('Mch_TL（龟分枝杆菌 TCL）', 'Trypsin+LysC 混合酶切', 'tab:blue',
                             r'E:\test\NTM\Mch\TCL\TL\original',
                             r'E:\test\NTM\pFind_results\20260915_Mch_TCL_TL_ALL_ncbi\result',
                             r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN', '蛋白酶自切肽'),
    })

# LL 组酶小库搜库结果（库内无酶条目 → 单独小库搜）
DATASETS['NTM']['groups']['Mab_LL']['enz_extra'] = [
    r'E:\test\NTM\enzyme_search\Mab_LL_enz\result\pFind-Filtered.spectra']
DATASETS['NTM']['groups']['Mch_LL']['enz_extra'] = [
    r'E:\test\NTM\enzyme_search\Mch_LL_enz\result\pFind-Filtered.spectra']
