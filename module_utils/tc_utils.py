#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility functions for the tc modules

Copyright (C) 2017 Matt Suringa <matthijs.suringa@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

def common_argument_spec():
    """ Define common arguments for tc modules """
    return dict(
        device=dict(required=False, default="eth0", type="str"),
        state=dict(required=False, default="present", choices=["present", "absent"], type="str")
    )


def _build_generic_command(binary, tc_type, action, device):
    """ Construct generic portion of the tc command """
    cmd = [binary, tc_type]
    cmd.append(action)
    cmd.extend(["dev", device])

    return cmd

def build_qdisc_command(module, action):
    """ Construct command parameters and return the list for qdisc"""
    cmd = _build_generic_command(module.get_bin_path('tc', required=True),
                                 "qdisc", action, module.params["device"])
    if action == "show":
        return cmd

    cmd.append(module.params["qdisc"])
    if action == "del":
        return cmd

    cmd.extend(["handle", module.params["handle"]])
    cmd.append(module.params["discipline"])

    return cmd

def build_class_command(module, action):
    """ Construct command parameters and return the list for class"""
    cmd = _build_generic_command(module.get_bin_path('tc', required=True),
                                 "class", action, module.params["device"])
    if action == "show":
        return cmd

    cmd.extend(["parent", module.params["parent"]])
    cmd.extend(["classid", module.params["classid"]])

    if action == "del":
        return cmd

    cmd.append(module.params["discipline"])
    cmd.extend(["rate", module.params["rate"]])
    cmd.extend(["ceil", module.params["ceil"]])

    return cmd

def build_filter_command(module, action):
    """ Construct command parameters and return the list for filter"""
    cmd = _build_generic_command(module.get_bin_path('tc', required=True),
                                 "filter", action, module.params["device"])
    if action == "show":
        return cmd

    cmd.extend(["parent", module.params["parent"]])
    cmd.extend(["protocol", "ip"]) # Required, static part of the command
    cmd.extend(["prio", str(module.params["priority"])])
    cmd.append("u32")       # Classifier is static
    if action == "del":
        return cmd

    cmd.extend(["match", "ip", "dport", str(module.params["port"]), "0xffff"])
    cmd.extend(["flowid", module.params["flowid"]])

    return cmd

def build_filter_cgroup_command(module, action):
    """ Construct command parameters and return the list for filter"""
    cmd = _build_generic_command(module.get_bin_path('tc', required=True),
                                 "filter", action, module.params["device"])
    if action == "show":
        return cmd

    cmd.extend(["parent", module.params["parent"]])
    cmd.extend(["prio", str(module.params["priority"])])
    if action == "del":
        return cmd

    cmd.extend(["handle", str(module.params["handle"])])
    cmd.append("cgroup")

    return cmd

def get_current(tc_type, module):
    """ Return any current configuration for the specified type (qdisc, class, filter)"""
    if tc_type == "qdisc":
        cmd = build_qdisc_command(module, "show")
    if tc_type == "class":
        cmd = build_class_command(module, "show")
    if tc_type == "filter":
        cmd = build_filter_command(module, "show")

    (rco, out, err) = module.run_command(cmd)
    if rco is not None and rco != 0:
        module.fail_json(msg=err, rc=rco)

    return out


def validate_device(module):
    """ Check if provided device name exists on current server """
    dev = module.params["device"]

    # netifaces library is not installed by default on all versions and distros
    # Attempt to import it, otherwise resort to querying "ip a"
    try:
        import netifaces
        return dev in netifaces.interfaces()
    except ImportError:
        cmd = [module.get_bin_path("ip", required=True), "a"]
        (rco, out, err) = module.run_command(cmd)
        if rco is not None and rco != 0:
            module.fail_json(msg=err, rc=rco)
        return dev in out


def validate_handle(handle):
    """ Check if provided handle is valid for qdisc """
    try:
        (_, minor) = handle.split(":")
    except ValueError:
        return False

    if minor:
        return minor == "0"
    return True

def validate_parent(module):
    """ Validate the provided parent """
    qdisc_set = get_current("qdisc", module).split(" ")
    (major, sep, _) = module.params["parent"].partition(":")

    if qdisc_set[2] != "".join([major, sep]):
        return False

    return True


def validate_classid(module, handle):
    """ Validate the provided classid """
    (p_major, _, _) = module.params["parent"].partition(":")
    (c_major, _, c_minor) = module.params[handle].partition(":")

    if p_major != c_major:
        return False
    if not c_minor or int(c_minor) == 0:
        return False

    return True


def set_action(state):
    """ Set action based on provided state """
    actions = dict(
        present="add",
        absent="del"
    )

    return actions[state]
