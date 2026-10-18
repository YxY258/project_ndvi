# 卫星影像与 NDVI 植被指数计算

用 rasterio 处理栅格数据，计算 NDVI（归一化植被指数），识别森林、裸土、水体三类地物。

## 项目说明

NDVI（归一化植被指数）是遥感监测植被最经典的指标：

```
NDVI = (NIR − Red) / (NIR + Red)      取值 −1 ~ +1
```

- 健康植被大量吸收红光（光合作用）、强烈反射近红外 → NDVI 高（0.6~0.9）
- 裸土两个波段接近 → NDVI ≈ 0
- 水体强吸收近红外 → NDVI 为负

当前阶段使用**模拟数据**（numpy 生成的假卫星影像：中心密林、周围裸土、左上角水体）验证完整计算链路；下一阶段将替换为真实 Sentinel-2 卫星影像（10 m 分辨率）。

## 项目结构

```
project_ndvi/
├── step1_raster_basics.py   # 1.1/1.2 造数组 → 写入 GeoTIFF → 读回验证
├── step2_ndvi.py            # 1.3/1.4 造场景 → 算 NDVI → 存 3 个 tif → 可视化
├── data/
│   ├── red.tif              # 模拟红光波段（EPSG:4326，10m 像元）
│   ├── nir.tif              # 模拟近红外波段
│   └── ndvi.tif             # NDVI 结果（含 nodata=-9999 声明）
└── ndvi_preview.png         # NDVI 可视化预览图
```

## 处理流程

1. **栅格读写**：numpy 数组 + affine transform（左上角锚点 + 像元步长）+ CRS → GeoTIFF；写后读回用 `np.array_equal` 验证无损
2. **造空间结构**：`np.meshgrid` 摊平坐标网格 → 向量化算各像元到圆心距离 → 布尔掩膜划分密林 / 裸土 / 水体
3. **分区赋值**：按三类地物的真实光谱特征赋反射率（森林红光 2%~6%、近红外 40%~55% 等）
4. **NDVI 计算**：向量化除法 + `np.errstate` 处理除零 + nodata 标记（−9999）
5. **验证**：分区统计均值与赋值区间中点互相印证（森林 0.844 / 裸土 0.076 / 水体 −0.317）
6. **可视化**：matplotlib `imshow`，cmap=RdYlGn，色标固定 −1~1

## 运行方式

```bash
conda activate forestry
python step1_raster_basics.py   # 栅格读写基础
python step2_ndvi.py            # NDVI 计算与可视化
```

## 依赖环境

- Python 3.x
- numpy、rasterio（GDAL）、matplotlib

建议用 conda-forge 源安装 rasterio，避免 pip 安装失败。

## 作者

YxY258
