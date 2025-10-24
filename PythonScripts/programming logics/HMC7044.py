# Copyright (c) 2017 by ADI. This code is the confidential and
# proprietary property of ADI and being distributed with the
# aggreement of 20150909-HMC704x-CTSLA excluding the 3rd party codes.
# ---------------------------------------------------------------------
# FTDI Class and Functions used for Communication over USB
print("Setting Up...")

import ftd2xx
from time import sleep
import logging

#SCK = 0x01
#SD0 = 0x02
#SDI = 0x04
SEN = 0x08
#
#HW_RSTB = 0x10
#EN_TCXO = 0x20
#RF_SWITCH = 0x40
#EXT_TRIG_AD7 = 0x80
#
FT_MODE_RESET = 0
FT_MODE_ASYBITBANG = 1
FT_MODE_MPSSE = 2

MPSSE_CMD_ReadDataBitsLowByte = 0x81
MPSSE_CMD_WriteDataBitsLowByte = 0x80
MPSSE_CMD_WriteDataBitsHiByte = 0x82
MPSSE_CMD_SetClkDivider = 0x86
MPSSE_CMD_ClkDataBytesOut_H11 = 0x11
MPSSE_CMD_ClkDataBytesInOut_H31 = 0x31
#
#BIT_MASK_PORT_AD = SEN + SD0 + SCK + HW_RSTB + EN_TCXO + RF_SWITCH + EXT_TRIG_AD7
#BIT_MASK_PORT_BD = 0xFF

def long_long_getbyte(ms, ls, byte_index):
    return (ls >> (byte_index*8)) & 0xFF

def AvailDeviceSerialList():
        devNumber = ftd2xx.createDeviceInfoList()
        devSerial = []
        for i in range(devNumber):
            dev = ftd2xx.getDeviceInfoDetail(i)
            print( dev['description'])
            if not (int(dev['flags']) % 2) and ('DLP2232M A' in dev['description'] or 'DLP232M A' in dev['description'] or 'DLP-2232H A' in dev['description']):
                devSerial.append(dev['serial'])
                logging.debug('serial %s is added' % dev['serial'])
        return devSerial

class ftdi():
    def __init__(self,serial):
        
        PortA = serial
        PortB = serial[0:len(serial)-1]+'B'
        
        self.PortA = ftd2xx.openEx(str(PortA))  
        self.PortA.resetDevice()
        logging.debug('FTDI PortA is reseted')
        
        self.PortA.setLatencyTimer(1)
        self.PortA.setTimeouts(5000,5000)
        self.PortA.setUSBParameters(4096,4096)
        self.PortA.setBitMode(0xFF,2) # MPSSE MODE
#        data = '%c' % 0x84
#        data += '%c' % 0xAB
#        self.PortA.write(data)
#        sleep(.1)
#        bytesToRead = self.PortA.getQueueStatus() # Sending a False Data Sequence
#        if bytesToRead != 2:
#            return False
        
        # Set clock dividier
        # MPSSE clk algorithm: 
        # if divide by 5 is disabled
        #   CLK = 60/((1 + clk_divider)*2)
        # else
        #   CLK = 12/((1 + clk_divider)*2)
        data = '%c' % MPSSE_CMD_SetClkDivider
        data += '%c' %0x3B
        data += '%c' %0x00
        self.PortA.write(data)
        
        data  = '%c' % 0x80 # MPSSE_CMD_WriteDataBitsLowByte
        data += '%c' % 0x08
        data += '%c' % 0xFF
        self.PortA.write(data)
        
