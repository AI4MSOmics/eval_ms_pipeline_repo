# 示例配置：胃分枝杆菌 M. gastri LL（FAIMS 双 CV，无 ms1 → rawdump-xic 半峰宽）
# 适配数据：E:\test\Mga_LL_20261030（两针 R1 −45/−65V、R2 −45/−60V，78 min）

def _mga_group(label, cv2, datadir, result):
    return dict(label=label, enz='LysargiNase+LysN 混合酶切（R29_KR_N）', color='tab:red',
                cv_colors={'45V': 'tab:red', cv2: 'tab:orange'},
                cv_off={'45V': -1, cv2: 1},
                instrument='Orbitrap Exploris 480（FAIMS 双 CV）', eval_date='2026-10-30',
                datadir=datadir, result=result,
                frac_pat=r'_R(\d)_(\d+)V', id_pat=r'_R(\d)_(\d+)V',
                autol_pat='CON_SL_LysN|CON_LysargiNase',
                autol_cn='LysargiNase/Lys-N 酶自切肽')

DATASETS['Mga'] = dict(
    out=r'E:\test\Mga_LL_20261030\评估产出',
    groups={
        'Mga_LL_R1': _mga_group('Mga_LL_R1（−45/−65V）', '65V',
                                r'E:\test\Mga_LL_20261030\raw\R1',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR1\result'),
        'Mga_LL_R2': _mga_group('Mga_LL_R2（−45/−60V）', '60V',
                                r'E:\test\Mga_LL_20261030\raw\R2',
                                r'E:\test\Mga_LL_20261030\raw\20261029_Mgastri_LLR2\result'),
    })
