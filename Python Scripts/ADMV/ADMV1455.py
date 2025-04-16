#Version 2


# Generated code compatible with Python 2.7+

## Copyright (c) 2025 by Analog Devices, Inc.  All rights reserved.  This software is proprietary to Analog Devices, Inc. and its licensors.
## This software is provided on an 'as is' basis without any representations, warranties, guarantees or liability of any kind.
## Use of the software is subject to the terms and conditions of the Clear BSD License ( https://spdx.org/licenses/BSD-3-Clause-Clear.html ).

# Requirements:
#  - pythonnet


import sys
import time
import os
import datetime
import csv

sys.path.append(r'C:\Program Files\Analog Devices\ACE\Client')

# noinspection SpellCheckingInspection
import clr  # noqa

# noinspection SpellCheckingInspection
clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')

from AnalogDevices.Csa.Remoting.Clients import ClientManager  #noqa
class Results_File:
    def __init__(self, fileName="", debug=False):
        self.__fileName       = fileName
        self.__genHeaderYet   = False
        self.__listOfKeys     = []
        self.__writeMode      = 'wa'
        self.__overWrite      = False
        self.__debug          = debug
        
        #see if file already exists
        if os.path.exists(fileName):
            #see if we can get a listOfKeys
            f = open(fileName, 'r')
            firstLine = f.readline()
            f.close()
            
            #is there already a header?
            if len(firstLine) > 0:
                self.__listOfKeys   = firstLine.strip('\n').split(',')
                self.__genHeaderYet = True                
    
        if self.__debug:
            print ("called: '__init__'")
    
    def SetFileName(self, fileName):
        '''Sets the file name'''
        self.__fileName = fileName
        
    def GetFileName(self):
        '''Gets the file name'''
        return self.__fileName
        
    def __write_line(self, line):
        try:
            f = open(self.__fileName, self.__writeMode)
            f.write(line + '\n')
            f.close()
            return True
        except:
            print ("Could not open file!")
            return False
        
    def SetOverWriteMode(self, mode):
        '''Sets the behavior of the class is the file already exists'''
        self.__overWrite = mode
        
    def GetOverWriteMode(self):
        '''Gets the behavior of the class is the file already exists'''
        return self.__overWrite
        
    def AutoCreateHeader(self, dict):
        '''Automatically makes a header given dict'''
        if self.__debug:
            print ("called: 'AutoCreateHeader()'")
        
        exists = os.path.exists(self.__fileName)
        cont = True
        if exists and not self.__overWrite:
            cont = False
                        
        if (not self.__genHeaderYet and cont):
            self.__writeMode = 'w'        
            self.__listOfKeys = dict.keys()
            self.__listOfKeys = sorted(dict.keys())
            
            line = ""
            
            for key in self.__listOfKeys:
                line = line + str(key) + ','
            line = line[:-1]    
                        
            self.__genHeaderYet = self.__write_line(line)
            self.__writeMode = 'a'
            
            return self.__genHeaderYet
        
        return False
            
    def ManualCreateHeader(self, listOfKeys):
        '''Allows the user to define which keys in what order to create the header'''
        if self.__debug:
            print ("called: 'ManualCreateHeader()'")
        
        exists = os.path.exists(self.__fileName)
        cont = True
        if exists and not self.__overWrite:
            cont = False
        
        if (not self.__genHeaderYet) and cont:
            self.__writeMode = 'w'        
            self.__listOfKeys = listOfKeys
            
            line = ""
            
            for key in self.__listOfKeys:
                line = line + str(key) + ','
            line = line[:-1]
                        
            self.__genHeaderYet = self.__write_line(line)
            self.__writeMode = 'a'
            
            return self.__genHeaderYet
        
        return False
        
    def WriteDictionary(self, dict):
        '''Writes the user's dictionary to a file with desired elements separated
        by commas'''
        if self.__debug:
            print ("called: 'WriteDictionary()'")
        
        exists = os.path.exists(self.__fileName)
        if (exists and self.__genHeaderYet):
            self.__writeMode = 'a'
            
            line = ""
            
            for element in self.__listOfKeys:
                try:
                    line = line + str(dict[element]) + ','
                except:
                    #key to dictionary was invalid; do nothing
                    line = line + ','
            line = line[:-1]
            
            res = self.__write_line(line)        
            
            return res
        
        return False
        
    def WriteKeyValueList(self, list):
        '''This method converts a list of alternating keys and values to a dictionary,
        and then writes the dictionary to a file with elements separated by commas.
        The list must be of a length divisible by 2, and ordered in a
        ["(key)", "(value)", "(key)", "(value)", ...] fashion.'''
        if self.__debug:
            print ("called: 'WriteKeyValueList()'")
        
        dict = ConvertKeyValueListToDict(list)
        return WriteDictionary(dict)
        
    def DeleteColumn(self, index):
        '''If a CSV file is loaded and valid, this function will delete an
        entire column from the file.  This will also delete the associated
        key from listOfKeys for future appending'''
        if self.__debug:
            print ("called: 'DeleteColumn()'")
        
        success = False
        
        exists = os.path.exists(self.__fileName)
        if (exists and self.__genHeaderYet):
        
            success = True
        
            #Get the contents of the entire file
            f = open(self.__fileName, 'r')
            entireFile = f.read()
            f.close()
            
            lines = entireFile.splitlines()
            
            #update listOfKeys
            keys = lines[0].split(',')
            try:
                self.__listOfKeys.remove(keys[index])
            except:
                success = False
                print ("Error: Could not delete from column %s" % (index))
            
            f = open(self.__fileName, 'w')
            for l in lines:
                t_list = l.split(',')
                try:
                    del(t_list[index])
                except:
                    success = False
                    print ("Error: Could not delete from column %s" % (index))
                    
                n_line = ''
                for elem in t_list:
                    n_line = n_line + elem + ','
                n_line = n_line[:-1] + '\n'
                
                f.write(n_line)
            
            f.close()
        
        return success
            
    def DeleteColumnByKey(self, keys):
        '''If a CSV file is loaded and valid, this function will delete an
        entire column from the file.  This will also delete the associated
        key from listOfKeys for future appending'''
        if self.__debug:
            print ("called: 'DeleteColumnByKeys()'")
        
        success = True
        
        for key in keys:
            try:
                success = success and self.DeleteColumn(self.__listOfKeys.index(key))
            except:
                success = False
                print ("Error: Could not delete column indicated by key '%s'" % (key))
        
        return success
             
    def DeleteRow(self, index):
        '''If a CSV file is loaded and valid, this function will delete an
        entire row from the file. The header (first) line cannot be deleted'''
        if self.__debug:
            print ("called: 'DeleteRow()'")
        
        success = False
        
        exists = os.path.exists(self.__fileName)
        if (exists and self.__genHeaderYet):
        
            success = True
           
            #Get the contents of the entire file
            f = open(self.__fileName, 'r')
            entireFile = f.read()
            f.close()
            
            lines = entireFile.splitlines()
            
            if index != 0:
                try:
                    del(lines[index])
                except:
                    success = False
                    print ("Error: Could not delete row %s" % (index))
            else:
                success = False
                print ("Error: Could not delete row %s, it's the header" % (index))
                
            f = open(self.__fileName, 'w')
            for line in lines:
                f.write(line + '\n')
            f.close()
            
        return success
                
    def FetchColumn(self, index):
        '''If a CSV file is loaded and valid, this function will fetch an
        entire column from the file.'''
        if self.__debug:
            print ("called: 'FetchColumn()'")
        
        column = []
        
        exists = os.path.exists(self.__fileName)
        if (exists and self.__genHeaderYet):
        
            success = True
        
            #Get the contents of the entire file
            f = open(self.__fileName, 'r')
            entireFile = f.read()
            f.close()
            
            lines = entireFile.splitlines()
            
            for line in lines:
                column.append( line.split(',')[index] )
            
            column = column[1:]
            
        return column
    
    def FetchColumnByKey(self, key):
        '''If a CSV file is loaded and valid, this function will fetch an
        entire column from the file.'''
        if self.__debug:
            print ("called: 'FetchColumn()'")
        
        column = []
        
        exists = os.path.exists(self.__fileName)
        if (exists and self.__genHeaderYet):
        
            success = True
        
            #Get the contents of the entire file
            f = open(self.__fileName, 'r')
            entireFile = f.read()
            f.close()
            
            lines = entireFile.splitlines()
            
            try:
                column_keys = lines[0].split(',')
                index = 0
                for column_key in column_keys:
                    if (column_key.strip() == key):
                        break
                    index += 1
                    
                for line in lines[1:]:
                    column.append( line.split(',')[index] )
            except:
                pass
            
        return column
        
    @staticmethod
    def ConvertKeyValueListToDict(list):
        '''This method converts a list of alternating keys and values to a dictionary.
        The list must be of a length divisible by 2, and ordered in a
        ["(key)", "(value)", "(key)", "(value)", ...] fashion.'''
        
        dict = {}
        length = len(list)
        
        if length % 2 != 0:
            raise Exception("Length of list not divisible by 2.")
        
        for i in range(0, length, 2):
            dict[list[i]] = list[i + 1]
        
        return dict
    
