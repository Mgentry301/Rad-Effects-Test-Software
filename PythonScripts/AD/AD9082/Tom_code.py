'''
Created on Apr 4, 2018

@author: DACdev
'''
import os
import re
import sys
import CSV
import time
import instr
import traceback
import numpy as np
import zipfile as zf
import comm.vecgen as gen
import bin.logger as logger
from Software.txfe.EP.ProductModule.TxFE import TxFE
from Software.txfe.EP.ProductModule.r0.txfe_temp_sense_r0 import Temp_sense


# Instrument classes
Meter34401A = instr.agilent34401A
PXA = instr.pxa
SMA = instr.sma

# Define Spectrum Analyzer address
pxa = PXA(addr=19, reset=False)                                                                   

#for quick reset
LOG = logger.initLog(__name__)
PAT = re.compile('w\((.*), ?(.*)\)\\n')

WAIT_PAT = re.compile('.*wait\((.*)\).*')

read_p = '.*read\((.*)\)\\n'
READ_PAT = re.compile(read_p)

# GLOBALS
SPI_COUNT = 0
LINK_ERROR = 0
RESET_ERROR = 0
FILE_EXTENSION = '.csv'


class CsvObject:
    def __init__(self, filepath):
        self._filepath = filepath

    @property
    def exists(self):
        return os.path.exists(self.filepath)

    @property
    def filepath(self):
        return self._filepath

    def write_dictionary(self, write_dict):
        """ Write a dictionary to the file

        Args:
            write_dict (dict): Dictionary to write to the file.
        """

        # Pull out the column names and values
        columns = sorted(write_dict.keys())
        values = [write_dict[c] for c in columns]

        # If the file doesn't exist, create it
        if not self.exists:
            # Initialize the write string
            write_string = ''

            # Add the columns
            for c in columns:
                write_string += '%s,' % c

            # Remove the last comma and add a newline
            write_string = write_string[:-1] + '\n'

            # Add the data
            for v in values:
                write_string += '%f,' % v

            # Write the string without the last comma and add a newline
            with open(self.filepath, 'w') as f:
                f.write('%s\n' % write_string[:-1])

        # If the file exists, append to it
        else:
            # Initialize the write string
            write_string = ''

            # Add the data
            for v in values:
                write_string += '%f,' % v

            # Write the string without the last comma and add a newline
            with open(self.filepath, 'a') as f:
                # Go to the end of the file
                f.seek(0, 2)

                # Add the new data
                f.write('%s\n' % write_string[:-1])
        return

    