#        
        GLB_portAC_pins_state = 0x00
        BIT_MASK_PORT_AC = 0x03
        
        data  = "%c" % MPSSE_CMD_WriteDataBitsHiByte
        data += "%c" % GLB_portAC_pins_state
        data += "%c" % BIT_MASK_PORT_AC
        
        data  = '%c' % 0x82 # MPSSE_CMD_WriteDataBitsHiByte 
        data += '%c' % 0x00
        data += '%c' % 0x03
        self.PortA.write(data)
        
        self.PortB = ftd2xx.openEx(str(PortB))
        self.PortB.setBitMode(0,0)
        logging.debug('FTDI PortB is reseted')
        self.PortB.setLatencyTimer(1)
        self.PortB.setTimeouts(5000,5000)
        self.PortB.setUSBParameters(4096,4096) ###
        self.PortB.setBitMode(0xFF,FT_MODE_ASYBITBANG)
        
        logging.info('FTDI has opened')
    def write(self,reg_addr,reg_data):
        data = '%c' % MPSSE_CMD_ReadDataBitsLowByte
        self.PortA.write(data)
        pin_state = ord(self.PortA.read(1))
        
        total_bytes = 3 
        bit_stream_hi = 0
        bit_stream_low = reg_addr << 8
        bit_stream_low = bit_stream_low | reg_data
        
        data  = '%c' % 0x80
        data += '%c' % (pin_state & ((~SEN)&0xF))
        data += '%c' % 0xFF
        
        data += '%c' % MPSSE_CMD_ClkDataBytesOut_H11
        data += '%c' % (total_bytes-1)
        data += '%c' % 0
        
        for i in range(total_bytes-1, -1 ,-1):
            data += '%c' % long_long_getbyte(bit_stream_hi, bit_stream_low, i)
        
        data += '%c' % 0x80
        data += '%c' % (pin_state | SEN)
        data += '%c' % 0xFF
        
        self.PortA.write(data)
        
    def read(self,reg_addr):
        total_bytes = 0
        data = '%c' % MPSSE_CMD_ReadDataBitsLowByte
        self.PortA.write(data)
        pin_state = ord(self.PortA.read(1))
        
        w1w0 = ( reg_addr>>13 ) & 3
        n_bytes = 3 + w1w0
        total_bytes += n_bytes
        bit_stream_hi = 0
        bit_stream_low = (reg_addr | 0x8000) << 8
                
        data  = '%c' % 0x80
        data += '%c' % (pin_state & ((~SEN)&0xF))
        data += '%c' % 0xFF
        
        data += '%c' % MPSSE_CMD_ClkDataBytesInOut_H31
        data += '%c' % (total_bytes-1)
        data += '%c' % 0
        
        for i in range(total_bytes-1, -1 ,-1):
            data += '%c' % long_long_getbyte(bit_stream_hi, bit_stream_low, i)
        
        data += '%c' % 0x80
        data += '%c' % (pin_state | SEN)
        data += '%c' % 0xFF
        
        self.PortA.write(data)
        reg_data = self.PortA.read(3)
        return ord(reg_data[2])
        
    def close(self):
        self.PortA.close()
        self.PortB.close()
        logging.debug('Connection closed')
        
    def scan(self):
        MPSSE_CMD_WriteDataBitsHiByte = 0x82
        GLB_portAC_pins_state = 0x00
        BIT_MASK_PORT_AC = 0x03
        
        data  = "%c" % MPSSE_CMD_WriteDataBitsHiByte
        data += "%c" % GLB_portAC_pins_state
        data += "%c" % BIT_MASK_PORT_AC
        
        self.PortA.write(data)
        
        logging.debug('scan mode is on')
# ---------------------------------------------------------------------
# Setting Up Power Supply
# import ADI_USB

# print("Setting up power supply...")

# s1 = ADI_USB.Keithley2230('0x05E6::0x2230::802901012766910023')    #BPS1 

# s1.V1 = 5.00 # sets the voltage on channel 1
# s1.I1 = 0.20 # sets the current on channel 1

# s1.V2 = 3.45  # sets the voltage on channel 2
# s1.I2 = 0.850 # sets the current on channel 2

# s1.Enabled = True  # turns on the power supply

# def power_cycle():
#     s1.Enabled = False
#     sleep(2.0) # wait 2s before turning on
#     s1.Enabled = True
# # ---------------------------------------------------------------------
# Hard and Soft Register Resets for HMC7044
import pandas as pd

print("Configuring HMC7044...")

df = pd.read_csv("C:\Git\Rad-Effects-Test-Software\HMC7044_init_config_values.csv")

reg_num = range(0, 339)
CONFIG_VALS = []
for i in reg_num:
    value = int(df[str(hex(reg_num[i]))])
    CONFIG_VALS.append(value)
    
def config():
    for n in range(0, 339):
        device.write(n, CONFIG_VALS[n])
    print("Device configured based on given configuration file.")
    
