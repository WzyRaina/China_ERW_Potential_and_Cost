# 计算每年铺洒 20 t rock/ha，直到达到 150 t rock/ha 的上限停止铺洒，然后计算年平均风化速率
# 潜力：tCO2 rem 或 tCO2 cap （每个网格的tCO2 rem/ha * ha）

import os
import pandas as pd
import numpy as np
from osgeo import gdal, osr
import sys
import matplotlib.pyplot as plt

os.chdir('C:/PyCharm/PycharmProjects/Grid-based MONET')

# 定义一个近似函数
def custom_round(values, step=0.005):  # 想保留x位小数这里就是step = 5 * 10^(-x)
    """
    将输入的值按照指定步长进行归类。
    例如：step=0.05，0.48~0.52归为0.50，0.53~0.57归为0.55。

    :param values: 输入的值或数组（可以是列表或numpy数组）
    :param step: 步长（默认0.05）
    :return: 归类后的值（numpy数组）
    """
    values = np.array(values)  # 确保输入为numpy数组
    return np.round(values / step) * step

# read electricity emission factors (from ArcGISPro)
EEF_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Emission_Factor.tif').ReadAsArray()  # 0.5°*0.5°; unit: gCO2eq/kWh; /3600 (kgCO2e/MJ)
# np.set_printoptions(threshold=sys.maxsize)

# land available for EW
EW_land_array = gdal.Open('C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif').ReadAsArray()

# 中国省级边界栅格，每个网格的值是省份代码
province_code_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_province.tif').ReadAsArray()

# PH data
PH = gdal.Open('C:/Users/WangZeyu/Documents/ArcGIS/Projects/GetData/T_PH_H20.tif')  # 360*720
PH_array = PH.ReadAsArray()  # turn tif to array
# Soil temperature
soil_temperature = gdal.Open('C:/Users/WangZeyu/Documents/ArcGIS/Projects/Biomass Yield/Soil_Temperature.tif')  # 360*720
soil_temperature_array = soil_temperature.ReadAsArray()  # turn tif to array

# raster's row and col depend on EEF_array
raster_row = 360
raster_col = 720

# read specific EW data
EW_data = pd.read_csv('Raw Data/EW/EW.csv', encoding='gbk')
# read common data
Energy_data = pd.read_csv('Raw Data/Common Data/Energy.csv')  # parameters about energy
Carbon_data = pd.read_csv('Raw Data/Common Data/China Carbon.csv', encoding='gbk')  # parameters about carbon
# read input data by myself
grain_size = pd.read_csv('Input Data/EW/Grain Size.csv', encoding='gbk')  # grain size settings
# read rock type
rock_type = pd.read_csv('Input Data/EW/Rock Type.csv', encoding='gbk')  # rock type settings
# read other parameters
other_data = pd.read_csv('Input Data/EW/Other Data.csv', encoding='gbk')  # other parameters
transport_mode = pd.read_csv('Raw Data/Common Data/China Transport Mode.csv', encoding='gbk')
transport_cost = pd.read_csv('Raw Data/Common Data/China Transport Mode Cost.csv', encoding='gbk')

# read cost data
# diesel cost
diesel_cost_array = gdal.Open('E:/ArcGIS Project/ChinaData/Diesel_Cost_Raster.tif').ReadAsArray()  # $/l
print(diesel_cost_array.shape)
# electricity price
electricity_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Price_Raster.tif').ReadAsArray()  # $/MWh; /3600 ($/MJ)
print(electricity_price_array.shape)
rock_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Rock_Price.tif').ReadAsArray()  # $/t rock
print(rock_price_array.shape)

# grain sizes and rock type number
num_of_grain_size = len(grain_size)  # grain size: 2, 10, 20, 50μm （ From: Strefler, J., Amann, T., Bauer, N., Kriegler, E., & Hartmann, J. (2018). Potential and costs of carbon dioxide removal by enhanced weathering of rocks. Environmental Research Letters, 13.)
num_of_type = len(rock_type)  # rock type: basalt, dunite

