# -*- coding: utf-8 -*-
# 2.4.1 SCL 云掩膜
#
# 背景：
# Sentinel-2 L2A 自带 SCL（Scene Classification Layer）波段，由 Sen2Cor 生成。
# 每个像元有类别码，云/云影/卷云/雪/无数据可直接据此掩膜，无需自行计算。
# SCL 是 20 m 分辨率，B04/B08 是 10 m，读取时用 out_shape 重采样到 10 m 网格。
#
# SCL 类别码（只列与本任务相关的）：
#   0  NO_DATA
#   1  饱和/缺陷
#   3  云影（必须掩，否则阴影 NDVI 虚低被误判退化）
#   4  植被
#   5  裸土
#   6  水体
#   8  中概率云
#   9  高概率云
#  10  薄卷云（单期分析建议掩；时序中值合成可保留）
#  11  雪
#
# 目标：
#   从已下载的 ndvi_real.tif 出发，用 SCL 生成云掩膜，把云/云影/卷云像元置为 NaN，
#   输出 ndvi_cloudfree.tif，并打印掩膜前后的统计对比（云量占比、NDVI 均值变化）。

import os
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

# ---------- 步骤 1：定位与已选影像一致的 SCL 资源 ----------
# 重新打开 STAC，选出和 step3 相同的那景影像（2025-08-08, T50RNQ），
# 取其 assets['SCL'].href。
# 提示：和 step3 的 2.2.2 选景代码完全一致，复制过来即可。
import pystac_client
import planetary_computer
from shapely.geometry import shape,Point

catalog=pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)
search=catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[117.9,26.4,118.1,26.6],
    datetime="2025-07-01/2025-08-31",
    query={"eo:cloud_cover":{"lt":10}}
)
items=list(search.items())

print("搜到影像数量:", len(items))              # 看是不是 0
for it in items[:10]:                           # 打印前 10 景的 id
    print("  ", it.id)

selected=[it for it in items
          if "20250808" in it.id and "T50RNQ" in it.id][0]

scl_href = selected.assets['SCL'].href
print("选定影像:", selected.id)
print("SCL 链接:", scl_href)
print("可用波段:", list(selected.assets.keys()))
# ---------- 步骤 2：读取 SCL 并重采样到 10 m ----------
# 打开 SCL（20 m），但用 out_shape=(2231, 2010) 让 rasterio 自动重采样到 10 m。
# 注意：SCL 是类别数据，重采样方法应为 nearest（默认对整数波段是 nearest）。
# 读出来的 scl 数组 shape 应为 (2231, 2010)，dtype uint8。
bbox=(117.9,26.4,118.1,26.6)
with rasterio.open(scl_href) as src:
    print("SCL 原始分辨率:", src.res)
    print("SCL 原始形状:", (src.height, src.width))
    left, bottom, right, top = transform_bounds("EPSG:4326", src.crs, *bbox)
    window = from_bounds(left, bottom, right, top, transform=src.transform)
    print("SCL 窗口行列:", window.height, window.width)
    scl = src.read(1, window=window, out_shape=(2231, 2010))

print("SCL 重采样后形状:", scl.shape)
print("SCL dtype:", scl.dtype)
print("SCL 唯一值:", np.unique(scl))
# ---------- 步骤 3：构建云掩膜 ----------
# 定义需要掩膜的类别集合：{0, 1, 3, 8, 9, 10, 11}
# 用 np.isin(scl, [0,1,3,8,9,10,11]) 得到 bool 数组 cloud_mask（True=要掩膜）。
# 打印掩膜像元占比（cloud_mask.sum() / cloud_mask.size * 100），预期约 5~6%。
cloud_mask=np.isin(scl,[0,1,3,8,9,10,11])
print("掩膜像素元数:",int(cloud_mask.sum()))
print("掩膜占比：%.2f%%" % (cloud_mask.sum()/cloud_mask.size*100))

