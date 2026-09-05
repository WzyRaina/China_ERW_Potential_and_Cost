# 本程序用于确定参数下的计算（不考虑贸易，路径2）
# 写成调用函数的形式，可以一次性运行所有代码

import os
import pandas as pd
import numpy as np
from osgeo import gdal, osr
import sys
import matplotlib.pyplot as plt
import importlib.util
from multiprocessing import Pool

# ==== 1. 导入各函数 ====
# 函数1：计算粒径分布: grain_size_distribution_py.generate_psd_for_multiple_p80(...)
grain_size_distribution_file_path = r"E:/wzy/1-CDR-Base/EW/Grain_Size_Distribution_More_Sizes.py"
spec_1 = importlib.util.spec_from_file_location("grain_size_distribution", grain_size_distribution_file_path)
grain_size_distribution_py = importlib.util.module_from_spec(spec_1)
spec_1.loader.exec_module(grain_size_distribution_py)
# 函数2：计算到目标年份的碳封存潜力
carbon_sequestration_file_path = r"E:/wzy/1-CDR-Base/EW/ERW_Core_Model.py"
spec_2 = importlib.util.spec_from_file_location("carbon_sequestration", carbon_sequestration_file_path)
carbon_sequestration_py = importlib.util.module_from_spec(spec_2)
spec_2.loader.exec_module(carbon_sequestration_py)
# 函数3：计算移除效率: removal_efficiency_py.compute_removal_efficiency(...)
removal_efficiency_file_path = r"E:/wzy/2-Grid-based-MONET/Code/EW/China/5-Assessment/MONET-EW-China-Removal Efficiency.py"
spec_3 = importlib.util.spec_from_file_location("removal_efficiency", removal_efficiency_file_path)
removal_efficiency_py = importlib.util.module_from_spec(spec_3)
spec_3.loader.exec_module(removal_efficiency_py)
# 函数4：计算碳移除潜力: removal_potential_py.compute_removal_potential(...)
removal_potential_file_path = r"E:/wzy/2-Grid-based-MONET/Code/EW/China/5-Assessment/MONET-EW-China-Potential.py"
spec_4 = importlib.util.spec_from_file_location("removal_potential", removal_potential_file_path)
removal_potential_py = importlib.util.module_from_spec(spec_4)
spec_4.loader.exec_module(removal_potential_py)
# 函数5：计算碳移成本: removal_cost_py.compute_removal_cost(...)
removal_cost_file_path = r"E:/wzy/2-Grid-based-MONET/Code/EW/China/5-Assessment/MONET-EW-China-Cost.py"
spec_5 = importlib.util.spec_from_file_location("removal_cost", removal_cost_file_path)
removal_cost_py = importlib.util.module_from_spec(spec_5)
spec_5.loader.exec_module(removal_cost_py)

# ==== 2. 导入数据 ====
# read electricity emission factors (from ArcGISPro)
EEF_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Emission_Factor.tif').ReadAsArray()  # 0.5°*0.5°; unit: gCO2eq/kWh; /3600 (kgCO2e/MJ)
# land available for EW
EW_land_array = gdal.Open('E:/wzy/2-Grid-based-MONET/Global Data/EW/Input/China/China_Cropland_CACD_2021_0.5.tif').ReadAsArray()
# 中国省级边界栅格，每个网格的值是省份代码
province_code_array = gdal.Open('E:/ArcGIS Project/ChinaData/China_province.tif').ReadAsArray()

raster_row = 360
raster_col = 720

pathway = 2

target_p80_list = [2, 10, 20, 50, 100, 250, 500, 750, 1000, 1500, 2000]
num_grain_sizes = len(target_p80_list)
num_rock_types = 2
num_tech = num_grain_sizes * num_rock_types
num_pixels = raster_col * raster_row
tech_labels = []
for rock in ["basalt", "dunite"]:
    for p in target_p80_list:
        tech_labels.append(f"{rock}_{p}μm")

start_year = 2025
end_year = 2100

Grid_Cropland_Area_km2 = gdal.Open('E:/wzy/2-Grid-based-MONET/Global Data/EW/Input/China/China_cropland_area_km2.tif').ReadAsArray()  # 每个网格的耕地面积（km2）（0.5° 分辨率的网格面积不一定是为 55km x 55km，要提前根据经纬度换算，并且乘网格的耕地比例）
T_TO_GT = 1e-9  # 吨到千兆吨的转换系数

work_index = [17.93, 12.38]  # basalt=17.93, dunite=12.38
F_80 = 1000  # μm

# read specific EW data
EW_data = pd.read_csv('E:/wzy/2-Grid-based-MONET/Raw Data/EW/EW.csv', encoding='gbk')
# read common data
Energy_data = pd.read_csv('E:/wzy/2-Grid-based-MONET/Raw Data/Common Data/Energy.csv')  # parameters about energy
Carbon_data = pd.read_csv('E:/wzy/2-Grid-based-MONET/Raw Data/Common Data/China Carbon.csv', encoding='gbk')  # parameters about carbon
# read input data by myself
grain_size = pd.read_csv('E:/wzy/2-Grid-based-MONET/Input Data/EW/Grain Size More.csv', encoding='gbk')  # grain size settings
# read rock type
rock_type = pd.read_csv('E:/wzy/2-Grid-based-MONET/Input Data/EW/Rock Type.csv', encoding='gbk')  # rock type settings
# read other parameters
other_data = pd.read_csv('E:/wzy/2-Grid-based-MONET/Input Data/EW/Other Data.csv', encoding='gbk')  # other parameters
transport_mode = pd.read_csv('E:/wzy/2-Grid-based-MONET/Raw Data/Common Data/China Transport Mode.csv', encoding='gbk')
transport_cost = pd.read_csv('E:/wzy/2-Grid-based-MONET/Raw Data/Common Data/China Transport Mode Cost.csv', encoding='gbk')

