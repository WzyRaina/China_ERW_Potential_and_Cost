# 本代码用于将从Tu Y, Wu S, Chen B, et al. A 30 m annual cropland dataset of China from 1986 to 2021[J].
# Earth System Science Data, 2024, 16(5): 2297-2316.文献获得的2021年中国30m分辨率栅格地图重采样为0.5°*0.5°，360行720列
# 并且与模板（此处选择省份代码栅格China_province.tif）对齐
# 总的来说就是，因为arcgis处理30m分辨率的地图出了问题，因此用代码处理
# 但因为30m分辨率的地图太大了，内存不够，因此采用的方法是：先用arcgis将30m用最近邻重采样为0.01°*0.01°，再用本代码重采样为0.5°*0.5°并且输出每个网格的耕地比例

import rioxarray
import numpy as np
from rasterio.enums import Resampling

# === 1. 读取原始 0.01° 栅格，像素值为 0/1，NoData 为 255 ===
input_path = "E:/ArcGIS Project/ChinaData/CACD_2021_0.01.tif"
cropland = rioxarray.open_rasterio(input_path, masked=True).squeeze()

# 设置像素为 float 类型，排除 NoData=255 的像素
cropland = cropland.astype("float32")
cropland = cropland.where((cropland >= 0) & (cropland <= 1), np.nan)

# === 2. 打开 0.5° 模板文件（如省份代码栅格，确保是0.5°精度） ===
template_path = "E:/ArcGIS Project/ChinaData/China_province.tif"
template = rioxarray.open_rasterio(template_path, masked=True).squeeze()

# === 3. 重采样：0.01° → 0.5°，取平均值作为耕地比例 ===
cropland_fraction = cropland.rio.reproject_match(template, resampling=Resampling.average)

# === 4. 保存结果 ===
cropland_fraction.rio.to_raster("C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif")
