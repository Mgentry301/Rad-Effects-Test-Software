import sys
import time
import os
import datetime

sys.path.append(r'C:\Program Files\Analog Devices\ACE\Client')

# noinspection SpellCheckingInspection
import clr  # noqa
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
clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')

# noinspection PyUnresolvedReferences,SpellCheckingInspection
from AnalogDevices.Csa.Remoting.Clients import ClientManager  #noqa

def register_loop(client2,register_array_addr,array_length):
    outlist = ['0']*array_length
    for i in range(array_length):
        outlist[i] = client2.ReadRegister(register_array_addr[i])
    return outlist
    

def register_record(output_dictionary,register_array_addr,array_length,register_array_vals):
    for i in range(array_length):
        
        output_dictionary["Reg_" + str(hex(int(register_array_addr[i])))] = register_array_vals[i].strip('\r\n')
    return output_dictionary
def toggle_selection_TF(statement):
    print(statement)
    valid_inputs = {'y','n'}
    while True:
        usr_inp = input("please enter y or n \n").strip().lower()
        
        if usr_inp in valid_inputs:
            print("status = " + usr_inp)
            return usr_inp          
        else: ("invalid, type y or n")
    
def enter_values(prompt):
    while True:
        user_inp = input(prompt + "\n").strip().lower()
        
        user_inp_true = input("is " + user_inp + " what you want? [y,n] \n")
        
        if user_inp_true in ['y','n']:
            return user_inp
        else:
            print("re-enter value")

def main():
    run_number= enter_values("What is the run number?")
    print(run_number)
    reg_corr_flag = toggle_selection_TF("are you enabling register based correction?")
    filename2 = r'C:\Campaigns\LBNL_May_2025' + os.sep + "run_" + run_number + os.sep + "run_" + run_number + "_registers_ADAR3006_correction_" + reg_corr_flag + ".csv"
    print("output log is at the following location")
    print(filename2)


    manager = ClientManager.Create()
    client = manager.CreateRequestClient("localhost:2357")
    execute_macro(client,filename2,reg_corr_flag)
    # client.CloseSession()