# noinspection SpellCheckingInspection
#clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
#clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')

# noinspection PyUnresolvedReferences,SpellCheckingInspection
#from AnalogDevices.Csa.Remoting.Clients import ClientManager  #noqa

def register_loop(client2,register_array_addr,array_length):
    outlist = ['0']*array_length
    for i in range(array_length):
        outlist[i] = client2.ReadRegister(register_array_addr[i])
    return outlist


def register_record(output_dictionary,register_array_addr,array_length,register_array_vals):
    for i in range(array_length):
        
        output_dictionary["Reg_" + str(hex(int(register_array_addr[i])))] = register_array_vals[i].strip('\r\n')
    return output_dictionary

def enter_values(prompt):
    while True:
        user_inp = input(prompt + "\n").strip().lower()
        
        user_inp_true = input("is " + user_inp + " what you want? [y,n] \n")
        
        if user_inp_true in ['y','n']:
            return user_inp
        else:
            print("re-enter value")

def main():
    run_number = enter_values("What is the run number?")
    print(run_number)
    filename2 = r'C:\Campaigns\LBNL_May_2025' + os.sep + "run_" + run_number + os.sep +  "run_" + run_number + "_registers_ADMV1455.csv"
    print("output log is at the following location")
    print(filename2)
    print()
    input("Please ensure that the device has been powered on through the tester and configured through ACE")
    manager = ClientManager.Create()
    client = manager.CreateRequestClient("localhost:2357")
    execute_macro(client,filename2)
    # client.CloseSession()