PH = gdal.Open('E:/ArcGIS/Projects/GetData/T_PH_H20.tif')
PH_array = PH.ReadAsArray()
soil_temperature = gdal.Open('E:/ArcGIS/Projects/Biomass Yield/Soil_Temperature.tif')
soil_temperature_array = soil_temperature.ReadAsArray()

# read cost data
# diesel cost
diesel_cost_array = gdal.Open('E:/ArcGIS Project/ChinaData/Diesel_Cost_Raster.tif').ReadAsArray()  # $/l
# electricity price
electricity_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Electricity_Price_Raster.tif').ReadAsArray()  # $/MWh; /3600 ($/MJ)
rock_price_array = gdal.Open('E:/ArcGIS Project/ChinaData/Rock_Price.tif').ReadAsArray()  # $/t rock

# ==== 3. 设定参数不确定性范围以及蒙特卡洛模拟参数 ====
param = {
    'sigma': 0.5,
    'k_H_dunite': 5.55e-8,
    'n_H_dunite': 0.372,
    'k_H_basalt': 588,
    'n_H_basalt': 1.16,
    'k_OH_basalt': 0.0822,
    'n_OH_basalt': 0.16,
    'E_a': 47500,
    'b': 5.2,
    'm': -1.0,
    'mining_diesel': 4.17,
    'crushing_electricity': 3.25,
    'road_transport_diesel': 0.1146,
    'rail_transport_diesel': 0.0177,
    'ship_transport_HFO': 0.0303,
    'rock_application_diesel': 4.92,
    'road_transport_price': 0.069,
    'rail_transport_price': 0.022,
    'ship_transport_price': 0.005,
    'rock_application_price': 5.833,
    'application_price_factor': 2.5
}

# ==== 4. 按步骤使用函数计算 ====
# ==== 步骤：生成粒径分布，计算到2100年的碳封存潜力、计算移除效率、碳移除潜力、碳移除成本 ====
# 生成粒径分布
print("正在生成粒径分布...")
psd_dict = grain_size_distribution_py.generate_psd_for_multiple_p80(
    sigma=param['sigma'],
    p80_list=target_p80_list,  # <--- 将动态列表传给函数
    save_folder='E:/wzy/1-CDR-Base/EW/Output/Grain Size Distribution/',
    plot=False,
    uncertainty=False
)

print("正在计算碳封存潜力...")
# 动态生成 CSV 路径列表
dynamic_grain_size_files = [
    f'E:/wzy/1-CDR-Base/EW/Output/Grain Size Distribution/Grain Size Distribution ({int(p)} μm).csv'
    for p in target_p80_list
]

# 计算到2100年的碳封存潜力
carbon_sequestration_py.carbon_sequestration_potential(
    EW_raw_data=EW_data,
    grain_size=grain_size,
    PH_array=PH_array,
    soil_temperature_array=soil_temperature_array,
    start_year=2025,
    end_year=2100,
    simulated_year=200,
    k_H_dunite=param['k_H_dunite'],
    n_H_dunite=param['n_H_dunite'],
    k_H_basalt=param['k_H_basalt'],
    n_H_basalt=param['n_H_basalt'],
    k_OH_basalt=param['k_OH_basalt'],
    n_OH_basalt=param['n_OH_basalt'],
    E_a=param['E_a'],
    b=param['b'],
    m=param['m'],
    pathway=pathway,
    grain_size_psd_dict=psd_dict,
    output_folder="E:/wzy/1-CDR-Base/EW/Output/Raster Data/",
    uncertainty=False
)

print("正在计算移除效率...")
# 计算移除效率
removal_efficiency_py.compute_removal_efficiency(
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
    mining_diesel=param['mining_diesel'],
    crushing_electricity=param['crushing_electricity'],
    road_transport_diesel=param['road_transport_diesel'],
    rail_transport_diesel=param['rail_transport_diesel'],
    ship_transport_HFO=param['ship_transport_HFO'],
    rock_application_diesel=param['rock_application_diesel'],
    CO2_seq_potential_dict=None,
    pathway=pathway,
    uncertainty=False
)

print("正在计算碳移除潜力...")
# 计算碳移除潜力
removal_potential_py.compute_removal_potential(
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
    mining_diesel=param['mining_diesel'],
    crushing_electricity=param['crushing_electricity'],
    road_transport_diesel=param['road_transport_diesel'],
    rail_transport_diesel=param['rail_transport_diesel'],
    ship_transport_HFO=param['ship_transport_HFO'],
    rock_application_diesel=param['rock_application_diesel'],
    pathway=pathway,
    uncertainty=False
)

print("正在计算碳移除成本...")
# 计算碳移除成本
removal_cost_py.compute_removal_cost(
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
    diesel_cost_array,
    electricity_price_array,
    rock_price_array,
    mining_diesel=param['mining_diesel'],
    crushing_electricity=param['crushing_electricity'],
    road_transport_diesel=param['road_transport_diesel'],
    rail_transport_diesel=param['rail_transport_diesel'],
    ship_transport_HFO=param['ship_transport_HFO'],
    rock_application_diesel=param['rock_application_diesel'],
    road_transport_price=param['road_transport_price'],
    rail_transport_price=param['rail_transport_price'],
    ship_transport_price=param['ship_transport_price'],
    rock_application_price=param['rock_application_price'],
    application_price_factor=param['application_price_factor'],
    pathway=pathway,
    uncertainty=False
)

print("全部计算任务顺利完成！")
