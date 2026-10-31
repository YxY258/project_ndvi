# -*- coding: utf-8 -*-
"""
课题三 阶段2：真实 Sentinel-2 影像
2.1 用 STAC API 搜索福建区域的影像（只查目录，不下载像素）
2.2 选景：确认样地中心落在哪一景的覆盖范围内

【数据来源：Sentinel-2 卫星】
  - 欧洲航天局（ESA）"哥白尼计划"（Copernicus Programme）的对地观测卫星
  - 星座成员：Sentinel-2A（2015 发射）、2B（2017）、2C（2024，接替退役中的 2A）
    ——本脚本搜到的 ID 以 S2C 开头，即最新那颗拍的
  - 载荷：多光谱成像仪 MSI，13 个波段，分辨率 10 / 20 / 60 米
    本项目只用两个 10 米波段：B04 红光 665nm、B08 近红外 842nm
  - 重访周期：双星协作下全球每 5 天扫一遍（所以能搜到多景同瓦片影像）
  - 幅宽 290 km，标准分幅为 100×100 km 的瓦片（ID 里的 T50RPQ/T50RNQ）
  - 数据免费开放，L2A 级已做大气校正，像素值即地表反射率（0~10000 整数）

STAC = Spatio-Temporal Asset Catalog，遥感数据的"图书检索系统"：
  输入 空间范围 + 时间范围 + 过滤条件 → 返回符合条件的影像清单（Item）
  每个 Item = 一景影像（卫星一次过境的完整拍摄），挂着各波段文件的链接和元数据
"""

import pystac_client
import planetary_computer

# ============================================================
# 1. 连接 Planetary Computer 的 STAC 目录
# 提示：pystac_client.Client.open(目录网址, modifier=planetary_computer.sign_inplace)
#   - 目录网址：https://planetarycomputer.microsoft.com/api/stac/v1
#   - modifier 传函数本身，不加括号（回调模式，同 folium 的 style_function）
#   - 漏掉 modifier：能搜到影像，但读数据时 401
# ============================================================
catalog=pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=planetary_computer.sign_inplace,
)

# ============================================================
# 2. 搜索：课题二样地区域、2025 年盛夏、云量 < 10%
# 提示：catalog.search(四个参数)
#   - collections=["sentinel-2-l2a"]   # L2A = 已大气校正
#   - bbox=[西, 南, 东, 北]            # 经度在前！[117.9, 26.4, 118.1, 26.6]
#   - datetime="2025-07-01/2025-08-31" # 斜杠分隔起止
#   - query={"eo:cloud_cover": {"lt": 10}}  # lt = less than
# ============================================================
search=catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[117.9,26.4,118.1,26.6],
    datetime="2025-07-01/2025-08-31",
    query={"eo:cloud_cover":{"lt":10}}
)

# ============================================================
# 3. 取回结果并打印
# 提示：items = list(search.items())   # 迭代器 → 列表
#   循环打印前 5 景：
#   - item.id                          # 影像唯一编号
#   - item.datetime                    # UTC 拍摄时间
#   - item.properties["eo:cloud_cover"]# 云量 %
#   - list(item.assets.keys())         # 波段名列表（确认有 B04、B08、SCL）
# ============================================================
items=list(search.items())
print(f"找到{len(items)}景影像")
print()

for item in items[:5]:
    print("ID:",item.id)
    print("拍摄时间:", item.datetime)
    print("云量: %.1f%%" % item.properties["eo:cloud_cover"])
    print("波段列表:", list(item.assets.keys()))
    print("-" * 60)

# ============================================================
# 2.2 选景：检查样地中心落在哪一景的覆盖范围内
# 背景：搜索框骑在两个瓦片（T50RNQ / T50RPQ）的边界上，
#       单景盖不满搜索框，裁剪前必须先确认用哪一景
# ============================================================
from shapely.geometry import shape, Point

# 课题二 50 个样地的中心点（step3_map.py 里 gdf['lat'/'lon'].mean() 算出的值）
# shapely 的 Point 是（经度, 纬度），和 folium 的 [纬度, 经度] 相反
plot_center = Point(117.9873, 26.4848)

