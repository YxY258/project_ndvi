# -*- coding: utf-8 -*-
# 2.3 用真实 Sentinel-2 数据算 NDVI
import os
import numpy as np
import rasterio
import matplotlib.pyplot as plt
# 导入：os、numpy as np、rasterio、matplotlib.pyplot as plt

# ---------- 步骤 1：读入本地两个波段 ----------
# 拼出 data 文件夹路径（和 2.2.2 同款写法）
data_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)),'data')

# 打开 B04.tif：read(1) 读出红光 DN 数组 red_dn；profile 拷贝一份备用
with rasterio.open(os.path.join(data_dir,'B04.tif'))as src:
    red_dn=src.read(1)
    profile = src.profile.copy()
# 打开 B08.tif：read(1) 读出近红外 DN 数组 nir_dn（形状和 B04 完全一致）
with rasterio.open(os.path.join(data_dir,'B08.tif'))as src:
    nir_dn=src.read(1)
# 打印两个数组的 shape 和 dtype（预期都是 (2231, 2010) uint16）
print("red",red_dn.shape,red_dn.dtype,"| nir:",nir_dn.shape,nir_dn.dtype)
# ---------- 步骤 2：DN → 反射率（先 astype 防下溢，再减 1000 修偏移、除 10000） ----------
# DN=0 是 nodata，先用布尔掩膜记下有效像元（& 是逐元素与，和 and 不同）
valid=(red_dn>0)&(nir_dn>0)
# 先转 float32（否则 693-1000 会 uint16 下溢！），减 1000 修新基线偏移，除 10000 转反射率
red=(red_dn.astype(np.float32)-1000.0)/10000.0
nir=(nir_dn.astype(np.float32)-1000.0)/10000.0
# 打印 red/nir 反射率范围（red 预期约 -0.03 ~ 1.72）
print("red反射率:%.3f ~ %.3f"%(np.nanmin(red),np.nanmax(red)))
print("nir反射率:%.3f ~ %.3f"%(np.nanmin(nir),np.nanmax(nir)))
# ---------- 步骤 3：算 NDVI ----------
# 分母可能为 0，用 errstate 压掉警告（阶段 1 用过）
with np.errstate(divide='ignore',invalid='ignore'):
    ndvi=(nir-red)/(nir+red)
# 无效像元统一设为 NaN：np.where(条件, 真值, 假值)，向量化版三元表达式
ndvi=np.where(valid,ndvi,np.nan)
# 打印 NDVI 范围和林地占比 (ndvi > 0.6).sum() / valid.sum() * 100
print("NDVI:%.3f ~ %.3f"%(np.nanmin(ndvi),np.nanmax(ndvi)))
print("林地占比(NDVI>0.6): %.1f%%"%((ndvi>0.6).sum()/valid.sum()*100))

# ---------- 步骤 4：存成 ndvi.tif ----------
# profile.update：dtype='float32'、nodata=-9999.0、count=1
profile.update(dtype='float32',nodata=-9999.0,count=1)
# NaN 换成 -9999 再写盘（transform/crs 自动继承，ndvi.tif 天生带地理定位）
ndvi_out=np.where(np.isnan(ndvi),-9999.0,ndvi).astype(np.float32)
# 写模式 rasterio.open(out_path, 'w', **profile)，dst.write(ndvi_out, 1)
out_path = os.path.join(data_dir,'ndvi_real.tif')
with rasterio.open(out_path,'w',**profile) as dst:
    dst.write(ndvi_out,1)
print("已保存:",out_path)    
# ---------- 步骤 5：出图（照抄 1.4 模板） ----------
# 中文黑体 SimHei + 负号正常显示（plt.rcParams 两行）
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
# imshow 画 NaN 版 ndvi（不是 ndvi_out！），cmap='RdYlGn'，vmin=-1 vmax=1
plt.figure(figsize=(10, 9))
plt.imshow(ndvi, cmap='RdYlGn', vmin=-1, vmax=1)
# colorbar + 标题「样地周边真实 NDVI（Sentinel-2，2025-08-08）」
plt.colorbar(label='NDVI')
plt.title('样地周边真实 NDVI（Sentinel-2，2025-08-08）')
# savefig 存 data/ndvi_real.png（dpi=150），必须在 show 之前
plt.savefig(os.path.join(data_dir, 'ndvi_real.png'), dpi=150, bbox_inches='tight')
plt.show()
