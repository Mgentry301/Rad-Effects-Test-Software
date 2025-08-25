#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import numpy as np

class VectorGen(object):
    """ Class for generating simple Tx vectors
    """

    def __init__(self):
        pass

    def create_iq_vecs(self, jesd_m, n_samples_per_converter, data_rate, tone_freq, nbits):
        """ Generates I/Q tone vectors

        Parameters
        ----------
        jesd_m: num of virtual dacs in jesd config
        n_samples_per_converter: number of samples in a vector (per virt dac)
        data_rate: Fdac/Total interpolation
        tone_freq:

        Returns array of alternating I/Q tone vectors for each jesd virtual dac
        """
        fs = data_rate      # data_rate is Fdac/Interpolation
        ft = tone_freq      # ft is tone freq
        n = n_samples_per_converter
        m = n*ft/fs
        m = int(m) | 1
        ft = (fs*m)/n
        print("ft= ", ft/1e6)
        x = np.arange(n)
        amp = (1 << (nbits-1))-1 # 32767 for 16 bits
        ivec = np.cos(2*np.pi*m*x/n)*amp
        qvec = np.sin(2*np.pi*m*x/n)*amp 

        # jesd M is 4, I/Q data on two channels
        if (jesd_m == 1):
            iq = [ivec]
        elif (jesd_m == 2):
            iq = [ivec, qvec]
        elif (jesd_m == 4):
            iq = [ivec, qvec, ivec, qvec]
        elif (jesd_m == 8):
            iq = [ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec]
        elif (jesd_m == 16):
            iq = [ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec, ivec, qvec]
        else:
            raise Exception("Tx Jesd M value not supported. ", jesd_m)

        return iq