for item in items:
    # item.geometry：这景影像的覆盖范围（GeoJSON 多边形）
    # shape()：GeoJSON 字典 → shapely 几何对象，之后才能调用空间关系方法
    polygon = shape(item.geometry)

    # contains：点是否在多边形内部（空间谓词，和课题二的 buffer/distance 同族）
    if polygon.contains(plot_center):
        print("样地中心在这景里:", item.id)
        print("  云量: %.1f%%" % item.properties["eo:cloud_cover"])

# 注：同一瓦片每 5 天被重拍一次，所以预期输出是两景（不同日期的 T50RNQ），
# 下一小节从其中选云量更低的那景做窗口裁剪。

# ============================================================
# 2.2.2 窗口裁剪：只下载样地窗口的 B04/B08，存成本地 tif
# COG 的本事：远程打开后只下载窗口内的像素，而不是整景 200MB+
# ============================================================
import os
import rasterio
from rasterio.windows import from_bounds     # 地理范围 → 行列窗口
from rasterio.warp import transform_bounds   # 坐标系转换（度 → 米）
#
# 步骤 1：选景
#   - 列表推导式：[it for it in items if "20250808" in it.id and "T50RNQ" in it.id]
#     筛出 8 月 8 日 T50RNQ 那景（云量 5.6%，两景里更低），末尾 [0] 取第一个
#
selected=[it for it in items
          if "20250808" in it.id and "T50RNQ" in it.id][0]
print("选定影像",selected.id)
bbox=(117.9,26.4,118.1,26.6)
script_dir = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(script_dir, 'data')

# 步骤 2：for 循环处理 "B04"、"B08" 两个波段
#   - selected.assets[波段名].href = 盖过章的云端文件链接
#   - with rasterio.open(href) as src:  # 远程打开，此刻只读文件头，像素不下载
#   - 打印 src.crs（应为 EPSG:32650，UTM 米制）和 src.res（10 米分辨率）
#
for band in["B04","B08"]:
    href=selected.assets[band].href
    with rasterio.open(href) as src:
        print(band,"影像自身坐标系",src.crs,"| 分辨率:", src.res)
# 步骤 3：坐标转换（关键！度 → 米）
#   - bbox 是经纬度"度"，影像是 UTM"米"，两套数字不能直接比较
#   - transform_bounds("EPSG:4326", src.crs, *bbox) → 返回 left, bottom, right, top
#   - *bbox 是元组拆包（同 **profile 思想），把四个值拆成四个参数
#
        left,bottom,right,top=transform_bounds(
            "EPSG:4326",src.crs,*bbox)
# 步骤 4：开窗口、读数据
#   - window = from_bounds(left, bottom, right, top, transform=src.transform)
#     把地理范围换算成影像上的行列窗口（transform 的反向使用）
#   - arr = src.read(1, window=window)  # 本块灵魂：只下载窗口内的像素
#
        window = from_bounds(left,bottom,right,top,transform=src.transform)
        arr=src.read(1,window=window)
# 步骤 5：存本地 tif
#   - win_transform = src.window_transform(window)
#     窗口的左上角不在原影像 (0,0)，要算出这块自己的定位规则
#   - profile = src.profile.copy()  # 继承 dtype/crs/nodata（dtype 是 uint16）
#   - profile.update(width=..., height=..., transform=win_transform)
#   - 用 with rasterio.open(路径, 'w', **profile) 写入 data 目录，
#     文件名用波段名（B04.tif / B08.tif），dst.write(arr, 1)
#
        win_transform = src.window_transform(window)
        profile = src.profile.copy()         # 继承原影像的 dtype/crs/nodata 等
        profile.update(width=arr.shape[1],
                       height=arr.shape[0],
                       transform=win_transform)

        out_path = os.path.join(data_dir, band + '.tif')
        with rasterio.open(out_path, 'w', **profile) as dst:
            dst.write(arr, 1)
        print("已保存:", out_path, "| 形状:", arr.shape,
              "| 类型:", arr.dtype)
# 预期：两文件形状约 (2222, 2000)，uint16，0~10000 的 DN 值
#       （除以 10000 才是反射率，2.3 算 NDVI 前要做）
# ============================================================

