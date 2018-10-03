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


from ansible.module_utils.basic import AnsibleModule
import ansible.module_utils.tc_utils as tc_utils # pylint: disable=E0611,E0401


DOCUMENTATION = '''
---
module: tc_filter
author:
    - Matt Suringa
short_description: Manage linux tc filters

version_added: "2.4"

description:
    - Manage Linux Traffic Control filters
notes:
    - Priority is used as the identifier on which to manage filters, this means
      that if you apply multiple filters, you need to specifiy different
      priorities otherwise previous installed filters will be overwritten.

options:
    device:
        description:
            - Name of the network device interface
        required: false
        default: eth0
    flowid:
        description:
            - Handle ID for the class this filter should be applied to
            - Minor number (after the colon) cannot be empty or 0
        required: false
        default: "1:1"
    parent:
        description:
            - Handle ID for the qdisc parent (must exist or module will fail)
            - Minor number (after the colon) must be empty or 0
        required: false
        default: "1:0"
    port:
        description:
            - Port on which to apply the rates set in the class
        required: true
    priority:
        description:
            - Priority of this filter, lower numbers get the highest priority
        required: true
    state:
        description:
            - Whether the class should exist or not, taking action if the state is different from what is stated.
        required: false
        default: present
        choices: [ present, absent ]
    cgroup:
        description:
            - Apply rate limit to cgroup with matching net_cls.clasid
            - Overrides port specification
            - Use invalid port value (65536) to ensure port filter is NOT used
        required: false
        default: false
        type: bool
        choices: [ true, false, yes, no ]
    handle:
        description:
            - The class handle to attach the cgroup 
            - Decimal or hex  value (example: "5:" or "0x5")
        required: false
'''

EXAMPLES = '''
- name: Create new filter
  tc_filter:
    parent: "1:0"
    flowid: "1:6"
    port: 80
    priority: 5

- name: Create cgroup filter
  tc_filter:
    device: eth0
    flowid: "1:8"
    parent: "1:0"
    port: 65536
    priority: 8
    state: present
    cgroup: yes
    handle: "8:"
'''

RETURN = '''
none
'''


STR_NONE = "NONE"
STR_MATCH = "MATCH"
STR_CHANGE = "CHANGE"


def _check_current_filter(module):
    """ Check what the current filter for the specicified device+qdisc+class is """
    filter_set = tc_utils.get_current("filter", module).split("\n")
    #(major, sep, _) = module.params["handle"].partition(":")

    if filter_set[0] == [""]:
        return STR_NONE

    idx = [i for i, s in enumerate(filter_set) if module.params["flowid"] in s]
    if not idx:
        return STR_NONE

    # tc output is split over 2 lines....
    fls = filter_set[idx[0]].split(" ")
    fl_match = filter_set[idx[0]+1].split(" ")

    if module.params["priority"] != int(fls[6]):
        return STR_NONE

    # tc stores its port as hex, so convert it to base10 to compare
    if module.params["port"] != int(fl_match[3].split("/")[0], 16):
        return STR_CHANGE

    return STR_MATCH


def _class_exists(module):
    current_classes = tc_utils.get_current("class", module)
    return module.params["flowid"] in current_classes


def main():
    """ Main """

    argument_spec = tc_utils.common_argument_spec()
    argument_spec.update(
        dict(
            parent=dict(required=False, default="1:0", type="str"),
            flowid=dict(required=False, default="1:1", type="str"),
            priority=dict(required=True, type="int"),
            port=dict(required=True, type="int"),
            cgroup=dict(required=False, default=False, type="bool"),
            handle=dict(required=False, type="str")
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
        module.fail_json(
            parent=module.params["parent"],
            msg="Invalid parent handle, check http://tldp.org/HOWTO/Traffic-Control-HOWTO/components.html#c-handle to see valid syntax"
        )

    if not tc_utils.validate_parent(module):
        module.fail_json(
            parent=module.params["parent"],
            msg="Parent handle does not exist."
        )

    if not tc_utils.validate_classid(module, "flowid"):
        module.fail_json(
            flowid=module.params["flowid"],
            msg="Invalid flowid. Either the major number didn't match the parent or the minor number was equal to 0"
        )

    if not _class_exists(module):
        module.fail_json(
            flowid=module.params["flowid"],
            msg="Cannot create a filter for a non existant class"
        )

    if module.check_mode:
        cmd = tc_utils.build_filter_command(module, action)
        module.debug("Running in check mode, would have run: %s" % " ".join(cmd))
        module.exit_json(skipped=True)

    current_filter = _check_current_filter(module)

    if current_filter == STR_MATCH and module.params["state"] == "present":
        module.exit_json(changed=False)

    if current_filter == STR_CHANGE and module.params["state"] == "present":
        cmd = tc_utils.build_filter_command(module, "del")
        (rco, _, err) = module.run_command(cmd)
        if rco is not None and rco != 0:
            module.fail_json(msg=err, rc=rco)

    if current_filter == STR_NONE and module.params["state"] == "absent":
        module.exit_json(changed=False)

    # create the filter
    if module.params["cgroup"] is not True:
        cmd = tc_utils.build_filter_command(module, action)
    else:
        cmd = tc_utils.build_filter_cgroup_command(module, action)
    #module.fail_json(msg=cmd, rc=1)
    (rco, _, err) = module.run_command(cmd)
    if rco is not None and rco != 0:
        module.fail_json(msg=err, rc=rco)

    module.exit_json(changed=True)


main()
