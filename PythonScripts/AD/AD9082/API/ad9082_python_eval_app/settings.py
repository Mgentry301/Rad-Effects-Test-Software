#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function

#Customer Configurable Settings
device = "ad9082"  

#Desired Clocking Scheme: 
use_7044 = False                    # Use HMC7044 to generate reference clocks
enable_pll = False                  # Use AD9081/2 On-chip PLL to generate ADC & DAC Clocks
hmc7044_crystal_freq = 122.88e6 if (device == "ad9986" or device == "ad9988") else 100e6    # 122.88MHz for EBZ-W2 eval boards. 100.00MHz for EBZ-A2


#ADI Platform Recommended Settings
#Default Settings for ADI AD9081/2 Evaluation Platform - Do Not adjust for Correct Operation with ADI Platforms
#ADS Microzed IP Address
ip_address = "192.168.0.10"
eval_board_type = "pe"  # "pe" or "ce" 

# Folder locations
erpc_folder = r'C:\Git\Rad-Effects-Test-Software\PythonScripts\AD\AD9082\API\erpc_pkgs'        # erpc client/server
fpga_folder = r'C:\Git\Rad-Effects-Test-Software\PythonScripts\AD\AD9082\API\fpga_images'      # FPGA images for PE and CE boards
lib_folder = r'C:\Git\Rad-Effects-Test-Software\PythonScripts\AD\AD9082\API\data_control_libs'         # .net dlls (e.g. DPG)

# FPGA images
fpga_ce = r'ad9986_ads9v2_fmc.bin'
fpga_pe = r'C:\Git\Rad-Effects-Test-Software\PythonScripts\AD\AD9082_PE_Board.bin'
always_load_fpga_image = False # If True, fpga image is always loaded at startup. If False, will only load image if one not detected.

def info():
    """Prints summary information about the settings"""
    return  'eval_board_type: {}'.format(eval_board_type) + \
            ' use_7044: {}'.format(use_7044) + \
            ' hmc7044_crystal_freq: {} MHz'.format(hmc7044_crystal_freq/1e6) + \
            ' enable_pll: {}'.format(enable_pll)
