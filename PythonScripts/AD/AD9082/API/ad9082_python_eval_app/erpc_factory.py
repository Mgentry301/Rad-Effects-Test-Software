#
# Copyright (c) 2019 Analog Devices, Inc. All Rights Reserved.
# This software is proprietary to Analog Devices, Inc. and its licensors.
#

#pylint: disable=import-error
from __future__ import print_function
import settings

#Target Device: set PC-Evaluation Board Remote Protocol Library (eRPC)


if settings.device == "ad9082":
    erpc = "ad9082_client.1.0.9055.29198" # API 1.7.0
    erpc_client = "ad9082_client"
    erpc_server = "ad9082_erpc_server"
elif settings.device == "ad9081":
    erpc = "ad9081_client.1.0.9055.29108"
    erpc_client = "ad9081_client"
    erpc_server = "ad9081_erpc_server"
elif settings.device == "ad9988":
    erpc = "ad9988_client.1.0.9055.29373"
    erpc_client = "ad9988_client"
    erpc_server = "ad9988_erpc_server"
elif settings.device == "ad9986":
    erpc = "ad9986_client.1.0.9055.29286"
    erpc_client = "ad9986_client"
    erpc_server = "ad9986_erpc_server"
else:
    raise Exception("Selected device variant: {} not found".format(settings.device))