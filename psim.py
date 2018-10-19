#! /usr/bin/python
#
# Copyright (c) 2018 Nutanix Inc. All rights reserved.
#
# Author: David Vrabel <david.vrabel@nutanix.com>
#         Jonathan Davies <jonathan.davies@nutanix.com>
#

import numpy as np
import matplotlib.pyplot as plot
from optparse import OptionParser

from host import Host
from squeezer import *
from workload import *

squeezer_map = {
    "static": StaticSqueezer,
    "simple": SimpleSqueezer,
    "mk1": Mk1Squeezer,
    "mk2": Mk2Squeezer,
    "mk3": Mk3Squeezer,
    "mk4": Mk4Squeezer,
}

parser = OptionParser()
parser.add_option("-m", "--memory", metavar="MAX", type="int", default=64)
parser.add_option("-t", "--ticks", metavar="TICKS", type="int", default=10000)
parser.add_option("-s", "--squeezer", type="choice", choices=squeezer_map.keys(), default="mk5")
    
(options, args) = parser.parse_args()

def main():
    memory = options.memory
    ticks = options.ticks

    if args:
        squeezer = squeezer_map[options.squeezer](int(args[0]))
    else:
        squeezer = squeezer_map[options.squeezer]()

    host = Host(memory, squeezer)
    host.enable_activity_log(False)
    host.set_workload(WorkloadRotate([WorkloadA(host.mm, 0.5), WorkloadA(host.mm, 0.25)], 100000))
    host.run(ticks)
    squeezer.plot(host)

    print "\n%d / %d (%.2f %%)" % (host.vcpu.work_done, ticks,
                                   float(host.vcpu.work_done) / ticks * 100.0)

    plot.show()

if __name__ == "__main__":
    main()
