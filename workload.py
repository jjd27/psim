#
# Copyright (c) 2018 Nutanix Inc. All rights reserved.
#
# Author: David Vrabel <david.vrabel@nutanix.com>
#         Jonathan Davies <jonathan.davies@nutanix.com>
#

from math import floor
import random

import numpy as np

class Workload(object):
    def __init__(self):
        pass

class IdleWorkload(Workload):
    def tick(self, vcpu):
        vcpu.idle()

class UniformWorkload(Workload):
    def __init__(self, max_mem):
        self.max_mem = max_mem

    def tick(self, vcpu):
        pfn = random.randint(0, self.mm.total-1)
        vcpu.access(pfn)

class NormalWorkload(Workload):
    def __init__(self, sigma):
        self.sigma = sigma

    def tick(self, vcpu):
        pfn = -1
        while pfn < 0 or pfn >= vcpu.mm.total:
            pfn = int(floor(random.normalvariate(vcpu.mm.total / 2, self.sigma)))
        vcpu.access(pfn)

class WorkloadA(Workload):
    """Split the PFNs into two: idle and busy.

    Busy pages will be used with a random normal distribution.  Idle
    pages will be unused.

    This models a Windows desktop workload (watching youtube videos).

    """

    def __init__(self, mm, idle_ratio):
        self.used_pages = np.random.choice(mm.total, int((1 - idle_ratio) * mm.total), replace=False)

    def tick(self, vcpu):
        nr_used = len(self.used_pages)
        idx = -1
        while idx < 0 or idx >= nr_used:
            idx = int(floor(random.normalvariate(nr_used / 2, nr_used / 8)))
        vcpu.access(self.used_pages[idx])

class WorkloadB(Workload):
    """Split the PFNs into two: idle and busy.

    Busy pages will be used with a random uniform distribution.  Idle
    pages will be unused.

    This models a "harry" workload.

    """

    def __init__(self, mm, idle_ratio):
        self.used_pages = np.random.choice(mm.total, (1 - idle_ratio) * mm.total, replace=False)

    def tick(self, vcpu):
        pfn = np.random.choice(self.used_pages, 1)
        vcpu.access(pfn)

class WorkloadRotate(Workload):
    """Rotate between different workloads on a regular period."""

    def __init__(self, workloads, period):
        self.workloads = workloads
        self.period = period

    def tick(self, vcpu):
        current_workload = (vcpu.mm.host.tick / self.period) % len(self.workloads)
        self.workloads[current_workload].tick(vcpu)
