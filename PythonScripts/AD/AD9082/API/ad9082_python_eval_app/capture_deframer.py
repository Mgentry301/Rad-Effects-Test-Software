#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
import numpy as np
import matplotlib.pyplot as plt


class CaptureDeframer(object):
    """ Class for extracting converter data from ADS9 capture memory
    """

    def __init__(self):
        pass

    def create_capture_data_sim(self, jesd_m, n_samples_per_converter):
        """
        Creates simulated ADS9 capture data for testing. This is how data resides in memory for single link.
        Each 32-bit word is encoded as follows:
            CCCCddddCCCCdddd

            where CCCC is the converter and dddd is data in a count pattern.
        """
        capture_data = np.zeros(jesd_m*16/2, dtype=np.uint32)

        idx = 0
        for s in range(n_samples_per_converter):
            for m in range(jesd_m):
                if (idx % 2 == 0):
                    capture_data[idx/2] = (m << 12) + (s & 0x0fff)
                else:
                    capture_data[idx/2] += ((m << 12) + (s & 0x0fff)) << 16
                idx += 1

        # for i in range(len(capture_data)):
        #     print '0x{0:0{1}X}'.format(capture_data[i],8)

        return capture_data

    def get_samples(self, input32, num_links, jesd_m_link0, jesd_m_link1=0):
        """
        Extract the ADS9 formatted sample data based on jesd link parameters

        Returns array of converter sample arrays for each link.
        """
        
        if (num_links == 1):
            samples_per_conv = (2*len(input32))//jesd_m_link0
            c0 = np.empty([jesd_m_link0, samples_per_conv], dtype=np.int16)
            c1 = None
            for c in range(jesd_m_link0):
                for s in range(samples_per_conv):
                    w16 = (s * jesd_m_link0) + (c % jesd_m_link0)
                    w32 = w16 / 2
                    c0[c][s] = input32[w32] & 0x0000FFFF if (w16 % 2 == 0) else input32[w32] >> 16
        else:
            samples_per_conv_link0 = (len(input32))//jesd_m_link0
            samples_per_conv_link1 = (len(input32))//jesd_m_link1
            c0 = np.empty([jesd_m_link0, samples_per_conv_link0], dtype=np.int16)
            c1 = np.empty([jesd_m_link1, samples_per_conv_link1], dtype=np.int16)

            for c in range(jesd_m_link0):
                for s in range(samples_per_conv_link0):
                    w16 = (s * jesd_m_link0) + (c % jesd_m_link0)
                    w32 = w16
                    c0[c][s] = input32[w32] & 0x0000FFFF
           
            for c in range(jesd_m_link1):
                for s in range(samples_per_conv_link1):
                    w16 = (s * jesd_m_link1) + (c % jesd_m_link1)
                    w32 = w16
                    c1[c][s] = input32[w32] >> 16

        return c0, c1


if __name__ == '__main__':

    # Create class instance
    capture_deframer = CaptureDeframer()

    capture_data = capture_deframer.create_capture_data_sim(
        jesd_m=4, n_samples_per_converter=16)

    for i in range(len(capture_data)):
        print('0x{0:0{1}X}'.format(capture_data[i], 8))

    np.set_printoptions(formatter={'int':hex})
    print(capture_data)

    link0 = capture_deframer.get_samples(capture_data, jesd_m=4,  num_links=1)

    print(link0)
    print(type(link0))
    print(link0[0].shape)
    for i in range(len(link0)):
        if link0[i] is not None:
            plt.plot(link0[i])
            plt.ylabel('some numbers from link{}'.format(i))
            plt.show()
