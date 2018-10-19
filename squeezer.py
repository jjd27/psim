#
# Copyright (c) 2018 Nutanix Inc. All rights reserved.
#
# Author: David Vrabel <david.vrabel@nutanix.com>
#         Jonathan Davies <jonathan.davies@nutanix.com>
#

import numpy as np
import matplotlib.pyplot as plot

MAJOR_FAULT_LIMIT = 2
MINOR_FAULT_LIMIT = 5

class Squeezer(object):
    def __init__(self):
        self.last_work = 0
        self.last_major_faults = 0
        self.last_minor_faults = 0
        self.ticks = []
        self.limit = []
        self.work = []
        self.major_faults = []
        self.minor_faults = []
        self.longterm_estimates = []

        self.longterm_estimate = None

    def squeeze(self, host):
        pass

    def count_faults(self, host):
        major_faults = host.mm.major_faults - self.last_major_faults
        self.last_major_faults = host.mm.major_faults
        minor_faults = host.mm.minor_faults - self.last_minor_faults
        self.last_minor_faults = host.mm.minor_faults

        if host.tick > 0:
            self.major_faults.append(major_faults)
            self.minor_faults.append(minor_faults)

        return (major_faults, minor_faults)

    def _calc_stats(self, host):
        if host.tick == 0:
            return

        self.limit.append(host.mm.limit)
        self.work.append(self._work_done(host))
        self.ticks.append(host.tick)
        if self.longterm_estimate:
            self.longterm_estimates.append(self.longterm_estimate)

    def _work_done(self, host):
        if len(self.ticks) > 0:
            ticks = host.tick - self.ticks[-1]
        else:
            ticks = host.tick
        work = float(host.vcpu.work_done - self.last_work) / ticks
        self.last_work = host.vcpu.work_done
        return work

    def plot(self, host):
        x = map(lambda x: x/1000, self.ticks)
        
        plot.subplot(221)
        plot.xlabel("Time/ktick")
        plot.ylabel("Limit/pages")
        plot.ylim((0.0, host.mm.total))
        plot.plot(x, self.limit, label="Short-term")
        if self.longterm_estimate:
            plot.plot(x, self.longterm_estimates, label="Long-term")
        plot.legend()
        plot.grid(True)
        
        plot.subplot(223)
        plot.xlabel("Time/ktick")
        plot.ylabel("Work done")
        plot.ylim((0.0, 1.0))
        plot.plot(x, self.work)
        plot.grid(True)

        plot.subplot(222)
        host.mm.plot_accesses()

        plot.subplot(224)
        plot.xlabel("Time/ktick")
        plot.ylabel("Faults")
        plot.plot(x, self.major_faults, label="Major")
        #plot.plot(x, self.minor_faults, label="Minor")
        plot.legend()
        plot.grid(True)


class NullSqueezer(Squeezer):
    pass


class StaticSqueezer(Squeezer):
    def __init__(self, limit):
        Squeezer.__init__(self)

        self.estimate = limit

    def squeeze(self, host):
        major_faults, _ = self.count_faults(host)

        host.mm.limit = self.estimate

        self._calc_stats(host)


class SimpleSqueezer(Squeezer):
    def __init__(self):
        Squeezer.__init__(self)

    def squeeze(self, host):
        major_faults, _ = self.count_faults(host)

        # Squeeze?
        if major_faults < MAJOR_FAULT_LIMIT and host.mm.limit > 1:
            host.mm.limit -= 1

        # Desqueeze?
        elif major_faults > MAJOR_FAULT_LIMIT:
            host.mm.limit += 1

        self._calc_stats(host)


class Mk1Squeezer(Squeezer):
    def __init__(self):
        Squeezer.__init__(self)

    def squeeze(self, host):
        major_faults, minor_faults = self.count_faults(host)

        limit = host.mm.limit

        if major_faults < MAJOR_FAULT_LIMIT:
            limit -= 2
        elif major_faults > MAJOR_FAULT_LIMIT:
            limit += 2

        elif minor_faults < MINOR_FAULT_LIMIT:
            limit -= 1
        elif minor_faults > MINOR_FAULT_LIMIT:
            limit += 1

        host.mm.limit = max(limit, 1)

        self._calc_stats(host)

class Mk2Squeezer(Squeezer):
    def __init__(self):
        Squeezer.__init__(self)

        self.estimate = []

    def squeeze(self, host):
        major_faults, _ = self.count_faults(host)

        limit = host.mm.limit

        if major_faults < MAJOR_FAULT_LIMIT:
            limit -= (MAJOR_FAULT_LIMIT - major_faults)
        elif major_faults > MAJOR_FAULT_LIMIT:
            limit += major_faults

        limit = max(limit, 1)

        self.estimate.append(limit)
        if len(self.estimate) > 10:
            self.estimate = self.estimate[1:]

        host.mm.limit = sum(self.estimate) / len(self.estimate)

        self._calc_stats(host)

class Mk3Squeezer(Squeezer):
    def __init__(self):
        Squeezer.__init__(self)

    def squeeze(self, host):
        major_faults, minor_faults = self.count_faults(host)

        limit = host.mm.limit

        if major_faults < MAJOR_FAULT_LIMIT:
            limit -= (MAJOR_FAULT_LIMIT - major_faults)
        elif major_faults > MAJOR_FAULT_LIMIT:
            limit += major_faults

        host.mm.limit = max(limit, 1)

        self._calc_stats(host)

class Mk4Squeezer(Squeezer):
    def __init__(self):
        Squeezer.__init__(self)

        self.faults = 0

    A = 0.6

    def squeeze(self, host):
        major_faults, _ = self.count_faults(host)

        self.faults = self.A * major_faults + (1 - self.A) * self.faults

        limit = host.mm.limit

        if self.faults < MAJOR_FAULT_LIMIT:
            limit -= (MAJOR_FAULT_LIMIT - self.faults / 2)
        elif self.faults > MAJOR_FAULT_LIMIT:
            limit += self.faults / 2

        host.mm.limit = max(limit, 1)
        print limit

        self._calc_stats(host)
