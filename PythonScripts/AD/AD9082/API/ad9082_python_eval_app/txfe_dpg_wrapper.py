#! python3
#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import sys
import clr     
import dpg
import settings
import time

dpgdir32 = settings.lib_folder
sys.path.append(dpgdir32)
clr.AddReference("System")
clr.AddReference('AnalogDevices.TxfeSupport.Ads9Lite')
clr.AddReference('AnalogDevices.TxfeSupport.Common')
clr.AddReference('AnalogDevices.TxfeSupport.TxFESupport')
from System import UInt32, Int32                                                
from AnalogDevices.TxfeSupport.TxFESupport import RemoteEvalApi   # pylint: disable=import-error

class TxfeDpgWrapper(object):
    """Wrapper class for accessing DPG .net methods of the RemoteEvalAPI 
    """

    def __init__(self, dpg):
        """Constructor
        """
        self.dpg = dpg
        self.ad9986 = RemoteEvalApi(dpg.net)
        self.jesd204_params0 = self.ad9986.LinkParams0
        self.jesd204_params1 = self.ad9986.LinkParams1
    
    def download_vectors(self, vecs, start_addr=0x80000000):
        print('@download_vectors to addr ', hex(start_addr))
        self.ad9986.DownloadVectors(UInt32(start_addr), vecs)
        print('@download_vectors done.')

    def download_vectors_dual_link(self, vecs0, vecs1, start_addr=0x80000000):
        print('@download_vectors (dual link) to addr ', hex(start_addr))
        self.ad9986.DownloadVectors(UInt32(start_addr), vecs0, vecs1)
        print('@download_vectors (dual link) done.')
    
    def transport(self, vecs, jesd204_params):
        return self.ad9986.Transport(vecs, jesd204_params)
    
    def play(self):
        self.ad9986.TransmitStart()
        self.ad9986.Play(True)      # True to force start FPGA transmitter
        
    def stop(self):
        self.ad9986.Stop()
        self.ad9986.TransmitStop()
    
    def get_jesd204_link_params(self, link=0):
        return self.jesd204_params0 if link == 0 else self.jesd204_params1  
          
    def get_num_links(self):
        return self.ad9986.NumLinks

    def set_num_links(self, val):
        self.ad9986.NumLinks = val
        
    def get_subclass(self):
        return self.ad9986.Subclass

    def set_subclass(self, val):
        self.ad9986.Subclass = val
                    
    def is_fpga_image_loaded(self):
        return self.ad9986.IsFpgaImageLoaded
    
    def get_fpga_image_file_name(self):
        return self.ad9986.FpgaImageName
    
    def get_sync_state(self, link=0):
        return self.ad9986.SyncState0 if link == 0 else self.ad9986.SyncState1
    
    def read_fpga_register(self, reg):
        val = self.ad9986.Ad9986Jesd204Tx._FpgaReadRegister(reg)
        return val
    
    def write_fpga_register(self, reg, val):
        self.ad9986.Ad9986Jesd204Tx._FpgaWriteRegister(reg, val)

    def read_capture_data(self, num_32bit_words=1024, start_capture=True):
        return self.ad9986.CaptureRead(num_32bit_words, start_capture)
    
    def capture(self, bytes_to_read):
        """ Start a capture and return raw data.

        Parameters
        ----------
        bytes_to_read : int
            Number of capture bytes to read. Must be multiple of 64k.       
        """

        # Set num bytes (in 64k blocks) to capture 
        self.write_fpga_register(0x143, bytes_to_read/65536)  
       
        # Kick off a capture
        self.write_fpga_register(0x140, 0x02)  # start capture

        cap_done = False
        to_cnt = 0
        to_word = 4
        print("wait for cap")
        while (not cap_done):
            cap_done = self.read_fpga_register(0x1040) & 0x01
            if (cap_done):
                break
            time.sleep(.1)
            to_cnt += 1
            if (to_cnt > 10):
                break

        if (not cap_done):
            print("wait for cap - timeout")
            raise Exception("Capture timeout")
        else:
            print("wait for cap - done")

        # Check that the fifo has data to read. If this is not done,
        # then captures will timeout and sometimes hang the USB.
        ok_to_read = False
        to_cnt = 0
        while (not ok_to_read):
            fifo_read_ready = self.read_fpga_register(0x14a)
            print('fifo_read_ready 0x{0:0{1}X}'.format(fifo_read_ready,4))
            ok_to_read = (fifo_read_ready & 0x0008) != 0
            time.sleep(.1)
            to_cnt += 1
            if (to_cnt > 10):
                print("no capture to read - timeout error")
                return 0
        capture_data = self.read_capture_data(bytes_to_read/to_word, False)   # Don't initiate the capture
        
        return capture_data