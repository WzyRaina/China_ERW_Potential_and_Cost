# 潜力：tCO2 rem （每个网格的tCO2 rem/ha * ha）

import os
import pandas as pd
import numpy as np
from osgeo import gdal, osr
import sys
import matplotlib.pyplot as plt

def compute_removal_potential(
    EEF_array,
    EW_land_array,
    province_code_array,
    raster_row,
    raster_col,
    rock_type,
    grain_size,
    EW_data,
    Energy_data,
    Carbon_data,
    transport_mode,
    other_data,
    Grid_Cropland_Area_km2,
    T_TO_GT,
    work_index,
    F_80,
    mining_diesel,
    crushing_electricity,
    road_transport_diesel,
    rail_transport_diesel,
    ship_transport_HFO,
    rock_application_diesel,
    pathway,
    uncertainty=False,
    CO2_seq_potential_dict=None
):

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

    # construct potential raster data (tCO2 cap)
    EW_potential_raster_array_rock_cap = np.full((raster_row, raster_col), np.nan)
    # construct potential raster data (tCO2 rem)
    EW_potential_raster_array_rock_rem = np.full((raster_row, raster_col), np.nan)

    # 记录每个网格的累积潜力
    # 动态计算情景总数 (例如 2 种岩石 * 11 种粒径 = 22)
    num_tech = num_of_type * num_of_grain_size

    # 使用 raster_row * raster_col 替代 360*720，并使用动态的 num_tech 替代 8
    EW_rem_potential_csv = np.full((raster_row * raster_col, num_tech), np.nan)  # MtCO2
    EW_rem_potential_csv_1 = np.full((raster_row * raster_col, num_tech), np.nan)  # tCO2/ha

    # compute carbon emissions
    # compute carbon emissions (tCO2e/t rock)
    # row 1
    EW_emission_structure.iloc[0, 0] = mining_diesel / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] / 1000  # kWh/t rock / 1000 = MWh/t rock, MWh/t rock * 3600 = MJ/t rock
    EW_emission_structure.iloc[0, 1] = mining_diesel / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] / 1000
    EW_emission_structure.iloc[0, 2] = EW_data.iloc[9, 2] * EW_data.iloc[10, 2] * EW_data.iloc[24, 2] * (Carbon_data.iloc[26, 2] + (Carbon_data.iloc[46, 2] + Carbon_data.iloc[47, 2] * Carbon_data.iloc[48, 2] + Carbon_data.iloc[49, 2] * Carbon_data.iloc[50, 2]) * EW_data.iloc[23, 2] * other_data.iloc[0, 2]) / 1000
    # row 2
    EW_emission_structure.iloc[1, 0] = 0
    EW_emission_structure.iloc[1, 2] = 0
    # row 3
    EW_emission_structure.iloc[2, 2] = 0
    # row 4
    EW_emission_structure.iloc[3, 0] = rock_application_diesel / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] / 1000
    EW_emission_structure.iloc[3, 1] = rock_application_diesel / 1000 * 3600 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] / 1000
    EW_emission_structure.iloc[3, 2] = 0

    EW_total_emission_structure.iloc[0, 1] = EW_emission_structure.iloc[0, 0] + EW_emission_structure.iloc[0, 1] + EW_emission_structure.iloc[0, 2]
    EW_total_emission_structure.iloc[0, 4] = EW_emission_structure.iloc[3, 0] + EW_emission_structure.iloc[3, 1] + EW_emission_structure.iloc[3, 2]

    for r in range(num_of_type):
        # print(rock_type.iloc[r, 0])
        for s in range(num_of_grain_size):
            current_p80 = int(grain_size.iloc[s, 0])
            rock_name = rock_type.iloc[r, 0]
            print(f"Calculating Potential for: {rock_name}, {current_p80} μm...")

            if uncertainty:
                if pathway == 1:
                    CO2_seq_potential_rock = CO2_seq_potential_dict[(rock_name.lower(), f"{current_p80}μm")]
                if pathway == 2:
                    CO2_seq_potential_rock = CO2_seq_potential_dict[(rock_name.lower(), f"{current_p80}μm_1")]
            else:
                if pathway == 1:
                    CO2_seq_potential_rock = gdal.Open(f'E:/wzy/1-CDR-Base/EW/Output/Raster Data/2025/CO2_seq_potential_{rock_name}(tCO2·t rock-1)_{current_p80} μm.tif').ReadAsArray()
                if pathway == 2:
                    CO2_seq_potential_rock = gdal.Open(f'E:/wzy/1-CDR-Base/EW/Output/Raster Data/2025/CO2_seq_potential_{rock_name}(tCO2·t rock-1)_{current_p80} μm_1.tif').ReadAsArray()
            # transport distance
            EW_global_transport_distance_array_rock = gdal.Open(f'E:/wzy/2-Grid-based-MONET/Global Data/EW/Output/EW_China_transport_distance_{rock_name}.tif').ReadAsArray()  # no trade
            # EW_global_transport_distance_array_rock = gdal.Open(f'./Global Data/EW/Output/EW_global_transport_distance_{rock_name} (with trade).tif').ReadAsArray()  # with trade
            for row in range(raster_row):  # row, 345, raster_row
                for col in range(raster_col):  # col, 720, raster_col
                    csv_row_idx = row * raster_col + col
                    csv_col_idx = r * num_of_grain_size + s

                    if province_code_array[row, col] > 0:  # 中国省份代码都大于0
                        if EW_land_array[row, col] > 0:  # available for EW
                            if not np.isnan(EW_global_transport_distance_array_rock[row, col]):  # no rock source in this country
                                if EEF_array[row, col] >= 0:
                                    # compute carbon emissions (tCO2e/t rock)
                                    EW_emission_structure.iloc[1, 1] = (crushing_electricity + 10 * work_index[r] * (1 / np.sqrt(grain_size.iloc[s, 0]) - 1 / np.sqrt(F_80))) * EEF_array[row, col] / 1000000

                                    EW_emission_structure.iloc[2, 0] = ((road_transport_diesel * transport_mode.iloc[0, 2] + rail_transport_diesel * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] + ship_transport_HFO * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[7, 2]) * EW_global_transport_distance_array_rock[row, col] / 1000
                                    EW_emission_structure.iloc[2, 1] = ((road_transport_diesel * transport_mode.iloc[0, 2] + rail_transport_diesel * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] + ship_transport_HFO * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[19, 2]) * EW_global_transport_distance_array_rock[row, col] / 1000

                                    # compute total emissions
                                    EW_total_emission_structure.iloc[0, 2] = EW_emission_structure.iloc[1, 0] + EW_emission_structure.iloc[1, 1] + EW_emission_structure.iloc[1, 2]
                                    EW_total_emission_structure.iloc[0, 3] = EW_emission_structure.iloc[2, 0] + EW_emission_structure.iloc[2, 1] + EW_emission_structure.iloc[2, 2]
                                    EW_total_emission_structure.iloc[0, 5] = (EW_total_emission_structure.iloc[0, 1] + EW_total_emission_structure.iloc[0, 2] +
                                                                              EW_total_emission_structure.iloc[0, 3] + EW_total_emission_structure.iloc[0, 4])

                                    # 不归一化
                                    CO2_removal_potential_rock = CO2_seq_potential_rock[row, col] - EW_total_emission_structure.iloc[0, 5]
                                    if CO2_removal_potential_rock > 0:  # tCO2/t rock
                                        # turn tCO2/t rock to tCO2/ha to tCO2
                                        EW_potential_raster_array_rock_cap[row, col] = CO2_seq_potential_rock[row, col] * EW_data.iloc[15, 2]  # 单位为tCO2/ha；如果用MtCO2为单位:  * Grid_Cropland_Area_km2[row, col] * 100 * T_TO_GT * 1000
                                        EW_potential_raster_array_rock_rem[row, col] = CO2_removal_potential_rock * EW_data.iloc[15, 2]  # 单位为tCO2/ha；如果用MtCO2为单位:  * Grid_Cropland_Area_km2[row, col] * 100 * T_TO_GT * 1000
                                        EW_rem_potential_csv[csv_row_idx, csv_col_idx] = EW_potential_raster_array_rock_rem[row, col]  # 单位为tCO2/ha
                                        EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = CO2_removal_potential_rock  # tCO2/t rock
                                    else:
                                        EW_potential_raster_array_rock_cap[row, col] = np.nan
                                        EW_potential_raster_array_rock_rem[row, col] = np.nan
                                        EW_rem_potential_csv[csv_row_idx, csv_col_idx] = np.nan
                                        EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = np.nan

                                else:
                                    EW_potential_raster_array_rock_cap[row, col] = np.nan
                                    EW_potential_raster_array_rock_rem[row, col] = np.nan
                                    EW_rem_potential_csv[csv_row_idx, csv_col_idx] = np.nan
                                    EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = np.nan
                            else:
                                EW_potential_raster_array_rock_cap[row, col] = np.nan
                                EW_potential_raster_array_rock_rem[row, col] = np.nan
                                EW_rem_potential_csv[csv_row_idx, csv_col_idx] = np.nan
                                EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = np.nan
                        else:
                            EW_potential_raster_array_rock_cap[row, col] = np.nan
                            EW_potential_raster_array_rock_rem[row, col] = np.nan
                            EW_rem_potential_csv[csv_row_idx, csv_col_idx] = np.nan
                            EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = np.nan
                    else:
                        EW_potential_raster_array_rock_cap[row, col] = np.nan
                        EW_potential_raster_array_rock_rem[row, col] = np.nan
                        EW_rem_potential_csv[csv_row_idx, csv_col_idx] = np.nan
                        EW_rem_potential_csv_1[csv_row_idx, csv_col_idx] = np.nan

            if uncertainty == False:
                if pathway == 1:
                    # write raster data
                    driver = gdal.GetDriverByName("GTiff")
                    # note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
                    EW_potential_raster_rock_rem = driver.Create(f'E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/EW_remove_potential_raster_{rock_name}_{current_p80} μm.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_potential_raster_rock_rem.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
                    srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
                    srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
                    EW_potential_raster_rock_rem.SetProjection(srs.ExportToWkt())
                    EW_potential_raster_rock_rem.GetRasterBand(1).WriteArray(EW_potential_raster_array_rock_rem)
                    EW_potential_raster_rock_rem.FlushCache()
                    EW_potential_raster_rock_rem = None  # prevent files from being locked
                if pathway == 2:
                    # write raster data
                    driver = gdal.GetDriverByName("GTiff")
                    # note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
                    EW_potential_raster_rock_rem = driver.Create(f'E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/EW_remove_potential_raster_{rock_name}_{current_p80} μm_1.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_potential_raster_rock_rem.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
                    srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
                    srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
                    EW_potential_raster_rock_rem.SetProjection(srs.ExportToWkt())
                    EW_potential_raster_rock_rem.GetRasterBand(1).WriteArray(EW_potential_raster_array_rock_rem)
                    EW_potential_raster_rock_rem.FlushCache()
                    EW_potential_raster_rock_rem = None  # prevent files from being locked

    if uncertainty == False:
        if pathway == 1:
            # 保存为csv文件
            EW_rem_potential_csv_df = pd.DataFrame(EW_rem_potential_csv)
            EW_rem_potential_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/Remove Potential.csv', index=False)
            EW_rem_potential_csv_df_1 = pd.DataFrame(EW_rem_potential_csv_1)
            EW_rem_potential_csv_df_1.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/Remove Potential (tCO2 t rock-1).csv', index=False)
        if pathway == 2:
            # 保存为csv文件
            EW_rem_potential_csv_df = pd.DataFrame(EW_rem_potential_csv)
            EW_rem_potential_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/Remove Potential_1.csv', index=False)
            EW_rem_potential_csv_df_1 = pd.DataFrame(EW_rem_potential_csv_1)
            EW_rem_potential_csv_df_1.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Remove Potential/Remove Potential (tCO2 t rock-1)_1.csv', index=False)
    else:
        # 不确定性分析，返回 numpy 数组给外层
        return {
            "EW_rem_potential_csv": EW_rem_potential_csv
        }

if __name__ == "__main__":
    # 调用函数
    os.chdir('E:/wzy/2-Grid-based-MONET')

    # read electricity emission factors (from ArcGISPro)
    EEF_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Emission_Factor.tif').ReadAsArray()  # 0.5°*0.5°; unit: gCO2eq/kWh; /3600 (kgCO2e/MJ)
    # np.set_printoptions(threshold=sys.maxsize)

    # land available for EW
    EW_land_array = gdal.Open('./Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif').ReadAsArray()

    # 中国省级边界栅格，每个网格的值是省份代码
    province_code_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_province.tif').ReadAsArray()

    # raster's row and col depend on EEF_array
    raster_row = 360
    raster_col = 720

    # 定义常量
    Grid_Cropland_Area_km2 = gdal.Open('./Global Data/EW/Input/China/China_cropland_area_km2.tif').ReadAsArray()  # 每个网格的耕地面积（km2）（0.5° 分辨率的网格面积不一定是为 55km x 55km，要提前根据经纬度换算，并且乘网格的耕地比例）
    T_TO_GT = 1e-9  # 吨到千兆吨的转换系数

    work_index = [17.93, 12.38]  # basalt=17.93, dunite=12.38
    F_80 = 1000  # μm

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
    # print(diesel_cost_array.shape)
    # electricity price
    electricity_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Price_Raster.tif').ReadAsArray()  # $/MWh; /3600 ($/MJ)
    # print(electricity_price_array.shape)
    rock_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Rock_Price.tif').ReadAsArray()  # $/t rock
    # print(rock_price_array.shape)

    compute_removal_potential(
        EEF_array,
        EW_land_array,
        province_code_array,
        raster_row,
        raster_col,
        rock_type,
        grain_size,
        EW_data,
        Energy_data,
        Carbon_data,
        transport_mode,
        other_data,
        Grid_Cropland_Area_km2,
        T_TO_GT,
        work_index,
        F_80,
        mining_diesel=EW_data.iloc[3, 2],
        crushing_electricity=EW_data.iloc[4, 2],
        road_transport_diesel=Energy_data.iloc[18, 2],
        rail_transport_diesel=Energy_data.iloc[19, 2],
        ship_transport_HFO=Energy_data.iloc[20, 2],
        rock_application_diesel=EW_data.iloc[7, 2],
        pathway=1,
        uncertainty=False
    )