def main(filename=None):
    '''
    Inputs:
        filename: String - Fully qualified name of datafile
    Returns:
        N/A
    Use:
        Main function of test code
    '''
    # Main function of the test. Can/should call other functions
    # Place to initialize instruments and boards

    global SPI_COUNT, LINK_ERROR, RESET_ERROR
    SPI_COUNT = 0
    LINK_ERROR = 0
    RESET_ERROR = 0
    
    # Define path and filenames for all datafiles saved to C:\Data\AD9082
    if filename is None:
        # Initialize the file path
        filename_reg_check = r'C:\Data\AD9082\11_7_2019\AD9082_register_check_run13.csv'

        # Loop until a filename does NOT exist
        while os.path.exists(filename_reg_check):
            # Search for a run number
            match = re.compile(f'[_\- ]*run[_\- ]*\d+', re.I).findall(filename_reg_check)[0]

            # If a match is found
            if match:
                # Search for the number and increment it
                run_number = int(re.compile(r'\d+').findall(match)[0]) + 1

                # Get the filename without the extension or the original number
                fn = os.path.splitext(filename_reg_check.replace(match, ''))[0]

                # Build a new filename with the incremented number
                filename_reg_check = '%s_run%d%s' % (fn, run_number, FILE_EXTENSION)
    else:
        # If the filename was given, use it
        filename_reg_check = filename

    Device = "AD9082"
    Rad_Level = "3MeV"
    Serial_Number = "2"
    Notes = " Run 13"

    # Meter used for temp sense
    dmm = Meter34401A(22)
    
    brd_ref_clk = 122.88e6
    ref_clk = 0
    fdac = 122.88e6 * 48    #6e9 TDs old code
    fadc = fdac / 2.

    tx_mode = 213

    txsetup = 'jesd' 
    subclass = 0
    main_shift = [1000e6, 1000e6, 1000e6, 1000e6] # dac0 was 900e6, switch back after nco testing #900e6 was 1000e6
    
    ch_shift = [0e6, 0e6, 0e6, 0e6, 0e6, 0e6, 0e6, 0e6]
    amplitude = [0]  # , -12, -12, -12, -12]
    dac0_chan = [0]    
    dac1_chan = [0]  #1
    dac2_chan = [0]   #2
    dac3_chan = [0]  #3
    scrambling = True  #False
    skip_cal = False #True
    shuffle = True

    clk = SMA(addr=28)
    clk.setFreq(ref_clk if ref_clk else fdac)
    clk.setLvl(3 if ref_clk else 10)
    clk.setEnable(enable=True)

    brd = TxFE(config='tx', brd_ref_clk=brd_ref_clk, ref_clk=ref_clk, fdac=fdac, fadc=fadc, tx_mode=tx_mode, 
               txsetup=txsetup, subclass=subclass, main_shift=main_shift, ch_shift=ch_shift, amplitude=amplitude, 
               scrambling=scrambling, skip_cal=skip_cal, shuffle=shuffle, dacs=[0, 1, 2, 3],
               dac0_chan=dac0_chan, dac1_chan=dac1_chan, dac2_chan=dac2_chan, dac3_chan=dac3_chan,
               use_clk_chip=False)

    clk.setCsynLvl(lvl=3)
    clk.setCsynEnabled(enable=True)
    brd.startDPT(clk.setCsynFreq)

    # Program scratch registers to monitor Soft reset
    Set_scratch_regs(brd)
    
    # Do some vecgen and vector loading below. Tx side should be ready to receive data.
    length = 2**14
    fout = 1e6
    cvec = gen.csine(fout=fout, fs=fdac/brd.tx.interp, bits=brd.tx.np, length=length, binary=False)
    
    brd.tx.loadPattern(data_arr=cvec)

    brd.tx.loadPattern(data_arr=cvec)

    tempTest = Temp_sense(txfe=brd, meter=dmm)
    temp = tempTest.measureTemp(dacadc=[0])

    LOG.info('Done!')

    pxaView(pxa, fcenter=1e9)
    while True:
        # Loop until we break out
        try:
            td = measFund(1e9, pxa)

            # Check scratch registers and log data
            Register_Checker(brd, filename_reg_check, Device, Rad_Level, Serial_Number, Notes, td, cvec, temp)

            # Check to see if we should break out
            if (SPI_COUNT + LINK_ERROR + RESET_ERROR) >= 150:
                break
        except:
            print ('x')
            

def Set_scratch_regs(brd):
    # Program Scratch register to FE
    brd.bfWrite('reg8_scratch_0', 0xfe)
    brd.bfWrite('reg8_scratch_1', 0xfe)
    brd.bfWrite('reg8_scratch_2', 0xfe)
    brd.bfWrite('reg8_scratch_3', 0xfe)
    return


def jesd_reset(brd):    
    brd.bfWrite('jrx_dl_204b_enable',1)  #('link_en', 1)
    time.sleep(0.25)
    return


