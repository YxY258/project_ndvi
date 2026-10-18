# -*- coding: utf-8 -*-
"""
课题三：1.3 造红光+近红外两个波段，计算 NDVI 并存盘
场景：中心密林、周围裸土、左上角水体
"""
import os
import numpy as np
import rasterio
from rasterio.transform import from_origin

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

np.random.seed(42)
H = W = 200
transform = from_origin(117.9, 26.6, 0.0001, 0.0001)

# ---- 造空间结构：每个像元到中心点的距离 ----
y_idx = np.arange(H)#等差数列，行数
x_idx = np.arange(W)#等差数列，列数
xx, yy=np.meshgrid(x_idx,y_idx)#铺开成行和列，x为列,y为行，点（1，1）行为yy（1,1）,列为xx(1,1)

cx,cy,radius=100,100,60#中心点坐标及范围
dist = np.sqrt((xx-cx)**2+ (yy-cy)**2)

forest=dist<=radius
water=(xx<40)&(yy<40)
print('密林像元数',forest.sum())
print('水体像元数',water.sum())
print('forest数组类型',forest.dtype)
print('dist[0,0]（左上角到圆心的距离）: %.1f' % dist[0, 0])

# ---- 红光/近红外：先铺裸土基底，再覆盖森林和水体 ----
red = np.random.uniform(0.12, 0.25, (H, W)).astype('float32')   # 裸土：红光较高
nir = np.random.uniform(0.15, 0.28, (H, W)).astype('float32')   # 裸土：近红外略高

red[forest] = np.random.uniform(0.02, 0.06, forest.sum())       # 森林：红光被叶绿素吸收
nir[forest] = np.random.uniform(0.40, 0.55, forest.sum())       # 森林：近红外强烈反射

red[water] = np.random.uniform(0.01, 0.03, water.sum())         # 水体：两个波段都吸收
nir[water] = np.random.uniform(0.005, 0.015, water.sum())       # 近红外吸收得更狠

bare = (~forest) & (~water)   # 既不是森林也不是水体的像元 = 裸土
print('裸土像元数:', bare.sum())
print('森林 red 均值: %.3f, nir 均值: %.3f' % (red[forest].mean(), nir[forest].mean()))
print('水体 red 均值: %.3f, nir 均值: %.3f' % (red[water].mean(), nir[water].mean()))
print('裸土 red 均值: %.3f, nir 均值: %.3f' % (red[bare].mean(), nir[bare].mean()))

# ---- 计算 NDVI ----
denominator = nir + red
with np.errstate(divide='ignore', invalid='ignore'):   # 只屏蔽告警，不改变计算结果
    ndvi = ((nir - red) / denominator).astype('float32')
ndvi[denominator==0]=-9999.0 #像元被破坏

# ---- 存盘：3 个文件共用同一套元数据 ----
profile={
    'driver':'GTiff',
    'height':H,
    'width':W,
    'count':1,
    'dtype':'float32',
    'crs':'EPSG:4326',
    'transform':transform,
    'nodata':-9999.0
}

for arr, name in [(red, 'red.tif'), (nir, 'nir.tif'), (ndvi, 'ndvi.tif')]:
    path = os.path.join(data_dir, name)
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(arr, 1)
    print('已写入:', name)

# ---- 分区统计验证 ----
print()
print('NDVI 全图范围: %.3f ~ %.3f' % (ndvi.min(), ndvi.max()))
print('密林 NDVI 均值: %.3f' % ndvi[forest].mean())
print('裸土 NDVI 均值: %.3f' % ndvi[(~forest) & (~water)].mean())
print('水体 NDVI 均值: %.3f' % ndvi[water].mean())

# ---- 验证 ndvi.tif 的元数据是否完整 ----
with rasterio.open(os.path.join(data_dir, 'ndvi.tif')) as src:
    print('transform:', src.transform)
    print('crs:', src.crs)
    print('nodata:', src.nodata)

import matplotlib.pyplot as plt

# ---- 1.4 NDVI 可视化 ----
plt.rcParams['font.sans-serif'] = ['SimHei']    # 让 matplotlib 支持中文（黑体）
plt.rcParams['axes.unicode_minus'] = False      # SimHei 没有减号字符，关闭 Unicode 减号

fig, ax = plt.subplots(figsize=(8, 6))          # 画布 8x6 英寸，fig=画布 ax=坐标区
im = ax.imshow(ndvi, cmap='RdYlGn', vmin=-1, vmax=1)
fig.colorbar(im, ax=ax, label='NDVI')
ax.set_title('模拟 NDVI 分布（密林 / 裸土 / 水体）')
ax.set_xlabel('列号 Column')
ax.set_ylabel('行号 Row')

out_path = os.path.join(script_dir, 'ndvi_preview.png')
plt.savefig(out_path, dpi=150)
plt.show()
print('图片已保存:', out_path)