# ---------- 步骤 4：读入 ndvi_real.tif ----------
# 读 data/ndvi_real.tif 的第 1 波段，注意里面 nodata=-9999，需先还原成 NaN 再掩膜。
# 即：ndvi = np.where(ndvi < -1, np.nan, ndvi)  —— NDVI 物理范围 [-1,1]，低于 -1 都是 nodata。
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir=os.path.join(script_dir,"data")
ndvi_path=os.path.join(data_dir,"ndvi_real.tif")

with rasterio.open(ndvi_path) as src:
    print("NDVI dtype:",src.dtypes[0])
    print("NDVI nodata:",src.nodata)
    ndvi = src.read(1)

print("NDVI形状:",ndvi.shape)

ndvi=np.where(ndvi<-1,np.nan,ndvi)
print("NaN像元数:",int(np.isnan(ndvi).sum()))
# ---------- 步骤 5：应用云掩膜 ----------
# np.where(cloud_mask, np.nan, ndvi) → ndvi_cloudfree
# 打印掩膜前后的 NDVI 均值、标准差、有效像元数对比。
# 预期：掩膜后有效像元数减少 ~5%，NDVI 均值略升（云区 NDVI 偏低被剔除）。
before_valid=np.sum(~np.isnan(ndvi))
before_mean=np.nanmean(ndvi)
before_std=np.nanstd(ndvi)

ndvi_cloudfree=np.where(cloud_mask,np.nan,ndvi)

after_valid=np.sum(~np.isnan(ndvi_cloudfree))
after_mean=np.nanmean(ndvi_cloudfree)
after_std=np.nanstd(ndvi_cloudfree)

print("掩膜前: 有效像元 %d | 均值 %.4f | 标准差 %.4f"
      % (before_valid, before_mean, before_std))
print("掩膜后: 有效像元 %d | 均值 %.4f | 标准差 %.4f"
      % (after_valid, after_mean, after_std))
print("减少像元 %d (%.2f%%)"
      % (before_valid - after_valid,
         (before_valid - after_valid) / before_valid * 100))
# ---------- 步骤 6：保存 ndvi_cloudfree.tif ----------
# profile 从 ndvi_real.tif 拷贝，dtype float32，nodata=-9999。
# NaN 换成 -9999 再写盘。
out_path=os.path.join(data_dir,"ndvi_cloudfree.tif")

with rasterio.open(ndvi_path) as src:
    profile= src.profile.copy()

profile.update(dtype="float32",nodata=-9999,count=1)

ndvi_out=np.where(np.isnan(ndvi_cloudfree),-9999,ndvi_cloudfree).astype("float32")

with rasterio.open(out_path,"w",**profile) as dst:
    dst.write(ndvi_out,1)

print("已保存:", out_path)
print("数组 dtype:", ndvi_out.dtype)
print("NaN 残留:", int(np.isnan(ndvi_out).sum()))    
# ---------- 步骤 7：出图对比 ----------
# 并排画两张子图：左图原始 NDVI，右图 cloudfree NDVI。
# 用同一套 cmap/vmin/vmax 保证可比。
# 标题分别标注"原始"和"云掩膜后"。
# 保存到 data/ndvi_cloudfree_comparison.png。
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

vmin, vmax = -1.0, 1.0

fig, axes = plt.subplots(1, 2, figsize=(14, 6))

im0 = axes[0].imshow(ndvi, cmap="RdYlGn", vmin=vmin, vmax=vmax)
axes[0].set_title("原始 NDVI")
axes[0].axis("off")

im1 = axes[1].imshow(ndvi_cloudfree, cmap="RdYlGn", vmin=vmin, vmax=vmax)
axes[1].set_title("SCL 云掩膜后")
axes[1].axis("off")

fig.colorbar(im1, ax=axes, fraction=0.025, pad=0.01, label="NDVI")

out_png = os.path.join(data_dir, "ndvi_cloudfree_comparison.png")
plt.savefig(out_png, dpi=150, bbox_inches="tight")
plt.close()

print("已保存图:", out_png)