def Register_Checker(brd, filename, Device, Rad_Level, Serial_Number, Notes, td, cvec, temp):
    global SPI_COUNT
    global RESET_ERROR
    global LINK_ERROR

    csvf = CsvObject(filename)
    # SPI_e = False
    reset = False

    # The following 3 statements are a cleaner way to get the register values that you wanted to read into a
    # dictionary. Something similar can be done with a list of register addresses instead of register names.
    registers_to_read = [
        'reg8_scratch_0',
        'reg8_scratch_1',
        'reg8_scratch_2',
        'reg8_scratch_3',
        'up_status',
        'jrx_dl_204b_fs_lost'
        'jrx_dl_204b_enable',
        'up_clocks_off',
        'chnl_auto_cg_en',
        'jtx_link_204c_sel',
        'core_status',
        'boot_done',
        'dll_internal_clk_div',
        'msb_rotation_spd',
        'spi_main_nco_rst_en',
        'xtensa_exception_exccause',
        'hcg_exception',
        'gpio_error_status',
        'd_impala_cal_control',
        'd_pd_vco_div'
    ]

    # Build a dictionary of register reads with the keys being the register names
    register_values = {r: brd.bfRead(r) for r in registers_to_read}

    # This read was different than the rest, so I did it separately and added it to the dictionary
    register_values['reset_reg'] = brd.fx3.SpiRead(0x00)

    current_time = time.strftime("%H:%M:%S")
    current_date = time.strftime("%d/%m/%Y")

    # Determine if reset required
    scratch_regs = ('reg_scratch0', 'reg_scratch1', 'reg_scratch2', 'reg_scratch3')
    if all(register_values[key] == 0 for key in scratch_regs) or (register_values['reset_reg'] == 0 and td < -5):
        SPI_COUNT += 1
        reset = True

    if register_values['jrx_dl_204b_enable'] == 0:                                #JESD link upset
        print ('Link Error')
        LINK_ERROR += 1

    if (td < -5) or reset:                        #lost DAC output or SPI reset - requires full reset
        RESET_ERROR += 1
        LOG.info('Long restart Channel Pwr Reset')
        toggle_rstb(brd)
        long_restart(brd, cvec)

        Set_scratch_regs(brd)    #resets scratch registers in case any bits upset

    else:
        if register_values['jrx_dl_204b_enable'] == 0:
            LOG.info('Long restart')
            jesd_reset(brd)
            toggle_rstb(brd)
            long_restart(brd, cvec)

            print ("jesd")

    # Check if tone is back, and test NCO only mode if not?
    reg_001_postreset = brd.bfRead('jrx_dl_204b_fs_lost') #  reads back 0 when ok # brd.bfRead('link_en')
    reg_002_postreset = brd.bfRead('jrx_dl_204b_enable')
    td_postreset = measFund(1e9, pxa)

    if (reg_001_postreset == 0x01) and (reg_002_postreset == 0x00) and (td_postreset < -5):
        print ("Lockout Reset!")
        td_postreset2 = measFund(1e9, pxa)
        LOG.info('Long restart')
        toggle_rstb(brd)
        long_restart(brd, cvec)
        print (td_postreset2)
        Set_scratch_regs(brd)

    dict_result = {
        "Device": Device,
        "Rad_Level": Rad_Level,
        "Serial_Number": Serial_Number,
        "Date": current_date,
        "Time": current_time,
        "SPI Reset": SPI_COUNT,
        "Notes": Notes,
        "reg_scratch0": register_values['reg8_scratch_0'],
        "reg_scratch1": register_values['reg8_scratch_1'],
        "reg_scratch2": register_values['reg8_scratch_2'],
        "reg_scratch3": register_values['reg8_scratch_3'],
        "UP Status": register_values['up_status'],
        "JESD Link": LINK_ERROR,
        "Full Reset Count": RESET_ERROR,
        "Fundamental": td,
        "UP clocks Off": register_values['up_clocks_off'],
        "reg_001": register_values['jrx_dl_204b_fs_lost'],
        "JESD Enable": register_values['jrx_dl_204b_enable'],
        "temp": temp,
        "Chnl_Auto_CG_En": register_values['chnl_auto_cg_en'],
        "JESD_204C_En": register_values['jtx_link_204c_sel'],
        "Core_Status": register_values['core_status'],
        "Boot_Done": register_values['boot_done'],
        "DLL_Internal_ClkDiv": register_values['dll_internal_clk_div'],
        "MSB_Rotation_Speed": register_values['msb_rotation_spd'],
        "SPI_Main_NCO_Reset": register_values['spi_main_nco_rst_en'],
        "Xtensa_Exception_Error": register_values['xtensa_exception_exccause'],
        "HCG_Exception": register_values['hcg_exception'],
        "GPIO_Error_Status": register_values['gpio_error_status'],
        "D_Impala_Cal_Control": register_values['d_impala_cal_control'],
        "D_PD_VCO_Divider": register_values['d_pd_vco_div']
    }

    # Write the file line
    csvf.write_dictionary(dict_result)
    return


def quick_restart(brd, cvec):
    filename = r'C:\Projects\MxFE_HTOL_Debug_preConv.txt'
    
    with open(filename, mode='r') as f:
        lines = f.readlines()
     
    add_val_ls = getWrites(lines)
    
    t0 = time.time()    
    writeLines(brd, add_val_ls)
    t1= time.time()

    brd.tx.loadPattern(data_arr=cvec)
    #KCHONG 11-3 ~ had sefi where all dacs were powered down, quick reset didn't seem to bring them back, trying this to see if it works??
#     brd.bfWrite('dac_pd0', 0)
    t2 = time.time()
    print ('reg writes took %f seconds' % (t1-t0))
    print ('reg writes + vector loading took %f seconds' % (t2-t0))
    return


