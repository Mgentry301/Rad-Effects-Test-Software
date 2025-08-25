#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function

class TxfeExtAds9Clocking(object):
    """Wrapper class supporting direct external clock on ADS9 for the TxFE evaluation board
    """

    def __init__(self, ads9, eval_board_type= "ce"):
        """Constructor
        """
        self.ads9 = ads9
        self.eval_board_type = eval_board_type

    def configure(self, dev_ref, fpga_ref, jesdv):
        """ Configure for external direct clock
        """
        print("Configure external clock")
        
        # ADS9 ref clock external (sma connector)
        self.ads9.adi_ads9_ad9528_vcxo_select_set(0)
        self.ads9.adi_ads9_mgt_ref_clk_select_set(0)
        self.ads9.adi_ads9_gbl_clk_select_set(0)

        self._setAds9FpgaRefClickDividers(fpga_ref, jesdv)

    def _setAds9FpgaRefClickDividers(self, fpga_ref, jesdv):
        """ Set the ADS9 ref clock dividers.

            fpga_ref assumed to be calculated with /66.
        """
        # Determine optimal ADS9 fpga jesd204 reference clock
        ads9_jrx_line_rate_div = 0   # from device (ADC)
        ads9_jtx_line_rate_div = 0   # to device (DAC)

        if (jesdv == 2):
            # JESD204C
            slr = fpga_ref * 66
            if (slr < 8.3e9):
                # Fpga ref clock is doubled for slower lane rates, change divider
                ads9_jrx_line_rate_div = 0x0101
                ads9_jtx_line_rate_div = 0x0101
                fpga_ref *= 2
        else:
            # JESD204B
            slr = fpga_ref * 20

        self.ads9.adi_ads9_reg_set(0x10c, ads9_jrx_line_rate_div) 
        self.ads9.adi_ads9_reg_set(0x50c, ads9_jtx_line_rate_div)
        
        print("Serial Lane Rate is {} Gbps".format(slr/1e6))
        print("FPGA ref clock {} MHz".format(fpga_ref/1e6))