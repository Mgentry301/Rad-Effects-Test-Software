#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function
from ad9082_client import Ad9082Client
from ad9082_erpc import adi_ad9082_jesd_link_select_e, adi_ad9082_adc_coarse_ddc_select_e, adi_ad9082_adc_fine_ddc_select_e, adi_ad9082_reset_e
from ad9082_erpc import adi_ad9082_adc_nyquist_zone_e
import time

class ConfigureFullChipMode(object):
    """ Class for configuring Tx and Rx for full chip mode (Tx and Rx)

    """
    def __init__(self, ad9082, ads9):
        self.ad9082 = ad9082
        self.ads9 = ads9

    def configure(self, uc, pllEn = 1, board_type = "ce"):    
              
        # Configure ADS9 jtx and jrx jesd parameters
        self.ads9.adi_ads9_config_jesd(uc.jtx_jesd, uc.jrx_jesd)
        self.ads9.adi_ads9_capture_size_set(0x20)
        self.ads9.adi_ads9_pattern_addr_set(0x80000000)
        self.ads9.adi_ads9_pattern_len_set(0x8000)

        self.ads9.adi_ads9_reg_set(0x540, 1) ## transmit_skip_data = 1
        self.ads9.adi_ads9_reg_set(0x106, 0x000) ## skip_rx_link_init = 0
        self.ads9.adi_ads9_reg_set(0x947, 2) ## bidir_start = 1
        self.ads9.adi_ads9_reg_set(0x106, 0x400) ## skip_rx_link_init = 1

        if (uc.jrx_jesd.jesd_l > 0) and (uc.jrx_jesd.jesd_jesdv == 2) and ((uc.fpga_ref_clk_hz * 66) > 16e9):
            self.ads9.adi_ads9_jesd_tx_lane_driver_config(0xff, 0x0, 0x0, 0x14)
        else:
            self.ads9.adi_ads9_jesd_tx_lane_driver_config(0xff, 0x4, 0x4, 0x1c)

        # Device reset and init
        self.ad9082.adi_ad9082_device_reset(adi_ad9082_reset_e.AD9082_SOFT_RESET)  # pylint: disable=undefined-variable
        self.ad9082.adi_ad9082_device_init()

        # Configure clocks
        ref_clk_hz = uc.ref_clk_hz if pllEn==1 else uc.dac_clk_hz     # for direct clock set ref_clk equal to dac_clk
        err = self.ad9082.adi_ad9082_device_clk_config_set(uc.dac_clk_hz, uc.adc_clk_hz, ref_clk_hz)
        if (err != 0):
            print("adi_ad9082_device_clk_config_set() returned error {0}".format(err))
            exit(err)

        err, pll_lock = self.ad9082.adi_ad9082_device_clk_pll_lock_status_get(int())
        if (pll_lock == 0x3):
            print("txfe PLL locked")
        if (err != 0):
            print("adi_ad9082_device_clk_pll_lock_status_get() returned error {0}".format(err))
        
        # Startup Tx (DAC)
        self.ad9082.adi_ad9082_device_startup_tx(uc.main_interp, uc.chan_interp, uc.tx_dac_chan, uc.txMainNCOShiftInHz, uc.txChanNCOShiftInHz, uc.jrx_jesd)

        # Set DAC channel gain
        tx_chan_gains = [0,0,0,0,0,0,0,0]
        for i in range(len(uc.tx_chan_gain)):
            tx_chan_gains[i] = pow(2,11) * pow(10, uc.tx_chan_gain[i]/20.0)
        self.ad9082.adi_ad9082_dac_duc_nco_gains_set(tx_chan_gains)

        # Startup Rx (ADC)
        self.ad9082.adi_ad9082_device_startup_rx(uc.rx_cddc_select, uc.rx_fddc_select, uc.rx_cddc_shift, uc.rx_fddc_shift,
                uc.rx_cddc_dcm, uc.rx_fddc_dcm, uc.rx_cddc_c2r, uc.rx_fddc_c2r, uc.jtx_jesd, uc.jtx_converter_mapping)

        # Set Rx coarse and fine ddc +6db gain
        self.ad9082.adi_ad9082_adc_ddc_coarse_gain_set(adi_ad9082_adc_coarse_ddc_select_e.AD9082_ADC_CDDC_ALL, uc.rx_cddc_6db_gain_en)
        self.ad9082.adi_ad9082_adc_ddc_fine_gain_set(adi_ad9082_adc_fine_ddc_select_e.AD9082_ADC_FDDC_ALL, uc.rx_fddc_6db_gain_en)

        # Enable the JRx and JTx jesd links
        self.ad9082.adi_ad9082_jesd_tx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL if (uc.jtx_jesd[0].jesd_duallink > 0) else adi_ad9082_jesd_link_select_e.AD9082_LINK_0, 1)
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL if (uc.jrx_jesd.jesd_duallink > 0) else adi_ad9082_jesd_link_select_e.AD9082_LINK_0, 1)

        #Oneshot sync, subclass 0 supported
        self.ad9082.adi_ad9082_jesd_sysref_input_mode_set(1 if (uc.jrx_jesd.jesd_subclass > 0) else 0, 0 if (uc.jrx_jesd.jesd_subclass > 0) else 1, 1)
        self.ad9082.adi_ad9082_jesd_oneshot_sync(1 if (uc.jrx_jesd.jesd_subclass > 0) else 0)
        
        # Check JESD PLL Status
        pll_lock_status = 0x00
        err, pll_lock_status = self.ad9082.adi_ad9082_jesd_pll_lock_status_get(int())
        if (err != 0):
            print("adi_ad9082_jesd_pll_lock_status_get() returned error {0}".format(err))
            exit(err)
        print("JESD PLL lock status:", "Locked" if pll_lock_status == 0x01 else "Not Locked")

    def configure_jesd_rx_lane_mapping(self):
        # jrx link lane mapping
        jrx_link0_logiclane_mapping = [0, 1, 2, 3, 4, 5, 6, 7]
        jrx_link1_logiclane_mapping = [4, 5, 6, 7, 0, 1, 2, 3]
        self.ad9082.adi_ad9082_jesd_rx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_0, jrx_link0_logiclane_mapping)
        self.ad9082.adi_ad9082_jesd_rx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_1, jrx_link1_logiclane_mapping)

    def configure_jesd_tx_lane_mapping(self, uc, board_type):
        # jtx Lane mapping
        if (board_type == "ce"):
            # CE board
            jtx_link0_logiclane_mapping_ce_brd = [6, 4, 3, 2, 1, 0, 7, 5]
            jtx_link1_logiclane_mapping_ce_brd = [2, 0, 7, 7, 7, 7, 3, 1]

            # Set logical lane mapping and lane ids
            self.ad9082.adi_ad9082_jesd_tx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_0, jtx_link0_logiclane_mapping_ce_brd)
            self.ad9082.adi_ad9082_jesd_tx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_1, jtx_link1_logiclane_mapping_ce_brd)
        else:
            # PE board
            jtx_link0_logiclane_mapping_pe_brd = [0, 1, 2, 3, 4, 5, 6, 7]
            jtx_link1_logiclane_mapping_pe_brd = [4, 5, 6, 7, 0, 1, 2, 3]

            # Set logical lane mapping and lane ids
            self.ad9082.adi_ad9082_jesd_tx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_0, jtx_link0_logiclane_mapping_pe_brd)
            self.ad9082.adi_ad9082_jesd_tx_lanes_xbar_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_1, jtx_link1_logiclane_mapping_pe_brd)

    def reset_jesd_link(self, uc):
        """ Reset the JESD links. 
        """
        self.ads9.adi_ads9_reg_set(0x106, 0)  # do not skip rx link init
        self.ads9.adi_ads9_reg_set(0x947, 2)  # bidir start
        time.sleep(.0001)
        self.ads9.adi_ads9_reg_set(0x106, 0x400)  # skip rx link init
        
        self.ads9.adi_ads9_reg_set(0x537, 4)  # gt_tx_ptn_play_stop
        
        # Disable jesd link
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL, 0)
        time.sleep(.1)

        self.ads9.adi_ads9_reg_set(0x537, 1)  # gt_tx_ptn_play_start
        time.sleep(.1)
        
        # Enable jesd link
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL
                                                       if(uc.jrx_jesd.jesd_duallink>0) else
                                                       adi_ad9082_jesd_link_select_e.AD9082_LINK_0 , 1)
        time.sleep(.1)
        
        # Run JESD RX Calibrations if JESD204C and JESD Lane Rate > 16Gbps
        if (uc.jrx_jesd.jesd_l > 0  and  uc.jrx_jesd.jesd_jesdv == 2 and  (uc.fpga_ref_clk_hz *66) > 16000000000):
            self.ad9082.adi_ad9082_jesd_rx_calibrate_204c(1, 0x00, 0 )

        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(0x3, 0)
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL if (uc.jrx_jesd.jesd_duallink > 0) else adi_ad9082_jesd_link_select_e.AD9082_LINK_0, 1)
        
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(0x3, 0)
        self.ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL if (uc.jrx_jesd.jesd_duallink > 0) else adi_ad9082_jesd_link_select_e.AD9082_LINK_0, 1)

