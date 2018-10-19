#
# Copyright (c) 2018 Nutanix Inc. All rights reserved.
#
# Author: David Vrabel <david.vrabel@nutanix.com>
#         Jonathan Davies <jonathan.davies@nutanix.com>
#

import numpy as np
import matplotlib.pyplot as plot
from optparse import OptionParser
import random
import sys

from workload import IdleWorkload

MINOR_DELAY = 1
MAJOR_DELAY = 32

PAGEOUT_TIME = 32

SCAN_INTERVAL = 256
SQUEEZE_INTERVAL = 1000
I = 4
A = 1

activity_log = True

p = 0
def d(s):
    if not activity_log:
        return
    sys.stdout.write(s[0])
    global p
    p += 1
    if p >= 64:
        p = 0
        sys.stdout.write("\n")

class Page(object):

    FREE = 0
    MAPPED = 1
    UNMAPPED = 2
    PAGED = 3
    
    def __init__(self, mm, pfn):
        self.mm = mm
        self.pfn = pfn
        self.state = self.FREE
        self.accessed = False
        self.nr_accesses = 0
        self.delay = 0
        self.timestamp = 0

    def access(self, vcpu):
        if self.state == self.FREE:
            self.mm.minor_faults += 1
            self.mm.alloc(self.pfn)
            self._accessed(vcpu)
        elif self.state == self.MAPPED:
            self._accessed(vcpu)
        elif self.state == self.UNMAPPED:
            self.mm.minor_faults += 1
            self._block(vcpu, MINOR_DELAY)
        elif self.state == self.PAGED:
            self.mm.major_faults += 1
            self._block(vcpu, MAJOR_DELAY)

    def is_active(self):
        if self.state == self.MAPPED:
            return True
        self.delay -= 1
        if self.delay == 0:
            self.mm.map(self.pfn)
        return self.state == self.MAPPED

    def is_paged(self):
        return self.state == self.PAGED

    def test_and_clear_accessed(self):
        a = self.accessed
        self.accessed = False
        return a

    def map(self):
        if self.state == self.FREE:
            d("A")
        elif self.state == self.PAGED:
            d("P")
        else:
            d("M")
        self.state = self.MAPPED

    def unmap(self):
        d("U")
        self.state = self.UNMAPPED
        # Unmapped pages are accounted as free, to avoid having to
        # model direct reclaim.
        self.mm.free(self.pfn)

    def pageout(self):
        if self.state == self.UNMAPPED:
            d("F")
            self.state = self.PAGED

    def _accessed(self, vcpu):
        self.accessed = True
        self.nr_accesses += 1
        vcpu.work()

    def _block(self, vcpu, delay):
        self.delay = delay
        vcpu.block(self)

class Memory(object):
    def __init__(self, host, size):
        self.host = host
        self.allocated = 0
        self.total = size
        self.limit = size
        self.pages = []
        for i in range(size):
            self.pages.append(Page(self, i))
        self.active = []
        self.inactive = []
        self.swapq = []
        self.major_faults = 0
        self.minor_faults = 0

    def alloc(self, pfn):
        self.allocated += 1
        self.active.append(pfn)
        self.pages[pfn].map()

    def free(self, pfn):
        self.allocated -= 1

    def map(self, pfn):
        self.alloc(pfn)

    def pageout(self, pfn):
        self.inactive.remove(pfn)
        self.pages[pfn].unmap()
        self.pages[pfn].timestamp = self.host.tick
        self.swapq.append(pfn)

    def access(self, pfn, vcpu):
        return self.pages[pfn].access(vcpu)

    def scan(self):
        self._age()
        self._reclaim()

    def _age(self):
        # Keep at least I pages in the inactive list, and A page in
        # the active list.
        #
        # Scan from head (oldest) to tail (newest).
        for pfn in list(self.active):
            if len(self.inactive) >= I or len(self.active) < A:
                break

            # Page accessed since last scan, move to tail. Otherwise,
            # move to tail of inactive list.
            self.active.remove(pfn)
            if self.pages[pfn].test_and_clear_accessed():
                self.active.append(pfn)
            else:
                self.inactive.append(pfn)

    def _reclaim(self):
        while self.allocated > self.limit:
            # Scan from head (oldest) to tail (newest).
            for pfn in list(self.inactive):
                if self.allocated <= self.limit:
                    return
                self.pageout(pfn)
            self._age()

    def swap_write(self):
        while len(self.swapq):
            page = self.pages[self.swapq[0]]
            elapsed = self.host.tick - page.timestamp
            if elapsed < PAGEOUT_TIME:
                break
            del self.swapq[0]
            page.pageout()

    def plot_accesses(self):
        plot.xlabel("Pages (ordered by accesses)")
        plot.ylabel("Accesses")
        plot.plot(map(lambda x: x.nr_accesses,
                      sorted(self.pages, key=lambda x: x.nr_accesses, reverse=True)))
        plot.grid(True)

class Vcpu(object):
    def __init__(self, mm):
        self.work_todo = 0
        self.work_done = 0
        self.blocked = None
        self.mm = mm
        self.workload = IdleWorkload()

    def set_workload(self, workload):
        self.workload = workload

    def tick(self):
        # Is work required this tick?  Work is accumulated while blocked.
        # TODO change 1.0 into a configurable parameter for the vCPU
        if random.random() < 1.0:
            self.work_todo += 1

        if self.blocked:
            if self.blocked.is_active():
                pfn = self.blocked.pfn
                self.blocked = None
                self.access(pfn)
            else:
                d("_")
                return
        else:
            if self.work_todo > 0:
                self.workload.tick(self)  # likely to call access() on a pfn
            else:
                self.idle()

    def idle(self):
        d(" ")

    def access(self, pfn):
        self.mm.access(pfn, self)

    def block(self, page):
        d("_")
        self.blocked = page

    def work(self):
        self.work_todo -= 1
        self.work_done += 1
        d(".")

class Host(object):
    def __init__(self, mem_max, squeezer):
        self.mm = Memory(self, mem_max)
        self.vcpu = Vcpu(self.mm)
        self.squeezer = squeezer

        self.tick = 0

    def enable_activity_log(self, on):
        global activity_log
        activity_log = on

    def set_workload(self, workload):
        self.vcpu.set_workload(workload)

    def run(self, ticks):
        while self.tick < ticks:
            if self.tick % SCAN_INTERVAL == 0:
                d("/")
                self.mm.scan()
            if self.tick % SQUEEZE_INTERVAL == 0:
                d("|")
                self.squeezer.squeeze(self)

            self.vcpu.tick()
            self.mm.swap_write()
            self.tick += 1