def execute_macro(client,filename,reg_corr):
    # UI.SelectTab("Root::");
    client.AddByComponentId("ADAR3006Board")
    client.NavigateToPath("Root::System")
    client.ContextPath = "\System\Subsystem_1\ADAR3006 Board"
    client.Run("@DefaultView")
    client.ContextPath = "\System\Subsystem_1\ADAR3006 Board\ADAR3006"
    client.NavigateToPath("Root::System.Subsystem_1.ADAR3006 Board.ADAR3006")
    client.SetBoolParameter("RX_TXB", "False", "-1")
    client.Run("@SetupWrite")
    client.SetBoolParameter("update_spi_pinb_ctl", "True", "-1")
    client.Run("@PinOrSpiControl")
    client.Run("@AllBeamUpdate")
    client.Run("@Temp_Comp_Select")
    client.Run("@Manual_Temp_Comp_Write")
    client.Run("@Temp_Comp_Update")
    # @Subsystem_1.ADAR3006 Board.ADAR3006: Evaluation.UI.MemoryMap.NavigateToChipAndMemoryMap();
    client.SetRegister("10", "255", "-1")
    client.Run("@ApplySettings")
    client.ReadRegister("10")
          
    input("Please ensure that the device has been powered on through the tester and configured through ACE")

    # UI.SelectTab("Root::System.Subsystem_1.ADAR3006 Board.ADAR3006");
    # UI.SelectTab("Root::System.Subsystem_1.ADAR3006 Board.ADAR3006.GeneralWriteRead");
    # UI.SelectTab("Root::System.Subsystem_1.ADAR3006 Board.ADAR3006");
    # @Subsystem_1.ADAR3006 Board.ADAR3006: Evaluation.UI.MemoryMap.NavigateToChipAndMemoryMap();
    #ALL = client.Run("@ReadSettings")
    #print(ALL)
    #current_time = time.strftime("%H:%M:%S")
    #print(current_time)
    Keep_Looping = True
    first_run = True
    #filename = r'C:\Data\ADAR3006\ADAR3006_reg.csv'
    dict_results = {}
   
    # #csvf = CSV.Results_File( filename )
    csvf = Results_File( filename )
    
    Reg_8   = 0
    Reg_A   = -2
    Reg_12  = 0
    Reg_13  = 0
    Reg_14  = 0
    Reg_42  = 0
    Reg_51  = 0
    Reg_53  = 0
    Reg_55  = 0
    Reg_57  = 0
    Reg_58  = 0
    Reg_59  = 0
    Reg_5A  = 0
    Reg_5B  = 0
    #Reg_5D  = 0
    Reg_A0  = 0
    Reg_AD  = 0
    Reg_130 = 0
    Reg_11D = 0
    Reg_3BF = 0
    Reg_3FF = 0
    
    register_read_array_number = [0,1,10,18,19,20,32,33,48,49,50,51,52,53,54]

    register_read_array = [str(x) for x in register_read_array_number]
    register_read_comp_array = register_loop(register_read_array_number)
    print(register_read_array)
    input("Press any key to begin recording")
    print("recording data now")
    print("press CTRL + C to end program")
    
    input("Press Enter to begin recording")
    print("recording started")
    print("press CTRL + C to end program")
    while Keep_Looping:
    
        output_register_list = register_loop(client,register_read_array,len(register_read_array))

        current_time = time.strftime("%H:%M:%S")
            
        current_date = time.strftime("%d/%m/%Y")
        dt = datetime.datetime.now()
        current_time_ms = str(dt.microsecond/1000)
        

        
        # Reg_8   = Reg_8.decode().strip('\r\n')
        # Reg_A   = Reg_A.decode().strip('\r\n')
        # Reg_12  = Reg_12.decode().strip('\r\n')
        # Reg_13  = Reg_13.decode().strip('\r\n')
        # Reg_14  = Reg_14.decode().strip('\r\n')
        # Reg_42  = Reg_42.decode().strip('\r\n')
        # Reg_51  = Reg_51.decode().strip('\r\n')
        # Reg_53  = Reg_53.decode().strip('\r\n')
        # Reg_55  = Reg_55.decode().strip('\r\n')
        # Reg_57  = Reg_57.decode().strip('\r\n')
        # Reg_58   = Reg_58.decode().strip('\r\n')
        # Reg_59   = Reg_59.decode().strip('\r\n')
        # Reg_5A   = Reg_5A.decode().strip('\r\n')
        # Reg_5B   = Reg_5B.decode().strip('\r\n')
        # Reg_A0   = Reg_A0.decode().strip('\r\n')
        # Reg_AD   = Reg_AD.decode().strip('\r\n')
        # Reg_130   = Reg_130.decode().strip('\r\n')
        # Reg_11D   = Reg_11D.decode().strip('\r\n')
        # Reg_3BF   = Reg_3BF.decode().strip('\r\n')
        # Reg_3FF   = Reg_3FF.decode().strip('\r\n')
        if reg_corr == "y":
            
            if register_read_comp_array != output_register_list:
                client.Run("@SoftReset")
                client.SetRegister("10", "255", "-1")
                client.Run("@ApplySettings")
                client.Run("@SetupWrite")
                client.Run("@PinOrSpiControl")
                client.Run("@AllBeamUpdate")
        
        dict_results = {}
            
        dict_results = register_record(dict_results,register_read_array,len(register_read_array),output_register_list)
        
       
            
        dict_results["Date"] = current_date
        dict_results["Time"] = current_time
        dict_results["Time_ms"]         = current_time_ms
        
        if first_run:
            csvf.AutoCreateHeader(dict_results) # Creates header in data file
        first_run = False
                    
        csvf.WriteDictionary(dict_results) # Write data to data file
    
    # UI.SelectTab("tool.macrorecorder");





if __name__ == "__main__":
    main()