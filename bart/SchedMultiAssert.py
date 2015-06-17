# $Copyright:
# ----------------------------------------------------------------
# This confidential and proprietary software may be used only as
# authorised by a licensing agreement from ARM Limited
#  (C) COPYRIGHT 2015 ARM Limited
#       ALL RIGHTS RESERVED
# The entire notice above must be reproduced on all authorised
# copies and copies may only be made to the extent permitted
# by a licensing agreement from ARM Limited.
# ----------------------------------------------------------------
# File:        SchedMultiAssert.py
# ----------------------------------------------------------------
# $
#
"""A library for asserting scheduler scenarios based on the
statistics aggregation framework"""

import re
import inspect
import cr2
from cr2.stats import SchedConf as sconf
from cr2.plotter.Utils import listify
from sheye.SchedAssert import SchedAssert
from sheye import Utils

class SchedMultiAssert(object):

    """The primary focus of this class is to assert and verify
    predefined scheduler scenarios. This does not compare parameters
    across runs"""

    def __init__(self, run, topology, execnames):
        """Args:
                run (cr2.Run): A single cr2.Run object
                    or a path that can be passed to cr2.Run
                topology(cr2.stats.Topology): The CPU topology
                execname(str, list): List of execnames or single task
        """

        self._execnames = listify(execnames)
        self._run = Utils.init_run(run)
        self._pids = self._populate_pids()
        self._topology = topology
        self._asserts = self._populate_asserts()
        self._populate_methods()

    def _populate_asserts(self):
        """Populate SchedAsserts for the PIDs"""

        asserts = {}

        for pid in self._pids:
            asserts[pid] = SchedAssert(self._run, self._topology, pid=pid)

        return asserts

    def _populate_pids(self):
        """Map the input execnames to PIDs"""

        if len(self._execnames) == 1:
            return sconf.get_pids_for_process(self._run, self._execnames[0])

        pids = []

        for proc in self._execnames:
            pids += sconf.get_pids_for_process(self._run, proc)

        return list(set(pids))

    def _create_method(self, attr_name):
        """A wrapper function to create a dispatch function"""

        return lambda *args, **kwargs: self._dispatch(attr_name, *args, **kwargs)

    def _populate_methods(self):
        """Populate Methods from SchedAssert"""

        for attr_name in dir(SchedAssert):
            attr = getattr(SchedAssert, attr_name)

            valid_method = attr_name.startswith("get") or \
                           attr_name.startswith("assert")
            if inspect.ismethod(attr) and valid_method:
                func = self._create_method(attr_name)
                setattr(self, attr_name, func)

    def get_task_name(self, pid):
        """Get task name for the PID"""
        return self._asserts[pid].execname


    def _dispatch(self, func_name, *args, **kwargs):
        """The dispatch function to call into the SchedAssert
           Method
        """

        assert_func = func_name.startswith("assert")
        num_true = 0

        rank = kwargs.pop("rank", None)
        result = kwargs.pop("result", {})
        param = kwargs.pop("param", re.sub(r"assert|get", "", func_name, count=1).lower())

        for pid in self._pids:

            if pid not in result:
                result[pid] = {}
                result[pid]["task_name"] = self.get_task_name(pid)

            attr = getattr(self._asserts[pid], func_name)
            result[pid][param] = attr(*args, **kwargs)

            if assert_func and result[pid][param]:
                num_true += 1

        if assert_func and rank:
            return num_true == rank
        else:
            return result

    def generate_events(self):
        """Generate Events for the trace plot"""

        events = []
        for s_assert in self._asserts.values():
            events += s_assert.generate_events(start_id=len(events))
        return events

    def plot(self):
        """
        Returns:
            cr2.plotter.AbstractDataPlotter. Call .view() for
                displaying the plot
        """
        level = "cpu"
        events = self.generate_events()
        names = [s.name for s in self._asserts.values()]
        num_lanes = self._topology.level_span(level)
        return cr2.EventPlot(events, names, "CPU: ", num_lanes)