# construct carbon emissions structure of EW in MONET, as well as output we want to get, tCO2e/t rock
EW_emission_structure = pd.DataFrame(columns=['Direct CO2 emissions from the combustion of fuels (diesel) for rocks mining/extraction, transport, and application on soil, and natural gas and/or wood for drying biomass (tCO2e/t rock)',
                                              'Indirect CO2 emissions due to the production of these fuels (diesel), and the generation of electricity for rocks crushing and grinding (tCO2e/t rock)',
                                              'Indirect CO2 emissions due to the manufacture of materials, i.e., ammonium nitrate-based explosives (tCO2e/t rock)'],
                                     index=['Mining',
                                            'Crushing & Grinding',
                                            'Transport',
                                            'Application on Soil'])
# construct total carbon emission structure of EW, tCO2e/t rock
EW_total_emission_structure = pd.DataFrame(columns=['Region', 'Mining (tCO2e/t rock)', 'Crushing & Grinding (tCO2e/t rock)',
                                                    'Transport (tCO2e/t rock)', 'Application on Soil (tCO2e/t rock)',
                                                    'Total emissions (tCO2e/t rock)'],
                                           index=range(1))  # 500 is a large number for five regions' sub-regions

# construct potential raster data (GtCO2 rem/yr)
EW_potential_raster_array_rock_rem = np.full((raster_row, raster_col), np.nan)
# 记录每个网格的累积潜力
EW_rem_potential_csv = np.full((360*720, 8), np.nan)

# settings
start_year = 2025
end_year = 2100

work_index = [17.93, 12.38]  # basalt=17.93, dunite=12.38
F_80 = 1000  # μm

# 定义常量
Grid_Cropland_Area_km2 = gdal.Open('C:/PyCharm/PycharmProjects/Grid-based MONET/Global Data/EW/Input/China/China_cropland_area_km2.tif').ReadAsArray()  # 每个网格的耕地面积（km2）（0.5° 分辨率的网格面积不一定是为 55km x 55km，要提前根据经纬度换算，并且乘网格的耕地比例）
T_TO_GT = 1e-9  # 吨到千兆吨的转换系数

# compute carbon emissions
# compute carbon emissions (tCO2e/t rock)
# row 1
EW_emission_structure.iloc[0, 0] = EW_data.iloc[3, 2] / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] / 1000  # kWh/t rock / 1000 = MWh/t rock, MWh/t rock * 3600 = MJ/t rock
EW_emission_structure.iloc[0, 1] = EW_data.iloc[3, 2] / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] / 1000
EW_emission_structure.iloc[0, 2] = EW_data.iloc[9, 2] * EW_data.iloc[10, 2] * EW_data.iloc[24, 2] * (Carbon_data.iloc[26, 2] + (Carbon_data.iloc[46, 2] + Carbon_data.iloc[47, 2] * Carbon_data.iloc[48, 2] + Carbon_data.iloc[49, 2] * Carbon_data.iloc[50, 2]) * EW_data.iloc[23, 2] * other_data.iloc[0, 2]) / 1000
# row 2
EW_emission_structure.iloc[1, 0] = 0
EW_emission_structure.iloc[1, 2] = 0
# row 3
EW_emission_structure.iloc[2, 2] = 0
# row 4
EW_emission_structure.iloc[3, 0] = EW_data.iloc[7, 2] / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] / 1000
EW_emission_structure.iloc[3, 1] = EW_data.iloc[7, 2] / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] / 1000
EW_emission_structure.iloc[3, 2] = 0

EW_total_emission_structure.iloc[0, 1] = EW_emission_structure.iloc[0, 0] + EW_emission_structure.iloc[0, 1] + EW_emission_structure.iloc[0, 2]
EW_total_emission_structure.iloc[0, 4] = EW_emission_structure.iloc[3, 0] + EW_emission_structure.iloc[3, 1] + EW_emission_structure.iloc[3, 2]

