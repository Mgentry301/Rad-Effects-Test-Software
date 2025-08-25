#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

from __future__ import print_function
from txfe_hmc_ads9_clocking import TxfeHmcAds9Clocking
from txfe_ext_ads9_clocking import TxfeExtAds9Clocking
import settings

class ClockConfigFactory(object):
    """Factory class for creating platform clock configuration objects
    """

    def __init__(self, ads9, ad9082, hmc7044):
        """Constructor
        """
        self.ads9 = ads9
        self.ad9082 = ad9082
        self.hmc7044 = hmc7044

    def create(self, uc):
        if (settings.use_7044 and settings.enable_pll):
            return TxfeHmcAds9Clocking(self.ads9, self.hmc7044, settings.eval_board_type, settings.hmc7044_crystal_freq)
        else:
            return TxfeExtAds9Clocking(self.ads9, settings.eval_board_type)
