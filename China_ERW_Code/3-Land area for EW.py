# 计算（1）全国各个网格面积；（2）中国各省份耕地总面积（需要考虑所在网格耕地占比）；（3）全国耕地总面积（需要考虑所在网格耕地占比）

import rasterio
import numpy as np
import pandas as pd
import math
import matplotlib.pyplot as plt

# === 1. 读取全球耕地栅格、中国省份代码栅格、全球国家代码栅格 ===
ew_tif_path = "C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif"  # 像素值表示该网格cropland的比例（0-1）
province_tif_path = "E:/ArcGIS Project/ChinaData/China_province.tif"
country_tif_path = "C:/Users/WangZeyu/Documents/ArcGIS/Projects/Country/Country_code.tif"

# 全球耕地数据
with rasterio.open(ew_tif_path) as ew_src:
    ew_data = ew_src.read(1).astype(np.float32)
    ew_data = np.where((ew_data >= 0) & (ew_data <= 1), ew_data, 0)
    transform = ew_src.transform
    bounds = ew_src.bounds
    profile = ew_src.profile

# 读取中国省份数据
with rasterio.open(province_tif_path) as province_src:
    province_data = province_src.read(1)
    province_nodata = province_src.nodata or -9999
    province_data = np.where(province_data == province_nodata, -9999, province_data)  # 将nodata值设为-9999

# 读取全球国家代码数据
with rasterio.open(country_tif_path) as country_src:
    country_data = country_src.read(1)
    country_nodata = country_src.nodata or -9999
    country_data = np.where(country_data == country_nodata, -9999, country_data)

# print(ew_data.shape, province_data.shape, country_data.shape)
# print(f"农田比例范围: {np.min(ew_data):.2f}~{np.max(ew_data):.2f}")  # 应为0~1

# === 2. 创建中国区域掩码 ===
# 使用省份数据（非-9999区域）（之后的中国掩码都用省份代码创建，不要用中国代码246）
china_mask = (province_data > 0)

# === 3. 计算网格面积（仅中国区域） ===
height, width = ew_data.shape
lon_min, lat_max = bounds.left, bounds.top
lon_max, lat_min = bounds.right, bounds.bottom

latitudes = np.linspace(lat_max - 0.25, lat_min + 0.25, height)
longitudes = np.linspace(lon_min + 0.25, lon_max - 0.25, width)
lat_grid, lon_grid = np.meshgrid(latitudes, longitudes, indexing='ij')

R = 6371  # 地球半径 km
dlon_rad = math.radians(0.5)
lat1 = np.radians(lat_grid - 0.25)
lat2 = np.radians(lat_grid + 0.25)
grid_area = R**2 * dlon_rad * (np.sin(lat2) - np.sin(lat1))  # 每格面积（km²）

# 提取中国区域面积
china_area = np.where(china_mask, grid_area, 0)

# === 4. 保存中国区域网格面积 ===
area_tif_path = "C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_grid_area_km2.tif"
profile.update(dtype=rasterio.float32, count=1)
with rasterio.open(area_tif_path, 'w', **profile) as dst:
    china_only_area = np.where(china_mask, grid_area, 0)
    dst.write(china_only_area.astype(np.float32), 1)

# === 5. 计算实际耕地面积 ===
# 中国区域实际耕地面积 = 网格面积 × 农田比例
china_cropland_area = grid_area * ew_data * china_mask  # 单位: km²

plt.imshow(china_cropland_area, vmax=1000)
plt.colorbar()
plt.title("China Cropland Map (km²)")
plt.show()

# 保存耕地面积栅格
output_tif = "C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_cropland_area_km2.tif"
profile.update(dtype=rasterio.float32, nodata=0)
with rasterio.open(output_tif, 'w', **profile) as dst:
    dst.write(china_cropland_area.astype(np.float32), 1)

# === 5. 按省份统计耕地面积 ===
province_stats = []
for code in np.unique(province_data[china_mask]):
    if code == -9999:
        continue
    mask = (province_data == code) & china_mask
    total_cropland_area = np.sum(china_cropland_area[mask])
    total_area = np.sum(china_only_area[mask])
    province_stats.append({
        'province_code': int(code),
        'total_area_km2': total_area,
        'total_cropland_area_km2': total_cropland_area,
        'mean_coverage': np.mean(ew_data[mask])  # 平均农田比例
    })

# 保存统计结果
df = pd.DataFrame(province_stats)
df.to_csv("C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_province_cropland_area.csv", index=False)

# === 6. 汇总结果：中国每个网格的面积、农田比例、农田面积（仍以全球的360*720形式呈现） ===
# 创建DataFrame
df_all = pd.DataFrame({
    'Province Code': province_data.flatten(),
    'Grid Area': china_only_area.flatten(),
    'Cropland Ratio': ew_data.flatten(),
    'Cropland Area': china_cropland_area.flatten()
})
# 保存为CSV
df_all.to_csv("C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_Cropland_Stats.csv", index=False)

total_cropland_area_km2 = np.sum(china_cropland_area)
print(f"中国适宜EW的土地总面积为：{total_cropland_area_km2:.2f} 平方公里")
