# 计算中国ERW适宜性网格（农田）距离最近的岩石来源的距离，从而替代原来岩石来源到农田固定50km的假设
# 假设采矿和粉碎厂在岩石来源地，因此只需要从采矿场运输到农田
# 假设不涉及国际贸易，用本国的岩石来源
# 简化运输路线为网格中心点之间的直线距离，再根据经纬度转换，用tortuosity因子修正为真实道路距离

import os
import numpy as np
from osgeo import gdal, osr
import matplotlib.pyplot as plt
from geopy.distance import geodesic  # 用于计算地理距离
from tqdm import tqdm
import sys

os.chdir('C:/PyCharm/PycharmProjects/Grid-based MONET')

# read data
# land available for EW: cropland
EW_land_array = gdal.Open('C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif').ReadAsArray()
# rock distribution
EW_rock_distribution_array = gdal.Open('./Global Data/EW/Input/China/China Rock Available Map.tif').ReadAsArray()
# 中国省级边界栅格，每个网格的值是省份代码
province_code_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_province.tif').ReadAsArray()
# tortuosity factor
tortuosity_factor_array = gdal.Open('E:/ArcGIS Project/ChinaData/Road_Tortuosity.tif').ReadAsArray()

# np.set_printoptions(threshold=sys.maxsize)

# set raster's row and col
raster_row = 360
raster_col = 720

# output
EW_China_transport_distance_array_basalt = np.full((raster_row, raster_col), np.nan)  # 默认NaN，表示无可用岩石; 使用basalt作为岩石来源
EW_China_transport_distance_array_dunite = np.full((raster_row, raster_col), np.nan)  # 使用dunite作为岩石来源
EW_China_transport_distance_array_basalt_csv = np.full((360*720, 1), np.nan)
EW_China_transport_distance_array_dunite_csv = np.full((360*720, 1), np.nan)

# 经纬度转换函数
def index_to_latlon(i, j):
    lat = 90 - i * 0.5
    lon = j * 0.5 - 180
    return lat, lon

def latlon_to_index(lat, lon):
    i = int(round((90 - lat) / 0.5))
    j = int(round((lon + 180) / 0.5))
    return i, j

# 不允许国际贸易
print("不允许国际贸易")
# 处理岩石类型（Dunite 和 Basalt）
for rock_type, output_array in zip([4, 2], [EW_China_transport_distance_array_dunite, EW_China_transport_distance_array_basalt]):
    # 选取中国的岩石源头
    rock_indices = np.argwhere(
        (EW_rock_distribution_array == rock_type) & (province_code_array > 0)  # 在中国境内
    )
    if len(rock_indices) == 0:
        print(f"No rock sources found.")
        continue

    # 选取本国的农田
    farmland_indices = np.argwhere(
        (EW_land_array > 0) & (province_code_array > 0)
    )
    if len(farmland_indices) == 0:
        print(f"No farmland found.")
        continue

    # 生成岩石坐标
    rock_coords = np.array([index_to_latlon(i, j) for i, j in rock_indices])

    # 生成农田坐标
    farmland_coords = np.array([index_to_latlon(i, j) for i, j in farmland_indices])

    for idx, (i, j) in enumerate(tqdm(farmland_indices, desc=f"China rock type {rock_type}")):
        farmland_point = index_to_latlon(i, j)

        # 找到 geodesic 最近的岩石点
        min_dist = float('inf')
        for rock_point in rock_coords:
            dist = geodesic(farmland_point, rock_point).km
            if dist < min_dist:
                min_dist = dist

        tortuosity = tortuosity_factor_array[i, j]
        if not np.isnan(tortuosity):
            output_array[i, j] = min_dist * tortuosity
        else:
            output_array[i, j] = np.nan  # 没有 tortuosity 值则保留为 NaN

# 写入 GeoTIFF 文件的函数
def save_raster(output_path, array):
    driver = gdal.GetDriverByName("GTiff")
    raster = driver.Create(output_path, xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)
    raster.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 左上角坐标(-180,90)，分辨率 0.5°
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)  # WGS 1984 (EPSG:4326)
    raster.SetProjection(srs.ExportToWkt())
    raster.GetRasterBand(1).WriteArray(array)
    raster.FlushCache()
    del raster  # 确保释放文件

# 保存 Dunite 和 Basalt 的运输距离数据
save_raster('./Global Data/EW/Output/EW_China_transport_distance_dunite.tif', EW_China_transport_distance_array_dunite)
save_raster('./Global Data/EW/Output/EW_China_transport_distance_basalt.tif', EW_China_transport_distance_array_basalt)

# 可视化
plt.figure(figsize=(10, 5))
plt.imshow(EW_China_transport_distance_array_dunite, cmap='viridis', interpolation='nearest')
plt.colorbar(label='Transport Distance (km)')
plt.title('Dunite Transport Distance')
plt.show()

plt.figure(figsize=(10, 5))
plt.imshow(EW_China_transport_distance_array_basalt, cmap='plasma', interpolation='nearest')
plt.colorbar(label='Transport Distance (km)')
plt.title('Basalt Transport Distance')
plt.show()

# 展平为一维用于 CSV 保存
EW_China_transport_distance_array_basalt_csv = EW_China_transport_distance_array_basalt.reshape(-1, 1)
EW_China_transport_distance_array_dunite_csv = EW_China_transport_distance_array_dunite.reshape(-1, 1)

# 保存为 CSV 文件
np.savetxt('./Global Data/EW/Output/EW_China_transport_distance_basalt.csv',
           EW_China_transport_distance_array_basalt_csv,
           delimiter=",", header="Basalt_Transport_Distance_km", comments="")

np.savetxt('./Global Data/EW/Output/EW_China_transport_distance_dunite.csv',
           EW_China_transport_distance_array_dunite_csv,
           delimiter=",", header="Dunite_Transport_Distance_km", comments="")
