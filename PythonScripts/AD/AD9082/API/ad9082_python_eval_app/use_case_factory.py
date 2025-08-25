#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function
from use_case_0 import UseCase0
from use_case_3 import UseCase3
from use_case_10 import UseCase10
from use_case_11 import UseCase11
from use_case_20 import UseCase20
class UseCaseFactory(object):
    """Factory class for creating use case objects
    """

    def __init__(self):
        """Constructor
        """
    
    def create(self, uc, description_formatter):
        """ Create a use case object from a use case number
        """
        if (uc == 0):
            uc = UseCase0()                                 # NCO test mode
        elif (uc == 3):
            uc = UseCase3(description_formatter)            # JESD204B at 7.33Gbps lane rate.
        elif uc == 10:
            uc = UseCase10(description_formatter)           # JESD204C at 8Gbps lane rate.
        elif uc == 11:
            uc = UseCase11(description_formatter)           # JESD204C at 16Gbps lane rate.
        elif uc == 20:
            uc = UseCase20(description_formatter)           # JESD204C at 24Gbps lane rate.
        else:
            raise Exception("Selected use case #{} not found".format(uc))

        return uc