# noinspection SpellCheckingInspection


def execute_macro(client,filename):
    #input("Please ensure that the device has been powered on through the tester and configured through ACE")
    print("\n")
    
    input("Are You Certain? Do you see a tone on your output (8GHz)?")
    print("\n")
    client.AddByComponentId("ADMV1455Board")
    client.NavigateToPath("Root::System")
    client.ContextPath = "\System\Subsystem_1\ADMV1455 Board"
    client.Run("@DefaultView")
    #Protecting the part so it's chip enabled is booted up safely
#    client.SetBoolParameter("virtual-parameter-dut_cen_pin_bool", "False", "-1")
#    client.SetBoolParameter("virtual-parameter-dut_rstb_pin_bool", "False", "-1")
 #   client.SetBoolParameter("virtual-parameter-dac_rstb_pin_bool", "False", "-1")
  #  client.SetBoolParameter("virtual-parameter-ps_en_pin_bool", "False", "-1")

    Keep_Looping = True
    first_run = True
    #filename = r'C:\Data\ADMV1455\ADMV1455_reg.csv'
    dict_results = {}
   
    # #csvf = CSV.Results_File( filename )
    csvf = Results_File( filename )



    #input("Please return to LabVIEW to Actually Power on the Part then press a key here to continue")
    #booting up the part and setting its default values again
#    client.SetBoolParameter("virtual-parameter-dut_cen_pin_bool", "True", "-1")
#    client.SetBoolParameter("virtual-parameter-dut_rstb_pin_bool", "True", "-1")
    client.ContextPath = "\System\Subsystem_1\ADMV1455 Board\ADMV1455"
    

    

    register_read_array_number = [0,4,5,10,19,64,65,67,81,82,83,84,95,160]
    register_read_array = [str(x) for x in register_read_array_number]
    print(register_read_array)
    input("Press any key to begin recording")
    print("recording data now")
    print("press CTRL + C to end program")
    
    # Configuration of the ADMV1455, do not uncomment this. It is for reference only
    
    # client.WriteRegister("0", "24")
    # client.WriteRegister("334", "10")
    # client.WriteRegister("388", "1")
    # client.WriteRegister("514", "0")
    # client.WriteRegister("520", "0")
    # client.WriteRegister("650", "1")
    # client.WriteRegister("651", "0")
    # client.WriteRegister("652", "0")
    # client.WriteRegister("653", "0")
    # client.WriteRegister("672", "16")
    # client.WriteRegister("673", "191")
    # client.WriteRegister("674", "18")
    # client.WriteRegister("2048", "10")
    # client.WriteRegister("2049", "135")
    # client.WriteRegister("2050", "0")
    # client.WriteRegister("2051", "170")
    # client.WriteRegister("2052", "3")
    # client.WriteRegister("2057", "0")
    # client.WriteRegister("2058", "32")
    # client.WriteRegister("2059", "0")
    # client.WriteRegister("2060", "4")    
    
    while Keep_Looping:
        output_register_list = register_loop(client,register_read_array,len(register_read_array))
        
        
    
        
        current_time = time.strftime("%H:%M:%S")
            
        current_date = time.strftime("%d/%m/%Y")
        dt = datetime.datetime.now()
        current_time_ms = str(dt.microsecond/1000)
        #print(Reg_0)
        

        
        dict_results = {}
        dict_results = register_record(dict_results,register_read_array,len(register_read_array),output_register_list)
        
            
       
            
        dict_results["Date"] = current_date
        dict_results["Time"] = current_time
        dict_results["Time_ms"] = current_time_ms
        
        if first_run:
            csvf.AutoCreateHeader(dict_results) # Creates header in data file
        first_run = False
                    
        csvf.WriteDictionary(dict_results) # Write data to data file
    
    # UI.SelectTab("tool.macrorecorder");


if __name__ == "__main__":
    main()

