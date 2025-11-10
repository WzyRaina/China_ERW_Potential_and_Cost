# 中国岩石地图获取方法：
# （1）《全国矿产地数据库2021版》的csv筛选出“玄武岩”和“橄榄岩”，并且去掉闭坑和关闭的数据
# （2）用arcgis pro将csv转化为shp文件
# （3）用arcgis将shp文件导出为栅格数据，分辨率0.5*0.5，与全球栅格保持一致（360*720）
# （4）用本代码将basalt和olivinite岩石分布结合到一张栅格地图上，对于有重合的地区，计为olivinite，因为olivinite成本更低
# （5）去掉保护区得到中国可用岩石分布（仍旧用2和4代表basalt和olivinite）


import os
import numpy as np
from osgeo import gdal, osr
import matplotlib.pyplot as plt

os.chdir('C:/PyCharm/PycharmProjects/Grid-based MONET')

# rock distribution
EW_basalt_distribution_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_Basalt_Map.tif').ReadAsArray()
EW_dunite_distribution_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_Olivinite_Map.tif').ReadAsArray()
# World Database on Protected Areas, 1 or nodata
WDPA_array = gdal.Open('C:/Users/WangZeyu/Documents/ArcGIS/Projects/GetData/WDPA_low_Clip.tif').ReadAsArray()

# set raster's row and col
raster_row = 360
raster_col = 720

# output
rock_available_distribution_array = np.full((raster_row, raster_col), np.nan)

for row in range(raster_row):
    for col in range(raster_col):
        if WDPA_array[row, col] == 1:
            continue
        else:
            if EW_basalt_distribution_array[row, col] != 0 and EW_dunite_distribution_array[row, col] != 0:
                rock_available_distribution_array[row, col] = 4  # 4代表olivinite
            if EW_basalt_distribution_array[row, col] != 0 and EW_dunite_distribution_array[row, col] == 0:
                rock_available_distribution_array[row, col] = 2  # 2代表basalt
            if EW_basalt_distribution_array[row, col] == 0 and EW_dunite_distribution_array[row, col] != 0:
                rock_available_distribution_array[row, col] = 4  # 4代表olivinite
            if EW_basalt_distribution_array[row, col] == 0 and EW_dunite_distribution_array[row, col] == 0:
                continue

# write raster data
driver = gdal.GetDriverByName("GTiff")
# note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
# EW_efficiency_raster_rock = driver.Create(f'./Output/EW/Removal Efficiency/Global Output/EW_removal_efficiency_raster_{rock_type.iloc[r, 0]}_{grain_size.iloc[s, 0]} μm.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
rock_available_distribution = driver.Create('./Global Data/EW/Input/China/China Rock Available Map.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
rock_available_distribution.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
rock_available_distribution.SetProjection(srs.ExportToWkt())
rock_available_distribution.GetRasterBand(1).WriteArray(rock_available_distribution_array)
rock_available_distribution.FlushCache()
rock_available_distribution = None  # prevent files from being locked