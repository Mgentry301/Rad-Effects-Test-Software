#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import sys
import os
import time
import settings
import clr                                           

dpgdir32 = settings.lib_folder
sys.path.append(r'C:\Git\Rad-Effects-Test-Software\PythonScripts\AD\AD9082\API\data_control_libs')
#sys.path.append("..\data_control_libs")

clr.AddReference('AnalogDevices.TxfeSupport.Common')
clr.AddReference('AnalogDevices.TxfeSupport.Ads9Lite')

from AnalogDevices.TxfeSupport.Ads9Lite import DPG as ADS9V2 # pylint: disable=import-error

class DPGError(Exception):
    pass

class DPG(object):
    """A wrapper class for .NET dpg objects.
    """
    def __init__(self, index=0):
        """
        Constructor
        """
        hwi = ADS9V2()
        attachedDevices = hwi.AttachedDevices
        num_dpgs = len(attachedDevices)
        if (num_dpgs == 0):
            raise DPGError('No DPGs are connected.')
        elif (index > num_dpgs-1):
            raise DPGError('Invalid DPG index. Entered %d, but only 0-%d are valid' % (index, num_dpgs-1))
      
        self.index = index
        self.net = attachedDevices[index]

    def configure_fpga_image(self, fpga_image_name, turn_on_fmc_power=True):
        """
        Downloads the fpga image file to the DPG device.
        """
        fpga_image_full_path = os.path.join(settings.fpga_folder, fpga_image_name)
        
        if not os.path.isfile(fpga_image_full_path) :
            print("The FPGA image file doesn't exist: ", fpga_image_full_path)

        print("Configuring fpga from: ", fpga_image_full_path)
        try:
            fpga_dl_err = self.net.DownloadConfiguration(fpga_image_full_path)
        except Exception as e:
            fpga_dl_err = True

        if (fpga_dl_err):
            print("Error occurred downloading fpga configuration.")
            return -1

        if (turn_on_fmc_power):
            self.turn_on_fmc_power()

        return 0

    def turn_on_fmc_power(self):
        """
        Turns on FMC power
        """
        self.net.TurnOnFmcSupplies()
        return 0

def get_dpg_device():
    """
    Factory method to get a connected DPG instance.
    """
    try:
        dpg = DPG(0)
        if (dpg.net.FriendlyName != 'ADS9-V2'):
            print("Only ADS9-V2 is supported (this board is ", dpg.net.FriendlyName, ")")
            return None
    except Exception as e:
        print("Can't find ADS9 controller board: " + str(e))
        return None
    return dpg

if __name__ == '__main__':
    # Get a connected DPG instance
    dpg = get_dpg_device()
    if (dpg):
        print("FriendlyName is " , dpg.net.FriendlyName)
    print("Done")
