# -*- coding: utf-8 -*-
"""
课题三：卫星影像与 NDVI
1.1 造一个假栅格，写入 GeoTIFF
1.2 读回来，查看元数据
"""
import os
import numpy as np
import rasterio
from rasterio.transform import from_origin#从原点出发

script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data')
os.makedirs(data_dir, exist_ok=True)  # 没有 data 文件夹就建一个

# ---- 1. 造数据：200x200 的二维数组，模拟红光波段反射率 ----
np.random.seed(42)  # 固定随机种子，每次运行结果一样
red=np.random.uniform(0.02,0.10,size=(200,200)).astype('float32')

print('数组形状',red.shape)
print('数组类型',red.dtype)
print('最小值',red.min(),'最大值',red.max())
print('左上角第一个单元',red[0,0])

transform =from_origin(
    west=117.9,   #左上角像元lon
    north=26.6,   #lat
    xsize=0.0001, #像元宽（度
    ysize=0.0001  #像元高 （度
)

tif_path=os.path.join(data_dir,'red.tif')

#创建单波段，红光
with rasterio.open(
    tif_path,'w',
    driver='GTiff',#栅格格式
    height=200,#对应数组行数
    width=200,#数组列数
    count=1,#波段数，种类
    dtype='float32',#像元类型，与数组一致
    crs='EPSG:4326',#坐标系
    transform=transform,
)as dst:
    dst.write(red,1)
print('文件写入',tif_path)

with rasterio.open(tif_path) as src:
    print('波段数 count',src.count)
    print('尺寸 height x width',src.width,'x',src.height)
    print('坐标系 crs',src.crs)
    print('定位规则 tranform')
    print(src.transform)
    arr=src.read(1)

print()
print('读回数组形状',arr.shape)
print('读回数组类型',arr.dtype)
print('最小值',arr.min(),'最大值',arr.max())
print('与写入前的red是否完全相同',np.array_equal(arr,red))
