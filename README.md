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

项目分两个阶段：

1. **模拟数据打通链路**（step1 / step2）：numpy 生成假卫星影像（中心密林、周围裸土、左上角水体），验证「造栅格 → 读写 GeoTIFF → 算 NDVI → 可视化」全流程；
2. **真实卫星影像**（step3 / step4）：从微软 Planetary Computer 检索 Sentinel-2 L2A 影像，按样地范围窗口裁剪下载 B04（红光）/ B08（近红外），计算真实 NDVI。

## 项目结构

```
project_ndvi/
├── step1_raster_basics.py   # 1.1/1.2 造数组 → 写入 GeoTIFF → 读回验证
├── step2_ndvi.py            # 1.3/1.4 造场景 → 算 NDVI → 存 3 个 tif → 可视化
├── step3_search_image.py    # 2.1/2.2 STAC 检索 → shapely 选景 → COG 窗口裁剪下载 B04/B08
├── step4_real_ndvi.py       # 2.3 真实数据：DN→反射率 → NDVI → 存盘 → 出图
├── data/
│   ├── red.tif              # 模拟红光波段（EPSG:4326，10m 像元）
│   ├── nir.tif              # 模拟近红外波段
│   ├── ndvi.tif             # 模拟数据 NDVI 结果（含 nodata=-9999 声明）
│   ├── B04.tif              # 真实红光波段（EPSG:32650 / UTM 50N，10m，2231×2010）※
│   ├── B08.tif              # 真实近红外波段 ※
│   ├── ndvi_real.tif        # 真实数据 NDVI 结果 ※
│   └── ndvi_real.png        # 真实 NDVI 可视化
└── ndvi_preview.png         # 模拟数据 NDVI 可视化预览图
```

※ 标注的三个 tif 单个体积 5~14 MB，可由 step3 / step4 重新生成，已写入 `.gitignore` 不进版本库。

## 处理流程

### 阶段 1：模拟数据（验证链路）

1. **栅格读写**：numpy 数组 + affine transform（左上角锚点 + 像元步长）+ CRS → GeoTIFF；写后读回用 `np.array_equal` 验证无损
2. **造空间结构**：`np.meshgrid` 摊平坐标网格 → 向量化算各像元到圆心距离 → 布尔掩膜划分密林 / 裸土 / 水体
3. **分区赋值**：按三类地物的真实光谱特征赋反射率（森林红光 2%~6%、近红外 40%~55% 等）
4. **NDVI 计算**：向量化除法 + `np.errstate` 处理除零 + nodata 标记（−9999）
5. **验证**：分区统计均值与赋值区间互相印证（森林 0.844 / 裸土 0.076 / 水体 −0.317）
6. **可视化**：matplotlib `imshow`，cmap=RdYlGn，色标固定 −1~1

### 阶段 2：真实 Sentinel-2 影像

1. **STAC 检索**：`pystac_client` + Planetary Computer，按集合（sentinel-2-l2a）、bbox、日期、云量条件检索
2. **选景**：shapely `Point.contains()` 判断样地中心落在哪一景覆盖范围内
3. **窗口裁剪**：`transform_bounds`（经纬度→UTM 米）+ `from_bounds`（地理范围→行列窗口）+ `read(1, window=...)`，只下载目标窗口像素（云端 COG 随机访问），新窗口图底由 `window_transform` 计算
4. **DN → 反射率**：`反射率 = (DN − 1000) / 10000`（Sentinel-2 处理基线 PB 04.00+，2022-01-25 起启用偏移 1000），先 `astype(float32)` 避免 uint16 下溢
5. **NDVI 计算**：无效像元置 NaN，存盘时转 −9999 哨兵值；`transform`/`crs` 从裁剪窗口继承，结果带地理定位
6. **验证**：NDVI 中位数 0.852、10% 分位 0.703，林地（NDVI>0.6）占比 92.4%

## 关键结果（2025-08-08，Sentinel-2 C，Tile T50RNQ）

| 指标 | 数值 |
|---|---|
| 研究窗口 | 117.9°~118.1°E，26.4°~26.6°N（三明，0.2°×0.2°） |
| 影像网格 | 2231 行 × 2010 列，10 m 分辨率，EPSG:32650 |
| red 反射率 | −0.031 ~ 1.724 |
| NDVI | −0.538 ~ 1.325，中位数 0.852 |
| NDVI>0.6 占比 | 92.4%（含森林与夏季稻田） |

## 运行方式

```bash
conda activate forestry
python step1_raster_basics.py   # 栅格读写基础
python step2_ndvi.py            # 模拟数据 NDVI（阶段 1）
python step3_search_image.py    # STAC 检索 + 窗口裁剪下载（需联网，阶段 2 第 1 步）
python step4_real_ndvi.py       # 真实数据 NDVI（阶段 2 第 2 步，依赖 step3 产物）
```

## 依赖环境

- Python 3.x
- numpy、rasterio（GDAL）、matplotlib
- 阶段 2 额外需要：pystac-client、planetary-computer、shapely

建议用 conda-forge 源安装 rasterio，避免 pip 安装失败。

## 作者

YxY258
