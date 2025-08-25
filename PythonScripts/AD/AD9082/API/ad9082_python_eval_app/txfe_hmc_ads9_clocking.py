#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function
import time
from ad9082_client import Ad9082Client
from ad9082_erpc import adi_hmc7044_op_ch_e, adi_hmc7044_clk_in_e, adi_cms_error_e, adi_hmc7044_ip_buffer_settings_e

class TxfeHmcAds9Clocking(object):
    """Wrapper class supporting the HMC7044 clock, ADS9 for the TxFE evaluation board
    """

    def __init__(self, ads9, hmc7044, eval_board_type= "ce", hmc7044_crystal_freq = 122.88e6):
        """Constructor
        """
        self.ads9 = ads9
        self.hmc7044 = hmc7044
        self.hmc7044_crystal_freq = hmc7044_crystal_freq
        self.eval_board_type = eval_board_type

    def configure(self, dev_ref, fpga_ref, jesdv):
        """ Configure the HMC7044 clock chip for the use case
        """
        print("Configure hmc7044")
        
        # ADS9 ref clock from FMC board
        self.ads9.adi_ads9_mgt_ref_clk_select_set(1)
        self.ads9.adi_ads9_gbl_clk_select_set(1)
        
        self.hmc7044.adi_hmc7044_device_init()
        self.hmc7044.adi_hmc7044_device_reset(0)
        self.hmc7044.adi_hmc7044_input_reference_set(0, adi_hmc7044_ip_buffer_settings_e.IPBUFFER_INTERNAL_100_OHM_EN | adi_hmc7044_ip_buffer_settings_e.IPBUFFER_AC_COUPLED_MODE_EN, 1)
        self.hmc7044.adi_hmc7044_input_reference_set(1, adi_hmc7044_ip_buffer_settings_e.IPBUFFER_INTERNAL_100_OHM_EN | adi_hmc7044_ip_buffer_settings_e.IPBUFFER_AC_COUPLED_MODE_EN, 1)
        self.hmc7044.adi_hmc7044_input_reference_los_config_set(7, 0, 0)
        self.hmc7044.adi_hmc7044_vco_sel_set(1, 1)
        self.hmc7044.adi_hmc7044_output_sync_config_set(3, 0, 1, 1)    # clkout3 as async mode
        self.hmc7044.adi_hmc7044_output_sync_config_set(13, 0, 1, 1)   # clkout13 as async mode
        self.hmc7044.adi_hmc7044_output_multi_slip_config_set(13, 0, 0)

        hmc_output_clk_hz = self._get_hmc_clock_config(dev_ref=dev_ref, fpga_ref=fpga_ref, jesdv=jesdv)
        hmc_output_ch = self._get_hmc_clock_mask()
        hmc_priority = [0, 1, 2, 3]
        self.hmc7044.adi_hmc7044_clk_config(adi_hmc7044_clk_in_e.HMC7044_CLK_IN_0,
            hmc_priority, self.hmc7044_crystal_freq, self.hmc7044_crystal_freq, hmc_output_ch, hmc_output_clk_hz)
        self.hmc7044.adi_hmc7044_reg_update()
        time.sleep(.1)

        self._setAds9FpgaRefClickDividers(fpga_ref, jesdv)

        # Check hmc pll lock status
        return_val, hmc_pll_locked = self.hmc7044.adi_hmc7044_device_pll_lock_status_get(int())
        if (return_val != adi_cms_error_e.API_CMS_ERROR_OK): raise Exception("Exception from: adi_hmc7044_device_pll_lock_status_get(). return_val=", return_val)
        print("HMC7044: PLL is", "locked" if hmc_pll_locked else "NOT locked")

    def _get_hmc_clock_config(self, dev_ref, fpga_ref, jesdv=0):
        """ Determine HMC clock configuration. Depends on Eval board type and JESD type.

            fpga_ref assumed to be calculated with /66.
        """
        hmc_out_clk_hz = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 ]
        if (self.eval_board_type == "ce"):
            # CE
            if (jesdv < 2): # 204B
                hmc_out_clk_hz[0] = fpga_ref / 2         
                hmc_out_clk_hz[2] = dev_ref      
                hmc_out_clk_hz[3] = fpga_ref / 16         
                hmc_out_clk_hz[6] = fpga_ref / 2         
                hmc_out_clk_hz[8] = fpga_ref        
                hmc_out_clk_hz[10] = fpga_ref / 2        
                hmc_out_clk_hz[12] = fpga_ref         
                hmc_out_clk_hz[13] = fpga_ref / 16         
            else:           #204C
                hmc_out_clk_hz[0] = fpga_ref       
                hmc_out_clk_hz[2] = dev_ref      
                hmc_out_clk_hz[3] = fpga_ref / 32         
                hmc_out_clk_hz[6] = fpga_ref        
                hmc_out_clk_hz[8] = fpga_ref*2 if (fpga_ref * 66 < 8.3e9) else fpga_ref        
                hmc_out_clk_hz[10] = fpga_ref         
                hmc_out_clk_hz[12] = fpga_ref*2 if (fpga_ref * 66 < 8.3e9) else fpga_ref         
                hmc_out_clk_hz[13] = fpga_ref / 32
        else: 
            # PE
            if (jesdv < 2): # 204B
                hmc_out_clk_hz[0] = fpga_ref / 2         
                hmc_out_clk_hz[2] = dev_ref      
                hmc_out_clk_hz[3] = fpga_ref / 16         
                hmc_out_clk_hz[6] = fpga_ref / 2         
                hmc_out_clk_hz[8] = fpga_ref        
                hmc_out_clk_hz[10] = fpga_ref         
                hmc_out_clk_hz[12] = fpga_ref         
                hmc_out_clk_hz[13] = fpga_ref / 16         
            else:           #204C
                hmc_out_clk_hz[0] = fpga_ref       
                hmc_out_clk_hz[2] = dev_ref      
                hmc_out_clk_hz[3] = fpga_ref / 32         
                hmc_out_clk_hz[6] = fpga_ref        
                hmc_out_clk_hz[8] = fpga_ref*2 if (fpga_ref * 66 < 8.3e9) else fpga_ref        
                hmc_out_clk_hz[10] = fpga_ref*2 if (fpga_ref * 66 < 8.3e9) else fpga_ref         
                hmc_out_clk_hz[12] = fpga_ref         
                hmc_out_clk_hz[13] = fpga_ref / 32

        return hmc_out_clk_hz

    def _get_hmc_clock_mask(self):
        hmc_output_ch = adi_hmc7044_op_ch_e.HMC7044_OP_CH_0 | adi_hmc7044_op_ch_e.HMC7044_OP_CH_2 | \
                        adi_hmc7044_op_ch_e.HMC7044_OP_CH_3 | adi_hmc7044_op_ch_e.HMC7044_OP_CH_6 | \
                        adi_hmc7044_op_ch_e.HMC7044_OP_CH_8 | adi_hmc7044_op_ch_e.HMC7044_OP_CH_10 | \
                        adi_hmc7044_op_ch_e.HMC7044_OP_CH_12 | adi_hmc7044_op_ch_e.HMC7044_OP_CH_13

        return hmc_output_ch

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

if __name__ == '__main__':
    obj = TxfeHmcAds9Clocking(None, None)
    print(hex(obj._get_hmc_clock_mask()))
