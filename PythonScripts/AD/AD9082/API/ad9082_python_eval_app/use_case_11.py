#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from ad9082_client import Ad9082Client
from ad9082_erpc import adi_cms_jesd_param_t, adi_ad9082_dac_channel_select_e, adi_ad9082_adc_coarse_ddc_select_e, \
    adi_ad9082_adc_coarse_ddc_dcm_e,adi_ad9082_adc_fine_ddc_select_e, adi_ad9082_adc_fine_ddc_dcm_e, \
    adi_ad9082_jtx_conv_sel_t, adi_ad9082_adc_fine_ddc_converter_e

class UseCase11(object):
    """ Class for configuring Tx and Rx for use case #11 (JESD204C 16.22Gbps)

    """
    def __init__(self, description_formatter = None):
        self.description_formatter = description_formatter
        self.name = "UseCase11"
        self.type = "fullchip"

        ##### Clocks #####
        self.dac_clk_hz = 11796.48e6
        self.adc_clk_hz = 2949.12e6
        self.ref_clk_hz = 122.88e6
        self.fpga_ref_clk_hz = 245.76e6

        ##### DAC #####
        self.jrx_jesd = self._jrx_param()
        self.main_interp = 12
        self.chan_interp = 1
        self.dac_total_interp =  self.main_interp*self.chan_interp
        self.tx_dac_chan = [0x01, 0x02, 0x04, 0x08]
        self.txMainNCOShiftInHz = [0,0,0,0]   
        self.txChanNCOShiftInHz = [0, 0, 0, 0, 0, 0, 0, 0]
        self.tx_chan_gain = [0, 0, 0, 0, 0, 0, 0, 0]

        ##### ADC #####
        self.jtx_jesd = self._jtx_param()
        self.rx_cddc_select = adi_ad9082_adc_coarse_ddc_select_e.AD9082_ADC_CDDC_ALL
        self.rx_fddc_select = adi_ad9082_adc_fine_ddc_select_e.AD9082_ADC_FDDC_0 | adi_ad9082_adc_fine_ddc_select_e.AD9082_ADC_FDDC_1 | \
                              adi_ad9082_adc_fine_ddc_select_e.AD9082_ADC_FDDC_4 | adi_ad9082_adc_fine_ddc_select_e.AD9082_ADC_FDDC_5
        self.rx_cddc_shift = [366e6,    376e6,    386e6,  396e6]
        self.rx_fddc_shift = [0, 0, 0, 0, 0, 0, 0, 0]
        self.rx_cddc_dcm = [adi_ad9082_adc_coarse_ddc_dcm_e.AD9082_CDDC_DCM_3, adi_ad9082_adc_coarse_ddc_dcm_e.AD9082_CDDC_DCM_3, \
                            adi_ad9082_adc_coarse_ddc_dcm_e.AD9082_CDDC_DCM_3, adi_ad9082_adc_coarse_ddc_dcm_e.AD9082_CDDC_DCM_3]
        self.rx_fddc_dcm = [adi_ad9082_adc_fine_ddc_dcm_e.AD9082_FDDC_DCM_1, adi_ad9082_adc_fine_ddc_dcm_e.AD9082_FDDC_DCM_1, \
                            0, 0, \
                            adi_ad9082_adc_fine_ddc_dcm_e.AD9082_FDDC_DCM_1, adi_ad9082_adc_fine_ddc_dcm_e.AD9082_FDDC_DCM_1, \
                            0, 0 ]
        self.rx_cddc_c2r = [0, 0, 0, 0]
        self.rx_fddc_c2r = [0, 0, 0, 0, 0, 0, 0, 0]
        self.rx_chip_dcm = [3, 0]   # link0, link1 decimation ratio (set to lowest if different)
        self.rx_fddc_6db_gain_en = 0
        self.rx_cddc_6db_gain_en = 0
        
        # setup ad9082 jtx converter mapping 
        self.jtx_link0_converter_mapping = adi_ad9082_jtx_conv_sel_t()
        self.jtx_link0_converter_mapping.virtual_converter0_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_0_I
        self.jtx_link0_converter_mapping.virtual_converter1_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_0_Q
        self.jtx_link0_converter_mapping.virtual_converter2_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_1_I
        self.jtx_link0_converter_mapping.virtual_converter3_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_1_Q
        self.jtx_link0_converter_mapping.virtual_converter4_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_4_I
        self.jtx_link0_converter_mapping.virtual_converter5_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_4_Q
        self.jtx_link0_converter_mapping.virtual_converter6_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_5_I
        self.jtx_link0_converter_mapping.virtual_converter7_index = adi_ad9082_adc_fine_ddc_converter_e.AD9082_FDDC_5_Q
        self.jtx_link0_converter_mapping.virtual_converter8_index = 0
        self.jtx_link0_converter_mapping.virtual_converter9_index = 0
        self.jtx_link0_converter_mapping.virtual_convertera_index = 0
        self.jtx_link0_converter_mapping.virtual_converterb_index = 0
        self.jtx_link0_converter_mapping.virtual_converterc_index = 0
        self.jtx_link0_converter_mapping.virtual_converterd_index = 0
        self.jtx_link0_converter_mapping.virtual_convertere_index = 0
        self.jtx_link0_converter_mapping.virtual_converterf_index = 0

        self.jtx_link1_converter_mapping = adi_ad9082_jtx_conv_sel_t()
        self.jtx_link1_converter_mapping.virtual_converter0_index = 0
        self.jtx_link1_converter_mapping.virtual_converter1_index = 0
        self.jtx_link1_converter_mapping.virtual_converter2_index = 0
        self.jtx_link1_converter_mapping.virtual_converter3_index = 0
        self.jtx_link1_converter_mapping.virtual_converter4_index = 0
        self.jtx_link1_converter_mapping.virtual_converter5_index = 0
        self.jtx_link1_converter_mapping.virtual_converter6_index = 0
        self.jtx_link1_converter_mapping.virtual_converter7_index = 0
        self.jtx_link1_converter_mapping.virtual_converter8_index = 0
        self.jtx_link1_converter_mapping.virtual_converter9_index = 0
        self.jtx_link1_converter_mapping.virtual_convertera_index = 0
        self.jtx_link1_converter_mapping.virtual_converterb_index = 0
        self.jtx_link1_converter_mapping.virtual_converterc_index = 0
        self.jtx_link1_converter_mapping.virtual_converterd_index = 0
        self.jtx_link1_converter_mapping.virtual_convertere_index = 0
        self.jtx_link1_converter_mapping.virtual_converterf_index = 0
        
        self.jtx_converter_mapping = [self.jtx_link0_converter_mapping, self.jtx_link1_converter_mapping]
        
    def _jrx_param(self):
        """Setup jrx jesd params (DAC)
        """
        jrx_param = adi_cms_jesd_param_t()
        jrx_param.jesd_l = 8
        jrx_param.jesd_f = 2
        jrx_param.jesd_m = 8
        jrx_param.jesd_s = 1
        jrx_param.jesd_hd = 0
        jrx_param.jesd_k = 128
        jrx_param.jesd_n = 16
        jrx_param.jesd_np = 16
        jrx_param.jesd_cf = 0
        jrx_param.jesd_cs = 0
        jrx_param.jesd_bid = 0
        jrx_param.jesd_did = 0
        jrx_param.jesd_lid0 = 0
        jrx_param.jesd_subclass = 0
        jrx_param.jesd_scr = 1
        jrx_param.jesd_duallink = 0
        jrx_param.jesd_jesdv = 2
        jrx_param.jesd_mode_id = 15
        return jrx_param

    def _jtx_param(self):
        """Setup jtx jesd params (ADC)
        """
        jtx_param = adi_cms_jesd_param_t()
        jtx_param.jesd_l = 8
        jtx_param.jesd_f = 2
        jtx_param.jesd_m = 8
        jtx_param.jesd_s = 1
        jtx_param.jesd_hd = 0
        jtx_param.jesd_k = 128
        jtx_param.jesd_n = 12
        jtx_param.jesd_np = 16
        jtx_param.jesd_cf = 0
        jtx_param.jesd_cs = 0
        jtx_param.jesd_bid = 0
        jtx_param.jesd_did = 0
        jtx_param.jesd_lid0 = 0
        jtx_param.jesd_subclass = 0
        jtx_param.jesd_scr = 1
        jtx_param.jesd_duallink = 0
        jtx_param.jesd_jesdv = 2
        jtx_param.jesd_mode_id = 16
        return [jtx_param, jtx_param]   # Link0, Link1


    def description(self):
        """ Brief description of use case
        """
        if (self.description_formatter == None):
            return self.name
        else:
            return self.description_formatter(self)