def spi_reset():
    device.write(0x0, 0x1)
    device.write(0x0, 0x0)
# ---------------------------------------------------------------------
# Initiliazing Communication over FTDI
usb_serial_a = "1284N678A" # Change this to specify USB serial (Version A)
device = ftdi(usb_serial_a)

print("USB found. Initializing communication...")

config()

run_time = input("How many minutes would you like to gather data? ")
# ---------------------------------------------------------------------
# Initializing DataFrame
import datetime as dt
import pandas as pd

print("Initializing DataFrame...")

start_time = dt.datetime.now()
start_time = (start_time.hour * 60) + start_time.minute # calculates specific minute in a day
current_time = start_time # initializing current_time

reg_num = range(0, 339) # creates vector of register indexes from 0 to 338 to
                        # read from HMC7044's registers
# unused_reg = [0x6, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x20, 0x29, 0x2A, 0x31, 0x32, 0x33, 0x33,
              # 0x34, 0x35, 0x36, 0x37, 0x46, 0x47, 0x48, 0x49, 0x50, 0x51, 0x52, 0x53, 0x54,
              # 0x5E, 0x65, 0x78, 0x79, 0x7A, 0x7F, 0x87, 0x8C, 0x8D, 0x90, 0x96, 0x97, 0x98,
              # 0x99, 0x9A, 0x9D, 0x9E, 0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9, 0xAA, 0xAB,
              # 0XAC, 0xAD, 0xAE, 0xAF, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xD1,
              # 0XE5, 0xF9, 0x103, 0x100, 0x127, 0x121, 0x12B, 0x135, 0x13F, 0x149]
unused_reg = range(120, 146)
unused_reg = sorted(unused_reg, reverse=True)
config_copy = CONFIG_VALS[:]
for index in unused_reg:
    del reg_num[index]      # removes registers from reg_num that are not critical to functionality
    del config_copy[index]  # removes registers from config_copy that are not critical to functionality;
                            # to be used in checking if register values change from configuration
                      
column_list = ["Date", "Time", "ms", "Current", "Voltage"]
for i in reg_num:
    column_list.append(str(hex(i))) # adds all registers to the columns of the dateframe
    
df = pd.DataFrame(columns = column_list) # initializing dataframe for .csv


# ---------------------------------------------------------------------
# Gathering Data
print("Gathering Data...")

s_event = 0 # initialization of single event counter
reset_trigger = 0
while (current_time - start_time) < run_time: # stop loop if 
    current_time = dt.datetime.now() # getting start time of one iteration of reading registers
    date = current_time.strftime("%m-%d-%Y")
    time = current_time.strftime("%H:%M:%S")
    ms = str(int(current_time.strftime("%f")) / 1000)
    current_time = (current_time.hour * 60) + current_time.minute
    
    current = 7  #round(s1.I2, 5) # measures current on channel 2
    voltage = 8  #round(s1.V2, 3) # measures voltage on channel 2
    
    #if (current > 0.8): # if current exceeds 800mA, then power cycle
    #    power_cycle()
    
    values = [date, time, ms, current, voltage]
    for i in range(len(reg_num)):
        value = device.read(reg_num[i]) # reads value from register
        values.append(value)          # appends value of register to list of all register values
        if value != config_copy[i]:   # check to see if a register has changed
            s_event = s_event + 1
            reset_trigger = reset_trigger + 1
            s_time = dt.datetime.now()
            s_time = s_time.strftime("%H:%M:%S.%f")
            if (reset_trigger == 15):
                print("Resetting the device...")
                reset_trigger = 0 # set the reset_trigger back to zero
                spi_reset()
                config()
                
    df.loc[len(df.index)] = values   # appends register values to dataframe
# ---------------------------------------------------------------------
# Saving Data
print("Saving Data...")

fname = input("What would you like to name the file (do NOT add the .csv extenstion)? ")
fname = r'C:\Users\tdecker\ADAR3000_SEE_TEST\HMC7044_DATA\\' + fname + '.csv'
df.to_csv(fname) 

print("Data Saved.")
print("A total of %d single events occured." % (s_event))
# ---------------------------------------------------------------------

