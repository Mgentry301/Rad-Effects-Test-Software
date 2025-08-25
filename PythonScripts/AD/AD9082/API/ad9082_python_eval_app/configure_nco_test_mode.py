#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function
from ad9082_client import Ad9082Client
from ad9082_erpc import *
import numpy as np
import time
import math

class ConfigureNcoTestMode(object):
    """ Class for configuring NCO tes mode

    """
    def __init__(self, ad9082, ads9):
        self.ad9082 = ad9082
        self.ads9 = ads9

    def configure(self, uc, pllEn = 1, board_type = "ce"):    

        # Device reset and init
        self.ad9082.adi_ad9082_device_reset(adi_ad9082_reset_e.AD9082_SOFT_RESET)  # pylint: disable=undefined-variable
        self.ad9082.adi_ad9082_device_init()

        # Configure clocks
        ref_clk_hz = uc.ref_clk_hz if pllEn==1 else uc.dac_clk_hz     # for direct clock set ref_clk equal to dac_clk
        err = self.ad9082.adi_ad9082_device_clk_config_set(uc.dac_clk_hz, uc.adc_clk_hz, ref_clk_hz)
        if (err != 0):
            print("adi_ad9082_device_clk_config_set() returned error {0}".format(err))
            exit(err)

        # Start up nco test mode
        main_interp = uc.main_interp
        chan_interp = uc.chan_interp
        tx_dac_chan_xbar = uc.tx_dac_chan
        txMainNCOShiftInHz = uc.txMainNCOShiftInHz
        txChanNCOShiftInHz = uc.txChanNCOShiftInHz
        jesd_param = uc.jrx_jesd
        dc_offset = np.int16(math.pow(10, ((0 + 20 * math.log10((0x5a82>>1))) / 20)))

        #backoff fullscale (0x5a82) if combining channels to prevent overage
        err = self.ad9082.adi_ad9082_device_startup_nco_test_mode(main_interp, chan_interp, tx_dac_chan_xbar,
            txMainNCOShiftInHz, txChanNCOShiftInHz, jesd_param, dc_offset)[0]  
        if (err != 0):
            print("adi_ad9082_device_startup_nco_test_mode() returned error {0}".format(err))
            exit(err)        
        

        # Configure the jesd lane mapping and IDs for Jtx 
        self.configure_jesd_tx_lane_mapping(uc, board_type)

        # Configure ADS9 jtx and jrx jesd parameters
        # self.ads9.adi_ads9_config_jesd(uc.jtx_jesd, uc.jrx_jesd)
        self.ad9082.adi_ad9082_jesd_oneshot_sync(0)


    # def set_main_nco_freq(self, main_nco=1.0e9):
    #     """Set the main (coarse) NCO freq
    #     """
    #     self.ad9082.adi_ad9082_dac_duc_nco_enable_set(1, 0, 1)
    #     dac_freq = self.dac_clk_hz
    #     ftw_val = np.int64(round((main_nco / dac_freq) * pow(2, 48)))
    #     print("ftw_val ", hex(ftw_val))
    #     self.ad9082.adi_ad9082_dac_duc_nco_ftw_set(1, 0, ftw_val, 0, 0)


    # def set_chan_nco_freq(self, chan_nco=100.0e6):
    #     """Set the channel (fine) NCO freq
    #     """
    #     self.ad9082.adi_ad9082_dac_duc_nco_enable_set(1, 0, 1)          #dacs, channels, enable
    #     dac_freq = self.dac_clk_hz
    #     ftw_val = np.int64(round((chan_nco * self.main_interp / dac_freq) * pow(2, 48)))
    #     print("ftw_val ", hex(ftw_val))
    #     self.ad9082.adi_ad9082_dac_duc_nco_ftw_set(0, 1, ftw_val, 0, 0) #dacs, chan, ftw, ...
        
    def configure_jesd_rx_lane_mapping(self):
        # N/A for nco test mode
        pass

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
        self.ad9082.adi_ad9082_device_spi_register_set(0x596, 0)
        time.sleep(.1)

        self.ads9.adi_ads9_reg_set(0x143, 1)  # cap size lsb
        self.ads9.adi_ads9_reg_set(0x144, 0)  # cap size msb

        # Start playback
        self.ads9.adi_ads9_reg_set(0x540, 0x1)  # tranmit_skip_data (outputs all zero samples)
        self.ads9.adi_ads9_reg_set(0x106, 0)  # do not skip rx link init
        self.ads9.adi_ads9_reg_set(0x947, 2)  # bidir start
        self.ads9.adi_ads9_reg_set(0x106, 0x400)  # skip rx link init
        
        self.ads9.adi_ads9_reg_set(0x537, 4)  # gt_tx_ptn_play_stop
        
        # Disable jesd link
        self.ad9082.adi_ad9082_device_spi_register_set(0x596, 0)
        time.sleep(.1)

        self.ads9.adi_ads9_reg_set(0x537, 1)  # gt_tx_ptn_play_start
        time.sleep(.1)
        
        # Enable jesd link
        self.ad9082.adi_ad9082_device_spi_register_set(0x596, 0x0b if (uc.jrx_jesd.jesd_duallink>0) else 0x01)
        time.sleep(.1)