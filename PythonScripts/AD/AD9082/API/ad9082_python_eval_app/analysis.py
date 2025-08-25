#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import sys
import math
import time
import operator
import matplotlib.pyplot as plt
import scipy.signal as sg
import scipy as sp
import numpy as np

class Analysis(object):
    ### Class for plotting capture data and fft
    ###
    res  = 16
    t    = None
    F    = None
    data = None    
    SdB  = None    

    def __init__(self, res):
        self.res = res
        plt.rcParams.update({'font.size': 8})

    def load(self, fs, data):
        self.t = np.linspace(0, len(data) * 1e6/fs, len(data)) # t unit is uS
        #w = sg.blackman(data.shape[0], False)
        #w = sg.blackmanharris(data.shape[0], False) # Blackman-Harris
        w = sg.chebwin(data.shape[0], 200, False)    # Dolph-Chebyshev
        w *= w.shape[0]/np.sum(w)
        S = sp.fft(data*w, data.shape[0]*4)
        S = S/math.pow(2, self.res-1)/len(S)*4
        self.F    = np.linspace(0, fs, len(S))
        self.SdB  = 20 * sp.log10(sp.absolute(S))
        self.data = data

    def plot(self, i, j, size, link, complex):
        if size < 2:
            plt.subplot(2, 1, (1 + j))
            plt.plot(self.t, self.data.real, 'g')
            if complex > 0:
                plt.plot(self.t, self.data.imag, 'r')
            plt.ylim(-32768, 32768)
            #plt.ylabel('data')
            plt.title('Link%d.Converter%d'%(link, i))
            plt.grid()
            plt.subplot(2, 1, (2 + j))
            plt.plot(self.F, self.SdB, 'b')
            plt.ylim(-180, 0)
            #plt.ylabel('dB')
            plt.grid()
            return
        if size < 3:
            plt.subplot(2, 2, (1 + j))
            plt.plot(self.t, self.data.real, 'g')
            if complex > 0:
                plt.plot(self.t, self.data.imag, 'r')
            plt.ylim(-32768, 32768)
            #plt.ylabel('data')
            plt.title('Link%d.Converter%d'%(link, i))
            plt.grid()
            plt.subplot(2, 2, (3 + j))
            plt.plot(self.F, self.SdB, 'b')
            plt.ylim(-180, 0)
            #plt.ylabel('dB')
            plt.grid()
            return
        if size < 5:
            plt.subplot(4, 2, (1 + j) if (j < 2) else (3 + j))
            plt.plot(self.t, self.data.real, 'g')
            if complex > 0:
                plt.plot(self.t, self.data.imag, 'r')
            plt.ylim(-32768, 32768)
            #plt.ylabel('data')            
            plt.title('Link%d.Converter%d'%(link, i))
            plt.grid()
            plt.subplot(4, 2, (3 + j) if (j < 2) else (5 + j))            
            plt.plot(self.F, self.SdB, 'b')
            plt.ylim(-180, 0)
            #plt.ylabel('dB')
            plt.grid()
            return
        if size < 9:
            plt.subplot(4, 4, (1 + j) if (j < 4) else (5 + j))
            plt.plot(self.t, self.data.real, 'g')
            if complex > 0:
                plt.plot(self.t, self.data.imag, 'r')
            plt.ylim(-32768, 32768)
            #plt.ylabel('data')            
            plt.title('Link%d.Converter%d'%(link, i))
            plt.grid()
            plt.subplot(4, 4, (5 + j) if (j < 4) else (9 + j))
            plt.plot(self.F, self.SdB, 'b')
            plt.ylim(-180, 0)
            #plt.ylabel('dB')
            plt.grid()
            return

    def show(self):
        # mng = plt.get_current_fig_manager()
        # mng.window.showMaximized()
        plt.show()
