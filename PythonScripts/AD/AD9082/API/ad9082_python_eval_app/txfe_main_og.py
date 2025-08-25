#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

""" Example script for configuring the AD9082 evaluation board in various modes.

"""
#pylint: disable=import-error
from __future__ import print_function
import sys, getopt
import os
import numpy as np
import argparse
import settings
import matplotlib.pyplot as plt

from analysis import Analysis
from capture_deframer import CaptureDeframer
from vector_gen import VectorGen
from eval_board_target import *         # pylint: disable=unused-wildcard-import
from dpg import *                       # pylint: disable=unused-wildcard-import
from txfe_dpg_wrapper import *          # pylint: disable=unused-wildcard-import

from use_case_factory import UseCaseFactory
from device_config_factory import DeviceConfigFactory
from clock_config_factory import ClockConfigFactory

from ad9082_client import Ad9082Client
from ad9082_erpc import adi_ad9082_dac_channel_select_e, adi_ad9082_jesd_link_select_e, adi_cms_chip_id_t

from configure_full_chip_mode import ConfigureFullChipMode
from txfe_hmc_ads9_clocking import TxfeHmcAds9Clocking

def configure_platform(ipaddr):
    """ Configures the TxFE evaluation environment. Will exit if any errors.

        - Verifies MicroZed is present (ping)
        - Tests ssh connection
        - Gets handle to DPG downloader API
        - Loads and ADS9 FPGA image if one not already detected (of force on)
        - Copies the erpc server to the target MicroZed
        - Starts the remote erpc server on MicroZed allowing for 
          client/server communication w/ the TxFE AP

    """

    # Create object for communicating with the target board (e.g. MicroZed)
    eval_board_target = EvalBoardTarget(ipaddr)

    # Ping the device to test if it's reachable
    if (eval_board_target.wait_for_ping() != 0):
        print("Can't detect microzed. Exiting....")
        sys.exit(-1)

    # Test the connection
    # if (eval_board_target.test_connection() != 0):
    #     print "Can't establish target ssh connection. Exiting..."
    #     sys.exit(-1)

    # Create objects to control the ADS9 dpg device
    dpg = get_dpg_device()
    if not dpg:
        print("Can't find an ADS9 controller board. Exiting...")
        sys.exit(-2)

    txfe_dpg_wrapper = TxfeDpgWrapper(dpg)

    # Configure the FPGA image
    if (settings.always_load_fpga_image or not txfe_dpg_wrapper.is_fpga_image_loaded()):
        print("Loading FPGA image...")
        
        if (settings.eval_board_type == "ce"):
            fpga_image = settings.fpga_ce       # CE board image
        else:
            fpga_image = settings.fpga_pe       # PE board image

        err = dpg.configure_fpga_image(fpga_image, turn_on_fmc_power=True)
        
        if (err != 0):
            sys.exit(-3)

    print("FPGA version: {}".format(hex(txfe_dpg_wrapper.read_fpga_register(0x102))))      # FPGA image date

    # Start the erpc server on the target (Microzed)
    # This must be done after an ADS9 fpga image is configured.
    if (eval_board_target.start_erpc_server() != 0):
        print("Can't start erpc server on microzed. Exiting...")
        sys.exit(-4)

    return txfe_dpg_wrapper

def nco_test(use_case, n_loops=10, interactive=False):
    """ Sets device up for NCO test mode and sweeps coarse and fine NCOs
    """

    print("nco_test()")

    # # Link tuning
    # if (use_case.jrx_jesd.jesd_jesdv == 2):
    #     # Calibrate JRx for jesd204c > 15Gbps
    #     ad9082.adi_ad9082_device_spi_register_set(0x21c1, 0x18)
    # else:
    #     # JESD204B FPGA pre/post cursor
    #     for i in range(8):
    #         ads9.adi_ads9_reg_set(0x550 + i, 0x01011c)

    # Enable interactive plot
    plt.ion()  

    # Enable the JRx link
    # ad9082.adi_ad9082_jesd_rx_link_enable_set(adi_ad9082_jesd_link_select_e.AD9082_LINK_ALL, 1)
    # time.sleep(.1)

    # Reset jesd links
    dev_config.reset_jesd_link(use_case)

    # Display the jesd link status
    # print_link_status(use_case)

    return 0


