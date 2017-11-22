#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
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


import itertools
from ansible.module_utils.basic import AnsibleModule
import ansible.module_utils.tc_utils as tc_utils # pylint: disable=E0611,E0401


DOCUMENTATION = '''
---
module: tc_class
author:
    - Matt Suringa
short_description: Manage linux tc classes

version_added: "2.4"

description:
    - Manage Linux Traffic Control classes

options:
    classid:
        description:
            - Handle ID for the class
            - Minor number (after the colon) cannot be empty or 0
        required: false
        default: "1:1"
    device:
        description:
            - Name of the network device interface
        required: false
        default: eth0
    discipline:
        description:
            - Type of queuing discipline you want to apply.
            - Only supports "htb" qdisc at the moment
        required: false
        default: htb
    parent:
        description:
            - Handle ID for the qdisc parent (must exist or module will fail)
            - Minor number (after the colon) must be empty or 0
        required: false
        default: "1:0"
    rate:
        description:
            - Rate to apply to the class, must be provided in the form of ##Unit, i.e. 10Mbit, 500Kbit
            - Allowed units are [ bit, kbit, mbit, gbit, bps, kbps, mbps, gbps ]
        required: true
    state:
        description:
            - Whether the class should exist or not, taking action if the state is different from what is stated.
        required: false
        default: present
        choices: [ present, absent ]
'''

EXAMPLES = '''
- name: Create new class
  tc_class:
    rate: 10Mbit

- name: Create new class with non-default parameters
  tc_class:
    parent: "1:0"
    classid: "1:6"
    device: eth4
    rate: 2Gbit
'''

RETURN = '''
none
'''


STR_NONE = "NONE"
STR_MATCH = "MATCH"
STR_CHANGE = "CHANGE"
RATES = dict(
    bit=1,
    bps=8,
    kbit=1000,
    kbps=8000,
    mbit=1000000,
    mbps=8000000,
    gbit=1000000000,
    gbps=8000000000
)

def _convert(rate):
    """ Convert provided rate to bits to do accurate comparison later """
    rate_set = ["".join(x) for _, x in itertools.groupby(rate, key=str.isdigit)]
    return int(rate_set[0]) * RATES[rate_set[1].lower()]


def _validate_rate(module):
    """ Compare input rate and rate currently specified for class """
    rate = ["".join(x) for _, x in itertools.groupby(module.params["rate"], key=str.isdigit)]
    if len(rate) != 2:
        return (False, "Incorrect syntax")
    # Fail if rate does not contain a valid number
    try:
        _ = int(rate[0])
    except ValueError:
        return (False, "No number specified in rate")
    if rate[1].lower() not in RATES:
        return (False, "Invalid rate specified, please use one of %s" % RATES.keys())

    return (True, "")


def _check_current_class(module):
    """ Check what the current class for the specicified device is """
    class_set = tc_utils.get_current("class", module).split("\n")

    if class_set[0] == [""]:
        return STR_NONE

    # Find classid from input in what's currently setup
    idx = [i for i, s in enumerate(class_set) if module.params["classid"] in s]
    if not idx:
        return STR_NONE

    cls = class_set[idx[0]].split(" ")
    u_rate = _convert(module.params["rate"])
    c_rate = _convert(cls[7])
    if u_rate != c_rate:
        return STR_CHANGE

    return STR_MATCH


def main():
    """ Main """

    argument_spec = tc_utils.common_argument_spec()
    argument_spec.update(
        dict(
            parent=dict(required=False, default="1:0", type="str"),
            classid=dict(required=False, default="1:1", type="str"),
            discipline=dict(required=False, default="htb", type="str"),
            rate=dict(required=True, type='str')
        )
    )

    # Instantiate the module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    state = module.params["state"]
    action = tc_utils.set_action(state)

    # Validate our input
    if not tc_utils.validate_device(module):
        module.fail_json(device=module.params["device"], msg="Device doesn't exist on machine")

    if not tc_utils.validate_handle(module.params["parent"]):
        url = "http://tldp.org/HOWTO/Traffic-Control-HOWTO/components.html#c-handle"
        module.fail_json(
            parent=module.params["parent"],
            msg="Invalid parent handle, check %s to see valid syntax" % url
        )

    if not tc_utils.validate_parent(module):
        module.fail_json(
            parent=module.params["parent"],
            msg="Parent handle does not exist."
        )

    if not tc_utils.validate_classid(module, "classid"):
        module.fail_json(
            classid=module.params["classid"],
            msg="Invalid classid. Either the major number didn't match the parent or the minor number was equal to 0"
        )

    (rco, msg) = _validate_rate(module)
    if not rco:
        module.fail_json(
            rate=module.params["rate"],
            msg=msg
        )

    if module.check_mode:
        cmd = tc_utils.build_class_command(module, action)
        module.debug("Running in check mode, would have run: %s" % " ".join(cmd))
        module.exit_json(skipped=True)

    current_class = _check_current_class(module)

    if current_class == STR_MATCH and module.params["state"] == "present":
        module.exit_json(changed=False)

    if current_class == STR_NONE and module.params["state"] == "absent":
        module.exit_json(changed=False)

    if current_class == STR_CHANGE and module.params["state"] == "present":
        action = "change"

    # create the class
    cmd = tc_utils.build_class_command(module, action)
    (rco, _, err) = module.run_command(cmd)
    if rco is not None and rco != 0:
        module.fail_json(msg=err, rc=rco)

    module.exit_json(changed=True)


main()