for r in range(num_of_type):  # num_of_type
    print(rock_type.iloc[r, 0])
    for s in range(num_of_grain_size):  # num_of_grain_size
        print("颗粒大小:", grain_size.iloc[s, 0])
        # transport distance
        EW_global_transport_distance_array_rock = gdal.Open(f'./Global Data/EW/Output/EW_China_transport_distance_{rock_type.iloc[r, 0]}.tif').ReadAsArray()  # no trade
        # EW_global_transport_distance_array_rock = gdal.Open(f'./Global Data/EW/Output/EW_global_transport_distance_{rock_type.iloc[r, 0]} (with trade).tif').ReadAsArray()  # with trade
        for row in range(raster_row):  # row, 345, raster_row
            for col in range(raster_col):  # col, 720, raster_col
                if province_code_array[row, col] > 0:  # 中国省份代码都大于0
                    if EW_land_array[row, col] > 0:  # available for EW
                        if not np.isnan(EW_global_transport_distance_array_rock[row, col]):  # no rock source in this country
                            if EEF_array[row, col] >= 0:
                                if PH_array[row, col] > 0:
                                    if soil_temperature_array[row, col] > -256:
                                        PH_temp = np.around(PH_array[row, col], 0)
                                        T_temp = np.around(custom_round(soil_temperature_array[row, col], step=10), 0)
                                        # print("PH:", PH_temp)
                                        # print("T:", T_temp)
                                        if os.path.isfile(f'C:/PyCharm/PycharmProjects/NETs/EW/Output/{rock_type.iloc[r, 0]}/modified/Annual Weathering Rate_{grain_size.iloc[s, 0]} μm_pH{PH_temp}_{T_temp}C.csv'):
                                            CO2_seq_potential_annual = pd.read_csv(f'C:/PyCharm/PycharmProjects/NETs/EW/Output/{rock_type.iloc[r, 0]}/modified/Annual Weathering Rate_{grain_size.iloc[s, 0]} μm_pH{PH_temp}_{T_temp}C.csv')

                                            # compute carbon emissions (tCO2e/t rock)
                                            EW_emission_structure.iloc[1, 1] = (EW_data.iloc[4, 2] + 10 * work_index[r] * (1 / np.sqrt(grain_size.iloc[s, 0]) - 1 / np.sqrt(F_80))) * EEF_array[row, col] / 1000000

                                            EW_emission_structure.iloc[2, 0] = ((Energy_data.iloc[18, 2] * transport_mode.iloc[0, 2] + Energy_data.iloc[19, 2] * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] + Energy_data.iloc[20, 2] * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[7, 2]) * EW_global_transport_distance_array_rock[row, col] / 1000
                                            EW_emission_structure.iloc[2, 1] = ((Energy_data.iloc[18, 2] * transport_mode.iloc[0, 2] + Energy_data.iloc[19, 2] * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] + Energy_data.iloc[20, 2] * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[19, 2]) * EW_global_transport_distance_array_rock[row, col] / 1000

                                            # compute total emissions
                                            EW_total_emission_structure.iloc[0, 2] = EW_emission_structure.iloc[1, 0] + EW_emission_structure.iloc[1, 1] + EW_emission_structure.iloc[1, 2]
                                            EW_total_emission_structure.iloc[0, 3] = EW_emission_structure.iloc[2, 0] + EW_emission_structure.iloc[2, 1] + EW_emission_structure.iloc[2, 2]
                                            EW_total_emission_structure.iloc[0, 5] = (EW_total_emission_structure.iloc[0, 1] + EW_total_emission_structure.iloc[0, 2] +
                                                                                      EW_total_emission_structure.iloc[0, 3] + EW_total_emission_structure.iloc[0, 4])


                                            # 计算连续多年铺洒的平均碳封存量（tCO2/ha封存量-tCO2e/ha排放量，再根据年求平均得到GtCO2/yr）
                                            # 每个网格的铺洒年不同，约束是150t rock/ha，先计算每个网格在当前技术组合下的apply_years，注意：截止时间是2200年，有可能到2200年之前的某一年又需要再次铺洒（由于风化导致不满足约束）
                                            apply_years = np.zeros(end_year - start_year + 1)  # 当前网格的铺洒年份初始化为0，如果某年铺洒了，就将该年的值变为1
                                            apply_years_value = 0  # 总共铺洒的年数，以计算碳排放量
                                            rock_volume = np.zeros(end_year - start_year + 1)  # 记录每年农田中岩石的数量，t rock/ha
                                            weathering_volume = np.zeros(end_year - start_year + 1)  # 记录每年农田风化的岩石量，t rock/ha
                                            potential = np.zeros(end_year - start_year + 1)  # 初始化每年潜力数组，tCO2/ha
                                            for yr in range(end_year - start_year + 1):  # 在2025到2200年期间
                                                if yr == 0:  # 第一年只铺洒不风化
                                                    apply_years[yr] = 1
                                                    apply_years_value += 1
                                                    rock_volume[yr] = EW_data.iloc[15, 2]
                                                    weathering_volume[yr] = 0
                                                    potential[yr] = 0 - EW_total_emission_structure.iloc[0, 5] * EW_data.iloc[15, 2]
                                                else:  # 第2年开始，每年都铺洒新的，也会风化
                                                    indices = np.where(apply_years == 1)[0]
                                                    for t in range(apply_years_value):  # yr表示风化了多少年
                                                        weathering_volume[yr] += EW_data.iloc[15, 2] * CO2_seq_potential_annual.iloc[yr - indices[t], 1]
                                                    if rock_volume[yr - 1] - weathering_volume[yr] <= 150:  # 每年之初就判断农田的岩石数量是否超出限制，如果不超出限制，才能铺洒，如果超出限制，则不铺洒，只风化
                                                        apply_years[yr] = 1
                                                        apply_years_value += 1
                                                        rock_volume[yr] = rock_volume[yr - 1] + EW_data.iloc[15, 2] - weathering_volume[yr]  # 每年农田的岩石数量是在前一年的基础上，新增20t rock，再减去之前几年铺洒岩石的风化量
                                                        # potential[yr] = EW_data.iloc[28, 2] * EW_data.iloc[26 + r, 2] * weathering_volume[yr] / 1000 - EW_total_emission_structure.iloc[0, 5] * EW_data.iloc[15, 2]  # 每年的潜力=每年封存的-每年排放的（当年铺洒的那一次排放量），ERW作用路径1，EW_data.iloc[28, 2]
                                                        potential[yr] = EW_data.iloc[29, 2] * EW_data.iloc[26 + r, 2] * weathering_volume[yr] / 1000 - EW_total_emission_structure.iloc[0, 5] * EW_data.iloc[15, 2]  # ERW作用路径2，EW_data.iloc[29, 2]
                                                    else:  # 如果超出限制，则不铺洒，只风化
                                                        apply_years[yr] = 0
                                                        apply_years_value += 0
                                                        rock_volume[yr] = rock_volume[yr - 1] - weathering_volume[yr]
                                                        # potential[yr] = EW_data.iloc[28, 2] * EW_data.iloc[26 + r, 2] * weathering_volume[yr] / 1000 - 0  # ERW作用机理1
                                                        potential[yr] = EW_data.iloc[29, 2] * EW_data.iloc[26 + r, 2] * weathering_volume[yr] / 1000 - 0  # ERW作用机理2
                                            # print("当前网格的铺洒年为:", apply_years, apply_years_value)
                                            # print("当前网格的年岩石量为:", rock_volume)
                                            # print("当前网格的年风化岩石量为:", weathering_volume)
                                            # print("当前网格的年潜力为:", potential)
                                            # print("当前网格的铺洒一次的排放量", EW_total_emission_structure.iloc[0, 5])

                                            # 计算年平均值（GtCO2/yr）
                                            sum_potential = 0  # tCO2/ha
                                            for year in range(end_year - start_year + 1):
                                                sum_potential += potential[year]
                                            # print("累积碳潜力:", sum_potential)
                                            if sum_potential > 0:  # 当前网格多年的净碳潜力大于0
                                                EW_potential_raster_array_rock_rem[row, col] = sum_potential / (end_year - start_year + 1) * Grid_Cropland_Area_km2[row, col] * 100 * T_TO_GT  # GtCO2/yr
                                                EW_rem_potential_csv[row * 720 + col, r * 4 + s] = EW_potential_raster_array_rock_rem[row, col]
                                            # print(EW_potential_raster_array_rock_rem[row, col])
                                        else:
                                            print("1")


        # write raster data
        driver = gdal.GetDriverByName("GTiff")
        # note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
        EW_potential_raster_rock_rem = driver.Create(f'./Output/EW/China/Remove Potential/EW_multi_year_remove_potential_raster_{rock_type.iloc[r, 0]}_{grain_size.iloc[s, 0]} μm_1.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
        EW_potential_raster_rock_rem.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
        srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
        srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
        EW_potential_raster_rock_rem.SetProjection(srs.ExportToWkt())
        EW_potential_raster_rock_rem.GetRasterBand(1).WriteArray(EW_potential_raster_array_rock_rem)
        EW_potential_raster_rock_rem.FlushCache()
        EW_potential_raster_rock_rem = None  # prevent files from being locked

# 保存为csv文件
EW_rem_potential_csv_df = pd.DataFrame(EW_rem_potential_csv)
EW_rem_potential_csv_df.to_csv('./Output/EW/China/Remove Potential/Multi Year Remove Potential_1.csv')