def long_restart(brd, cvec):
    # -- variables for startup debug --
    brd_ref_clk = 122.88e6
    ref_clk = 0
    fdac = 122.88e6 * 48    #6e9 TDs old code
    fadc = fdac / 2.
       
    tx_mode = 213

    txsetup = 'jesd' 
    subclass = 0
    main_shift = [900e6, 1000e6, 1000e6, 1000e6]  #900e6 was 1000e6
    
    ch_shift = [0e6, 0e6, 0e6, 0e6, 0e6, 0e6, 0e6, 0e6]
    amplitude = [0]  # , -12, -12, -12, -12]
    dac0_chan = [0]    
    dac1_chan = [0]  #1
    dac2_chan = [0]   #2
    dac3_chan = [0]  #3
    scrambling = True  #False
    skip_cal = False #True
    shuffle = True
    
    brd.startup(config='tx', brd_ref_clk=brd_ref_clk, ref_clk=ref_clk, fdac=fdac, fadc=fadc, tx_mode=tx_mode, 
                txsetup=txsetup, subclass=subclass, main_shift=main_shift, ch_shift=ch_shift, amplitude=amplitude, 
                scrambling=scrambling, skip_cal=skip_cal, shuffle=shuffle, dacs=[0, 1, 2, 3],
                dac0_chan=dac0_chan, dac1_chan=dac1_chan, dac2_chan=dac2_chan, dac3_chan=dac3_chan,
                use_clk_chip=False)
    brd.tx.loadPattern(cvec)
    return

  
def toggle_rstb(brd):
    brd.bfWriteFpga('dut_rstb', 0)
    print ('dut_rstb = %d' % brd.bfReadFpga('dut_rstb'))
  
    brd.bfWriteFpga('dut_rstb', 1)
    print ('dut_rstb = %d' % brd.bfReadFpga('dut_rstb'))
    return
    
    
def pxaInit(pxa, mtype='fund'):
    if 'fund' in mtype.lower():
        pxa.reset()
        pxa.setDetector()
        pxa.setAttenuation(atten=24)
        pxa.setAverage(enable=True, count=2)
        pxa.setSpan(1e3)
        pxa.setBW(30)
    elif 'nsd' in mtype.lower():
        '''Write the configuration values to the PXA. This function is typically called by runTest()'''
        # Channel Power Settings
        # Start Channel Power Mode
        pxa.reset()
        pxa.setDetector()
        # pxa.setAttenuation(atten=32)
        pxa.write('INST:SEL SA')
        pxa.write('CONF:CHP')
        pxa.write('CONF:CHP:NDEF')
        pxa.write('INIT:CONT OFF')
        
        # Write User Settings
        pxa.write('CHP:BAND:INT %f' % (100e3))
        pxa.write('CHP:FREQ:SPAN %f' % (2e6))
        pxa.write('CHP:BAND %f' % (10e3))
        pxa.write('CHP:AVER:COUN 5')
        pxa.write('DISP:CHP:VIEW:WIND:TRAC:Y:RLEV %f' % (-100))
        pxa.write('POW:ATT 0')
        
        # Turn on PreAmp and Noise Correction
        pxa.write('POW:GAIN ON')
        pxa.write('POW:GAIN:BAND FULL')
        pxa.write('CORR:NOIS:FLO ON')
    elif 'noise' in mtype.lower():
        pxa.reset()
        pxa.setDetector(mode='AVER')
        pxa.write('AVER:TYPE RMS')
        pxa.write('DISP:WIND:TRAC:Y:RLEV %f' % (-70))
        pxa.write('POW:ATT 0')
        pxa.write('CALC:MARK:FUNC NOIS')
        pxa.write('CALC:MARK:FUNC:BAND:SPAN %f' % (100e3))
        pxa.setSpan(150e3)
        pxa.setBW(2e3)
        
        pxa.write('POW:GAIN ON')
        pxa.write('POW:GAIN:BAND LOW')
        pxa.write('CORR:NOIS:FLO ON')
    return

    
def getWrites(lines):
    add_val_ls = []
    
    for line in lines:
        find = PAT.findall(line)
        try:
            add_val_ls.append((int(find[0][0], 16), int(find[0][1], 16)))
        except IndexError:
            find = WAIT_PAT.findall(line)
            try:
                add_val_ls.append(('w', float(find[0])))
            except IndexError:
                find = READ_PAT.findall(line)
                try:
                    if len(find) > 0:
                        add_val_ls.append(('read', int(find[0], 16)))
                except:
                    continue
    
    return add_val_ls


