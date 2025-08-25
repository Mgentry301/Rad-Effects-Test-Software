#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

from __future__ import print_function
from configure_full_chip_mode import ConfigureFullChipMode
from configure_nco_test_mode import ConfigureNcoTestMode

class DeviceConfigFactory(object):
    """Factory class for creating device configuration objects
    """

    def __init__(self, ad9082, ads9):
        """Constructor
        """
        self.ad9082 = ad9082
        self.ads9 = ads9

    def create(self, uc):
        if (uc.type == "fullchip"):
            return ConfigureFullChipMode(self.ad9082, self.ads9)
        if (uc.type == "ncotest"):
            return ConfigureNcoTestMode(self.ad9082, self.ads9)
        else:
            raise Exception("Unknown use case type.")