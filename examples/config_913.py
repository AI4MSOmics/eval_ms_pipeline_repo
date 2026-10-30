# 示例配置：913 耳念菌双酶切（QE HF 2号，无 FAIMS，13 馏分，有 ms1）
# 913R=LysargiNase（R29_KR_N），913T=Trypsin（KR_C）

DATASETS['913'] = dict(
    out=r'E:\test\评估产出',
    groups={
        '913T': dict(label='913T（Trypsin 酶切）', enz='Trypsin（KR_C）', color='tab:blue',
                     cv_colors={'CV': 'tab:blue'}, cv_off={'CV': 0}, has_ms1=True,
                     instrument='Q Exactive HF 2号（HF02）', eval_date='2026-10-17',
                     datadir=r'E:\test\913T', result=r'E:\test\913T\913T\result',
                     frac_pat=r'_F(\d+)_90min', id_pat=r'_F(\d+)_90min',
                     autol_pat=r'TRYP_PIG|TRY1_BOVIN|IPI00011694|LYSC_LYSEN|XP_028892624',
                     autol_cn='酶自切肽'),
        '913R': dict(label='913R（LysargiNase 酶切）', enz='LysargiNase（R29_KR_N）', color='tab:red',
                     cv_colors={'CV': 'tab:red'}, cv_off={'CV': 0}, has_ms1=True,
                     instrument='Q Exactive HF 2号（HF02）', eval_date='2026-10-17',
                     datadir=r'E:\test\913R', result=r'E:\test\913R\913R\result',
                     frac_pat=r'_F(\d+)_90min', id_pat=r'_F(\d+)_90min',
                     autol_pat=r'CON_SL_LysN|CON_LysargiNase|XP_028892624',
                     autol_cn='LysargiNase/Lys-N 酶自切肽'),
    })
