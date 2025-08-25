#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#
from __future__ import print_function
import sys
import os
import paramiko
import settings
import erpc_factory

class EvalBoardTarget(object):
    """Class used to establish target communication
    """
    def __init__(self, ipaddr):
        self.ipaddr = ipaddr
        self.port = 22
        self.user = "root"
        self.pw = "analog"
        self.erpc_server_dir = os.path.join(settings.erpc_folder, erpc_factory.erpc, r"content")
        self.erpc_server_file = erpc_factory.erpc_server

    def wait_for_ping(self):
        """Return the ping status of the target
        """
        print("Attempting to ping MicroZed (will try up to 10 seconds)...")
        for x in range(10):
            response = os.system('ping -n 1 -w 1000 ' + self.ipaddr + ' > NUL')
            if (response == 0):
                print("MicroZed is alive!")
                return 0

        print("Can't ping MicroZed.")
        return -1

    def test_connection(self):
        """Test the connection with target
        """
        s = paramiko.SSHClient()
        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Testing connection with target", self.ipaddr, "...")
        is_connected = False
        num_connect_tries = 30
        while (not is_connected and num_connect_tries != 0):
            num_connect_tries -= 1
            try:
                s.connect(self.ipaddr, self.port, self.user, self.pw, timeout=1)
                is_connected = True
                print("Connection ok.")
            except Exception as e:
                #print("Connect to microzed failed: " + str(e))
                print(".")

        s.close()
        
        if (not is_connected):
            print("Can't establish connection with microzed", self.ipaddr)
            return -1
        
        return 0

    def start_erpc_server(self):
        """ Copy and start the erpc server on the target
        """
        s = paramiko.SSHClient()
        s.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        print("Connecting to target", self.ipaddr, " ...")
        is_connected = False
        num_connect_tries = 10
        while (not is_connected and num_connect_tries != 0):
            num_connect_tries -= 1
            try:
                s.connect(self.ipaddr, self.port, self.user, self.pw, timeout=1)
                is_connected = True
                print("Connection ok.")
            except Exception as e:
                print("Connect to microzed failed: " + str(e))
                print(".")

        if (not is_connected):
            print("Can't establish connection with microzed")
            return -1

        # stdin, stdout, stderr = s.exec_command("ps -u root | grep erpc")
        # print(stdout.read())

        # kill any currently running server
        stdin, stdout, stderr = s.exec_command("killall -u root ./" + self.erpc_server_file)
        print(stdout.read())

        # Copy the erpc server to the microzed target 
        print("Copying the erpc server to target: ", self.erpc_server_file)
        sftp = s.open_sftp()
        sftp.chdir("/root")
        sftp.put(os.path.join(self.erpc_server_dir, self.erpc_server_file), r"/root/" + self.erpc_server_file)
        sftp.close()

        #print("Make erpc server executable")
        stdin, stdout, stderr = s.exec_command("chmod +x " r"/root/" + self.erpc_server_file)

        print("Start erpc server on target")
        stdin, stdout, stderr = s.exec_command(r"/root/" + self.erpc_server_file + " &")
        #don't read on & invoked process! print stdout.read"()

        stdin, stdout, stderr = s.exec_command("ps -u root | grep erpc")
        print(stdout.read())

        s.close()

        return 0