def analog_loopback_test(use_case, do_init=True, n_loops=10, interactive=False):
    """ Sets up device for TX (dac) RX (adc) analog loopback.
    """
    print("analog_loopback_test()")
    
    # Generate some I/Q vectors for each virtual dac.
    vector_gen = VectorGen()
    iq = vector_gen.create_iq_vecs(use_case.jrx_jesd.jesd_m, 16384, use_case.dac_clk_hz/use_case.dac_total_interp, (use_case.dac_clk_hz/use_case.dac_total_interp)*0.4, use_case.jrx_jesd.jesd_np)

    # Download vectors into the ADS9 for playback.
    if (txfe_dpg.get_num_links() < 2):
        print("Downloading vector to ads9: Single Link")     
        txfe_dpg.download_vectors(iq)
    else:
        print("Downloading vector to ads9: Dual Link")     
        txfe_dpg.download_vectors_dual_link(iq, iq)

    # Enable interactive plot
    plt.ion()

    # Reset jesd links
    dev_config.reset_jesd_link(use_case)
    time.sleep(0.1)

    # Display the jesd link status
    print_link_status(use_case)

    # Specify num bytes to capture (64k blocks) (should be in api)
    bytes_to_read = 65536*10
    
    capture_more = True
    while (capture_more):
        print("Starting Capture:\n")
        for z in range(n_loops):

            print("\nloop: ", z)

            try:
                capture_data = txfe_dpg.capture(bytes_to_read)
            except Exception as e:
                print("Capture error exception: {}".format(e))
                print_link_status(use_case)
                break

            # Use CaptureDeframer object to separate capture data
            capture_deframer = CaptureDeframer()
            numLinks = 2 if use_case.jtx_jesd[0].jesd_duallink == 1 else 1
            c0, c1 = capture_deframer.get_samples(capture_data, num_links=numLinks, jesd_m_link0=use_case.jtx_jesd[0].jesd_m, jesd_m_link1= use_case.jtx_jesd[1].jesd_m if numLinks == 2 else use_case.jtx_jesd[0].jesd_m)
            
            print("Max/Min for I: {}/{}".format(max(c0[0]), min(c0[0])))
            print("Max/Min for Q: {}/{}".format(max(c0[1]), min(c0[1])))

            # Save capture on last iteration
            if (z == n_loops-1):
                print("Saving I/Q data files")
                np.savetxt(r'dataI.txt', c0[0], fmt='%d')   # Link0, virt conv 0
                np.savetxt(r'dataQ.txt', c0[1], fmt='%d')   # Link0, virt conv 1
            
            # Plot data from virtual converters
            plt.clf()
            n_points_to_plot = 8192
            t = range(n_points_to_plot)
            plt.ylim(-32768, 32768)
            if (numLinks < 2):
                plt.plot(t, c0[0][0:n_points_to_plot], 'g', t, c0[1][0:n_points_to_plot], 'r')
            else:
                plt.plot(t, c0[0][0:n_points_to_plot], 'g', t, c0[1][0:n_points_to_plot], 'r', t, c1[0][0:n_points_to_plot], 'b', t, c1[1][0:n_points_to_plot], 'c')
            plt.draw()
            plt.pause(.150)
        
        capture_more = False if not interactive else input("Capture more (y/n)? ") == "y"

    return 0

