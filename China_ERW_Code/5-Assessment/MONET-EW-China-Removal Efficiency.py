import os
import pandas as pd
import numpy as np
from osgeo import gdal, osr
import sys
import matplotlib.pyplot as plt

def compute_removal_efficiency(
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
    work_index,
    F_80,
    mining_diesel,
    crushing_electricity,
    road_transport_diesel,
    rail_transport_diesel,
    ship_transport_HFO,
    rock_application_diesel,
    CO2_seq_potential_dict,
    pathway,
    uncertainty=False
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

    # construct efficiency raster data
    EW_efficiency_raster_array_rock = np.full((raster_row, raster_col), np.nan)

    # 记录每个网格的移除效率和风化速率
    # 动态计算情景总数 (例如 2 种岩石 * 11 种粒径 = 22)
    num_tech = num_of_type * num_of_grain_size

    # 使用 raster_row * raster_col 替代 360*720，并使用动态的 num_tech 替代 8
    EW_removal_efficiency_csv = np.full((raster_row * raster_col, num_tech), np.nan)
    EW_weathering_rate_csv = np.full((raster_row * raster_col, num_tech), np.nan)

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
            print(f"Calculating Efficiency for: {rock_name}, {current_p80} μm...")

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
            EW_China_transport_distance_array_rock = gdal.Open(f'E:/wzy/2-Grid-based-MONET/Global Data/EW/Output/EW_China_transport_distance_{rock_name}.tif').ReadAsArray()  # no trade
            # EW_global_transport_distance_array_rock = gdal.Open(f'./Global Data/EW/Output/EW_global_transport_distance_{rock_name} (with trade).tif').ReadAsArray()  # with trade
            weathering_rate_array = gdal.Open(f'E:/wzy/1-CDR-Base/EW/Output/Raster Data/2025/weathering_rate_{rock_name}_{current_p80} μm.tif').ReadAsArray()
            for row in range(raster_row):  # row, 345, raster_row
                for col in range(raster_col):  # col, 720, raster_col
                    if province_code_array[row, col] > 0:  # 中国省份代码都大于0
                        if EW_land_array[row, col] > 0:  # 耕地像素值代表该网格耕地比例，0-100
                            if not np.isnan(EW_China_transport_distance_array_rock[row, col]):  # no rock source in this country
                                if EEF_array[row, col] >= 0:
                                    # compute carbon emissions (tCO2e/t rock)
                                    EW_emission_structure.iloc[1, 1] = (crushing_electricity + 10 * work_index[r] * (1 / np.sqrt(grain_size.iloc[s, 0]) - 1 / np.sqrt(F_80))) * EEF_array[row, col] / 1000000

                                    EW_emission_structure.iloc[2, 0] = ((road_transport_diesel * transport_mode.iloc[0, 2] + rail_transport_diesel * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[2, 2] + ship_transport_HFO * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[7, 2]) * EW_China_transport_distance_array_rock[row, col] / 1000
                                    EW_emission_structure.iloc[2, 1] = ((road_transport_diesel * transport_mode.iloc[0, 2] + rail_transport_diesel * transport_mode.iloc[1, 2]) * 3.6 / Energy_data.iloc[2, 2] * Carbon_data.iloc[14, 2] + ship_transport_HFO * transport_mode.iloc[2, 2] * 3.6 / Energy_data.iloc[6, 2] * Carbon_data.iloc[19, 2]) * EW_China_transport_distance_array_rock[row, col] / 1000

                                    # compute total emissions
                                    EW_total_emission_structure.iloc[0, 2] = EW_emission_structure.iloc[1, 0] + EW_emission_structure.iloc[1, 1] + EW_emission_structure.iloc[1, 2]
                                    EW_total_emission_structure.iloc[0, 3] = EW_emission_structure.iloc[2, 0] + EW_emission_structure.iloc[2, 1] + EW_emission_structure.iloc[2, 2]
                                    EW_total_emission_structure.iloc[0, 5] = (EW_total_emission_structure.iloc[0, 1] + EW_total_emission_structure.iloc[0, 2] +
                                                                              EW_total_emission_structure.iloc[0, 3] + EW_total_emission_structure.iloc[0, 4])

                                    # change tCO2e/t rock to tCO2e/tCO2 sequestrated
                                    # EW's CO2 sequestration potential vary over time, equal to maximum CO2 sequestration potential * CR_EW, maximum CO2 sequestration potential is equal to 1.7 * carbonation potential
                                    # CR_EW = pd.read_csv(f'E:/wzy/1-CDR-Base/EW/Output/Weathering Rate_{current_p80} μm_pH{PH.iloc[p, 0]}.csv')  # order: dunite, basalt; mean, low, up

                                    # CO2_seq_potential_dunite = EW_data.iloc[28, 2] * EW_data.iloc[27, 2] * CR_EW.iloc[end_year - start_year, 1] / 100 0  # dunite, mean; attention: CR_EW.iloc[0, 0] is 0, 1, 2,......
                                    # 不归一化
                                    CO2_removal_potential_rock = CO2_seq_potential_rock[row, col] - EW_total_emission_structure.iloc[0, 5]
                                    csv_row_idx = row * raster_col + col
                                    csv_col_idx = r * num_of_grain_size + s
                                    if CO2_removal_potential_rock > 0:
                                        removal_efficiency_rock = CO2_removal_potential_rock / CO2_seq_potential_rock[row, col]
                                        EW_weathering_rate_csv[csv_row_idx, csv_col_idx] = weathering_rate_array[row, col]
                                    else:
                                        # print("1")
                                        removal_efficiency_rock = np.nan


                                    EW_efficiency_raster_array_rock[row, col] = removal_efficiency_rock
                                    EW_removal_efficiency_csv[csv_row_idx, csv_col_idx] = EW_efficiency_raster_array_rock[row, col]

                                else:
                                    # print("2")
                                    EW_efficiency_raster_array_rock[row, col] = np.nan
                            else:
                                # print("3")
                                EW_efficiency_raster_array_rock[row, col] = np.nan
                        else:
                            # print("4")
                            EW_efficiency_raster_array_rock[row, col] = np.nan
                    else:
                        # print("5")
                        EW_efficiency_raster_array_rock[row, col] = np.nan

            if uncertainty==False:
                if pathway == 1:
                    # write raster data
                    driver = gdal.GetDriverByName("GTiff")
                    # note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
                    # EW_efficiency_raster_rock = driver.Create(f'./Output/EW/Removal Efficiency/Global Output/EW_removal_efficiency_raster_{rock_name}_{current_p80} μm.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_efficiency_raster_rock = driver.Create(f'E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/EW_removal_efficiency_raster_{rock_name}_{current_p80} μm.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_efficiency_raster_rock.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
                    srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
                    srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
                    EW_efficiency_raster_rock.SetProjection(srs.ExportToWkt())
                    EW_efficiency_raster_rock.GetRasterBand(1).WriteArray(EW_efficiency_raster_array_rock)
                    EW_efficiency_raster_rock.FlushCache()
                    EW_efficiency_raster_rock = None  # prevent files from being locked
                if pathway == 2:
                    # write raster data
                    driver = gdal.GetDriverByName("GTiff")
                    # note: xsize=ecological_zones_raster_array.shape[1], not [0]; eType=gdal.GDT_Float32
                    # EW_efficiency_raster_rock = driver.Create(f'./Output/EW/Removal Efficiency/Global Output/EW_removal_efficiency_raster_{rock_name}_{current_p80} μm.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_efficiency_raster_rock = driver.Create(f'E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/EW_removal_efficiency_raster_{rock_name}_{current_p80} μm_1.tif', xsize=raster_col, ysize=raster_row, bands=1, eType=gdal.GDT_Float32)  # note: xsize=ecological_zones_raster_array.shape[1], not [0]
                    EW_efficiency_raster_rock.SetGeoTransform([-180, 0.5, 0, 90, 0, -0.5])  # 设置地理变换参数;原点；左上角坐标(-180, 90)，像元大小(0.5 x 0.5)，即0.5°分辨率
                    srs = osr.SpatialReference()  # 设置坐标参考系为 WGS 1984 (EPSG:4326)
                    srs.ImportFromEPSG(4326)  # WGS 1984 的 EPSG 编号是 4326
                    EW_efficiency_raster_rock.SetProjection(srs.ExportToWkt())
                    EW_efficiency_raster_rock.GetRasterBand(1).WriteArray(EW_efficiency_raster_array_rock)
                    EW_efficiency_raster_rock.FlushCache()
                    EW_efficiency_raster_rock = None  # prevent files from being locked

    if uncertainty == False:
        if pathway == 1:
            # 保存为csv文件
            EW_removal_efficiency_csv_df = pd.DataFrame(EW_removal_efficiency_csv)
            # EW_removal_efficiency_csv_df.to_csv('./Output/EW/Removal Efficiency/Global Output/Removal Efficiency.csv')
            EW_removal_efficiency_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/Removal Efficiency.csv')

            EW_weathering_rate_csv_df = pd.DataFrame(EW_weathering_rate_csv)
            # EW_weathering_rate_csv_df.to_csv('./Output/EW/Removal Efficiency/Global Output/Weathering Rate.csv')
            EW_weathering_rate_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/Weathering Rate.csv')
        if pathway == 2:
            # 保存为csv文件
            EW_removal_efficiency_csv_df = pd.DataFrame(EW_removal_efficiency_csv)
            # EW_removal_efficiency_csv_df.to_csv('./Output/EW/Removal Efficiency/Global Output/Removal Efficiency.csv')
            EW_removal_efficiency_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/Removal Efficiency_1.csv')

            EW_weathering_rate_csv_df = pd.DataFrame(EW_weathering_rate_csv)
            # EW_weathering_rate_csv_df.to_csv('./Output/EW/Removal Efficiency/Global Output/Weathering Rate.csv')
            EW_weathering_rate_csv_df.to_csv('E:/wzy/2-Grid-based-MONET/Output/EW/China/Removal Efficiency/Weathering Rate_1.csv')
    else:
        # 不确定性分析，返回 numpy 数组给外层
        return {
            "EW_removal_efficiency_csv": EW_removal_efficiency_csv,
            "EW_weathering_rate_csv": EW_weathering_rate_csv
        }


if __name__ == "__main__":
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

    work_index = [17.93, 12.38]  # basalt=17.93, dunite=12.38
    F_80 = 1000  # μm

    compute_removal_efficiency(
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
        work_index,
        F_80,
        mining_diesel=EW_data.iloc[3, 2],
        crushing_electricity=EW_data.iloc[4, 2],
        road_transport_diesel=Energy_data.iloc[18, 2],
        rail_transport_diesel=Energy_data.iloc[19, 2],
        ship_transport_HFO=Energy_data.iloc[20, 2],
        rock_application_diesel=EW_data.iloc[7, 2],
        CO2_seq_potential_dict=None,
        pathway=1,
        uncertainty=False
    )