def writeLines(brd, add_val_ls):
    for addr, val in add_val_ls:
        if addr == 0x1b and val == 0x1:
            print ('s')
            
        if addr == 'w':
            time.sleep(val)
            
        elif addr == 'read':
            print ("reg %s = %s" % (hex(val), hex(brd.fx3.SpiRead(val))))
        
        elif addr < 0x600000:
            brd.fx3.SpiWrite(addr, val)
            print ("addr = %s, addr val = %s" % (hex(addr), hex(brd.fx3.SpiRead(addr))))
        
        else:
            reg32bitWrite(reg_write=brd.fx3.SpiWrite, addr=addr, value=val)
    return


def reg32bitRead(reg_write, reg_read, addr=0x01005618):

    # Set the base address (offset)
    reg_write(0x3D20, 0x00)
    reg_write(0x3D21, 0x00)
    reg_write(0x3D22, (addr >> 16) & 0xFF)
    reg_write(0x3D23, (addr >> 24) & 0xFF)

    # look if the enable_offset BIT is set in the address
    addr = addr & 0x0000FFFF
    if ((addr & (0x1 << 14)) >> 14) == 0:
        print ('NOTE: Given 32-bit address without enable_offset BIT set')
        print ('Setting the enable bit')
        addr = addr | (0x1 << 14)

    # read the 32-bit address
    result = 0
    for i in range(4):
        result = result | (reg_read(addr + i) << (8 * i))

    # clear the base address
    reg_write(0x3D20, 0x00)
    reg_write(0x3D21, 0x00)
    reg_write(0x3D22, 0x00)
    reg_write(0x3D23, 0x00)

    return result


def reg32bitWrite(reg_write, addr=0x01005618, value=0x00004000):
    # Set the base address
    reg_write(0x3D20, 0x00)
    reg_write(0x3D21, 0x00)
    reg_write(0x3D22, (addr >> 16) & 0xFF)
    reg_write(0x3D23, (addr >> 24) & 0xFF)

    # look if the enable_offset BIT is set
    addr = addr & 0x0000FFFF
    if ((addr & (0x1 << 14)) >> 14) == 0:
        print ('NOTE: Given 32-bit address without enable_offset BIT set')
        print ('Setting the enable bit')
        addr = addr | (0x1 << 14)

    # write the 32-bit address
    mask = 0xFF
    for i in range(4):
        reg_write((addr + i), (value >> 8 * i) & mask)

    # clear the base address
    reg_write(0x3D20, 0x00)
    reg_write(0x3D21, 0x00)
    reg_write(0x3D22, 0x00)
    reg_write(0x3D23, 0x00)
    

def pxaView(pxa, fcenter=None):
    pxa.reset()
    pxa.setContinuousMode()
    pxa.setDetector('POS')
    if fcenter:
        pxa.setCenter(fcenter)


def measFund(freq, pxa):
    amplitude = pxa.measurePeak(freq)
    print (amplitude[1])
    return amplitude[1]


def measureNSD(freq, offset, pxa):
    
    if abs(offset) < 1:
        fmeas = freq * (1 + offset)
    else:
        fmeas = freq + offset
    LOG.debug('fout = %dMHz, fmeas = %dMHz' % ((freq / 1e6), (fmeas/1e6)))
    pxa.setCenter(fmeas)
        
    PSD_min = 100    
    for delta in np.arange(-1e6, 1e6, 0.2e6):
        pxa.setCenter(fmeas + delta)
        pxa.write('INIT:CHP')
        PSD = float(pxa.ask('FETCH:CHP:DENS?'))
        PSD_min = min(PSD_min, PSD)
        #print "PSD_min = ",PSD_min
        
    return PSD_min   


if __name__ == '__main__':

    ''' FILL IN DIRECTORY AND FILENAME '''
    # Filename should be a fully qualified name (N:\hscdac\etc...)
    # KCHONG: do we need to put something here instead of None?
    filename = None
    # Path to log archive on the N:\ drive
    arcPath = None

    fh, sh, logFileName, logFilePath = logger.startLog(shlvl=10)
    try:
        main(filename)
    except Exception as e:
        ''' HANDLE EXCEPTIONS '''
        desired_trace = traceback.format_exc(sys.exc_info())
        LOG.error(desired_trace)
    finally:
        ''' CLEAN UP '''
        # Zip up log files and store on N: drive
        logger.stopLog(fh, sh)
        try:
            zfile = zf.ZipFile(arcPath, mode='a')
            zfile.write(filename=logFilePath, arcname=logFileName)
            zfile.close()
            os.remove(logFilePath)  # Destroy logs after zipping
        except AttributeError:
            pass