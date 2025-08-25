#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import sys
import time
import clr
import os
import settings
import erpc_factory

# Add reference to the erpc client dll
sys.path.append(os.path.join(settings.erpc_folder, erpc_factory.erpc, r"lib\net40"))
clr.AddReference(erpc_factory.erpc_client)
from ad9082_erpc import ads9, ad9082, hmc7044, adi_cms_chip_id_t, TCPTransport   # pylint: disable=import-error

class Ad9082Client(object):
    """A utility class for accessing the .NET ad9082_erpc client
    """
    def __init__(self, ipaddr="192.168.0.10"):
        """Constructor"""

        tt = TCPTransport(ipaddr, 12345, False)     # pylint: disable=undefined-variable
        print("ads9 erpcgen_version:    ", ads9.erpcgen_version, "/", ads9.erpc_generated_crc)
        print("ad9082 erpcgen_version:  ", ad9082.erpcgen_version, "/", ad9082.erpc_generated_crc)
        print("hmc7044 erpcgen_version: ", hmc7044.erpcgen_version, "/", hmc7044.erpc_generated_crc)

        self.ads9 = ads9(tt)
        self.ad9082 = ad9082(tt)
        self.hmc7044 = hmc7044(tt)

    def __del__(self):
        #print('Destructor called, Ad9082Client')
        pass

    def get_devices(self):
        """ Returns the device handles """
        return [self.ads9, self.ad9082, self.hmc7044]

if __name__ == '__main__':

    # Create class instance
    ad9082_client = Ad9082Client()
    ads9, ad9082, hmc7044 = ad9082_client.get_devices()

    # Read FPGA version
    returned_val, regval = ads9.adi_ads9_reg_get(0x102, 0)
    print("reg102: ", hex(regval))

    # Scratch register
    returned_val = ads9.adi_ads9_reg_set(0x1000, 0x12345678)
    returned_val, regval = ads9.adi_ads9_reg_get(0x1000, 0)
    print("scratch reg: ", hex(regval))
    returned_val = ads9.adi_ads9_reg_set(0x1000, 0x87654321)
    returned_val, regval = ads9.adi_ads9_reg_get(0x1000, 0)
    print("scratch reg: ", hex(regval))

    # Pattern len
    ads9.adi_ads9_pattern_len_set(0x100)
    returned_val, regval = ads9.adi_ads9_reg_get(0x535, 0)
    print("Tx pat len reg: ", hex(regval))

    # ad9082
    return_val, chip_id = ad9082.adi_ad9082_device_chip_id_get(adi_cms_chip_id_t())
    print("ad9082 chip id (type, id, grade, rev): ", hex(chip_id.chip_type), hex(chip_id.prod_id), hex(chip_id.prod_grade), hex(chip_id.dev_revision))

    # hmc7044
    return_val, chip_id = hmc7044.adi_hmc7044_device_chip_id_get(adi_cms_chip_id_t())
    print("hmc7044 chip id (type, id, grade, rev): ", hex(chip_id.chip_type), hex(chip_id.prod_id), hex(chip_id.prod_grade), hex(chip_id.dev_revision))

    # Print API version
    ret_val, r0, r1, r2 = ad9082.adi_ad9082_device_api_revision_get(int(), int(), int())
    print("AD9082 API v{}.{}.{}".format(r0, r1, r2))

    # Print ADS9 FPGA image version
    ret_val, fpga_ver = ads9.adi_ads9_ver_get(int())
    ret_val, fpga_sw_ver = ads9.adi_ads9_sw_ver_get(int())
    print("ADS9 FPGA image v:{0:08X} sv:{1:08X}".format(fpga_ver, fpga_sw_ver))


    print("done")
