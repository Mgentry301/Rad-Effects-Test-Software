# Generated code compatible with Python 2.7+

## Copyright (c) 2026 by Analog Devices, Inc.  All rights reserved.  This software is proprietary to Analog Devices, Inc. and its licensors.
## This software is provided on an 'as is' basis without any representations, warranties, guarantees or liability of any kind.
## Use of the software is subject to the terms and conditions of the Clear BSD License ( https://spdx.org/licenses/BSD-3-Clause-Clear.html ).

# Requirements:
#  - pythonnet


import sys
sys.path.append(r'C:\Program Files\Analog Devices\ACE\Client')

# noinspection SpellCheckingInspection
import clr  # noqa
# noinspection SpellCheckingInspection
clr.AddReference('AnalogDevices.Csa.Remoting.Clients')
clr.AddReference('AnalogDevices.Csa.Remoting.Contracts')

# noinspection PyUnresolvedReferences,SpellCheckingInspection
from AnalogDevices.Csa.Remoting.Clients import ClientManager  #noqa


def main():
    manager = ClientManager.Create()
    client = manager.CreateRequestClient("localhost:2357")
    execute_macro(client)
    # client.CloseSession()


# noinspection SpellCheckingInspection
def execute_macro(client):
    client.AddByComponentId("ADF4030Board")
    client.NavigateToPath("Root::System")
    client.ContextPath = "\System\Subsystem_1\ADF4030 Board"
    client.Run("@DefaultView")
    client.ContextPath = "\System\Subsystem_1\ADF4030 Board\ADF4030"
    client.NavigateToPath("Root::System.Subsystem_1.ADF4030 Board.ADF4030")
    client.Run("@LockDetectReadback")
    client.Run("@LoadDefault")
    client.Run("@ApplySettings")
    # UI.SelectTab("tool.macrorecorder");


if __name__ == "__main__":
    main()