def real_data_test(use_case):

    vector_gen = VectorGen()
    iq = vector_gen.create_iq_vecs(use_case.jrx_jesd.jesd_m, 16384, use_case.dac_clk_hz/use_case.dac_total_interp, 100e6, use_case.jrx_jesd.jesd_np)

    # Download vectors into the ADS9 for playback.
    if (txfe_dpg.get_num_links() < 2):
        print("Downloading vector to ads9: Single Link")     
        txfe_dpg.download_vectors(iq)
    else:
        print("Downloading vector to ads9: Dual Link")     
        txfe_dpg.download_vectors_dual_link(iq, iq)

    # Reset jesd links
    dev_config.reset_jesd_link(use_case)
    time.sleep(1)

    # Display the jesd link status
    print_link_status(use_case)

    # Specify num bytes to capture (64k blocks) (should be in api)
    bytes_to_read = 65536*10
    print("Starting Capture:\n")
    try:
        capture_data = txfe_dpg.capture(bytes_to_read)
    except Exception as e:
        print("Capture error exception: {}".format(e))
        print_link_status(use_case)
        return -1
        
    # Use CaptureDeframer object to separate capture data
    capture_deframer = CaptureDeframer()
    numLinks = 2 if use_case.jtx_jesd[0].jesd_duallink == 1 else 1
    c0, c1 = capture_deframer.get_samples(capture_data, num_links=numLinks, jesd_m_link0=use_case.jtx_jesd[0].jesd_m, jesd_m_link1= use_case.jtx_jesd[1].jesd_m if numLinks == 2 else use_case.jtx_jesd[0].jesd_m)
    
    print("Max/Min for Data: {}/{}".format(max(c0[0]), min(c0[0])))

    print("Saving I/Q data files for Link 0 VC 0")
    np.savetxt(r'dataI.txt', c0[0], fmt='%d')   # Link0, virt conv 0, real data
    print("Captured %d words" %(len(capture_data)))
    
    return 0

def print_link_status(use_case):
    jrxl0 = ad9082.adi_ad9082_jesd_rx_link_status_get(1, int())[1]
    jrxl1 = ad9082.adi_ad9082_jesd_rx_link_status_get(2, int())[1]
    jtxl0 = ad9082.adi_ad9082_jesd_tx_link_status_get(1, int())[1]
    jtxl1 = ad9082.adi_ad9082_jesd_tx_link_status_get(2, int())[1]

    print("JRx (DAC) link0 status {}".format(hex(jrxl0)))
    if (use_case.jrx_jesd.jesd_duallink):
         print("JRx (DAC) link1 status {}".format(hex(jrxl1)))

    print("JTx (ADC) link0 status {}".format(hex(jtxl0)))
    if (use_case.jtx_jesd[0].jesd_duallink):
        print("JTx (ADC) link1 status {}".format(hex(jtxl1)))


    if (use_case.jrx_jesd.jesd_jesdv == 1):
        # JESD204B
        print("JRx (DAC) link0 is {}".format("UP!" if ((jrxl0 & 0xf) == 0xf) else "DOWN"))
        if (use_case.jrx_jesd.jesd_duallink):
            print("JRx (DAC) link1 is {}".format("UP!" if ((jrxl1 & 0xf) == 0xf) else "DOWN"))

        print("JTx (ADC) link0 is {}".format("UP!" if ((jtxl0 & 0xff) == 0x7d) else "DOWN"))
        if (use_case.jtx_jesd[0].jesd_duallink):
            print("JTx (ADC) link1 is {}".format("UP!" if ((jtxl1 & 0xff) == 0x7d) else "DOWN"))
    else:
        # JESD204C
        print("JRx (DAC) link0 is {}".format("UP!" if ((jrxl0 & 0xf00) == 0x600) else "DOWN"))
        if (use_case.jrx_jesd.jesd_duallink):
            print("JRx (DAC) link1 is {}".format("UP!" if ((jrxl1 & 0xf00) == 0x600) else "DOWN"))

        print("JTx (ADC) link0 is {}".format("UP!" if ((jtxl0 & 0x60) == 0x60) else "DOWN"))
        if (use_case.jtx_jesd[0].jesd_duallink):
            print("JTx (ADC) link1 is {}".format("UP!" if ((jtxl1 & 0x60) == 0x60) else "DOWN"))

def description_formatter(uc):
    """ Brief description of use case
    """
    return "{}: Fdac:{:06.2f}  Fadc:{}  Ref Clk:{:06.2f}  FPGA Ref Clk:{:06.2f} ".format(uc.name, uc.dac_clk_hz/1e6, uc.adc_clk_hz/1e6, uc.ref_clk_hz/1e6, uc.fpga_ref_clk_hz/1e6) + \
            "\nTx: Jesd mode: {}  LMFS: {}{}{}{}  {} link".format("C" if uc.jrx_jesd.jesd_jesdv == 2 else "B", uc.jrx_jesd.jesd_l, uc.jrx_jesd.jesd_m, uc.jrx_jesd.jesd_f, uc.jrx_jesd.jesd_s, "dual" if uc.jrx_jesd.jesd_duallink>0 else "single") + \
            "\nRx: Jesd mode: {}  LMFS: {}{}{}{}  {} link".format("C" if uc.jtx_jesd[0].jesd_jesdv == 2 else "B", uc.jtx_jesd[0].jesd_l, uc.jtx_jesd[0].jesd_m, uc.jtx_jesd[0].jesd_f, uc.jtx_jesd[0].jesd_s, "dual" if uc.jtx_jesd[0].jesd_duallink>0 else "single")

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--uc", help="use case number. See associated use_case_xx.py file.", type=int)
    parser.add_argument("--realonly", help="real data only", type=int, required=False, default=0)
    args = parser.parse_args()

    # Get a use case from the factory
    uc_factory = UseCaseFactory()
    if args.uc is not None:
        uc = uc_factory.create(args.uc, description_formatter)
    else:
        print("Selecting default use case #{}".format(3))
        uc = uc_factory.create(3, description_formatter)                # JESD204B at 7.33Gbps lane rate.
   
    # Print use case description
    print(uc.description())

    # Print settings configuration
    print("Settings: {}".format(settings.info()))

    # Configure the TxFE eval platform
    txfe_dpg = configure_platform(settings.ip_address)

    # Create handles to each device API
    ad9082_client = Ad9082Client(settings.ip_address)
    ads9, ad9082, hmc7044 = ad9082_client.get_devices()

    # Open the HMC7044
    hmc7044.adi_hmc7044_device_hw_open()

    # Open the ad9082
    ad9082.adi_ad9082_device_hw_open()

    # Print API version
    ret_val, r0, r1, r2 = ad9082.adi_ad9082_device_api_revision_get(int(), int(), int())
    print("AD9082 API v{}.{}.{}".format(r0, r1, r2))

    # Print ADS9 FPGA image version
    ret_val, fpga_ver = ads9.adi_ads9_ver_get(int())
    ret_val, fpga_sw_ver = ads9.adi_ads9_sw_ver_get(int())
    print("ADS9 FPGA image v:{0:08X} sv:{1:08X}".format(fpga_ver, fpga_sw_ver))

    # Get a clock configurator 
    clk_config_factory = ClockConfigFactory(ads9, ad9082, hmc7044)
    clk_config = clk_config_factory.create(uc)

    # Get a device configurator 
    dev_config_factory = DeviceConfigFactory(ad9082, ads9)
    dev_config = dev_config_factory.create(uc)
    
    # Initialize the ADS9 for external or HMC7044 clock
    print("Initializing clocks.")
    clk_config.configure(uc.ref_clk_hz, uc.fpga_ref_clk_hz, uc.jrx_jesd.jesd_jesdv)

    return_val, chip_id = hmc7044.adi_hmc7044_device_chip_id_get(adi_cms_chip_id_t())
    print("hmc7044 chip id (type, id, grade, rev): ", hex(chip_id.chip_type), 
        hex(chip_id.prod_id), hex(chip_id.prod_grade), hex(chip_id.dev_revision))
    print("Initializing clocks done.")

    print("Initializing device.")
    dev_config.configure(uc, pllEn=settings.enable_pll, board_type=settings.eval_board_type)

    return_val, chip_id = ad9082.adi_ad9082_device_chip_id_get(adi_cms_chip_id_t())
    print("ad9082 chip id (type, id, grade, rev): ", hex(chip_id.chip_type), hex(
        chip_id.prod_id), hex(chip_id.prod_grade), hex(chip_id.dev_revision))
    print("Initializing device done.")

    # This script is compatible with device revision 2 only
    if (chip_id.dev_revision != 3):
        print("***** This script is only compatible with device revision #2. This device rev is {} *****".format(hex(chip_id.dev_revision)))
        sys.exit(-5) 
    if (uc.type is "ncotest"):
        nco_test(uc, n_loops=0, interactive=True)
    elif (args.realonly):
        real_data_test(uc)
    else:
        analog_loopback_test(uc, True, n_loops=5, interactive=True)   

    print("done")
