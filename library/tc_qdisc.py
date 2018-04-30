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
module: tc_qdisc
author:
    - Matt Suringa
short_description: Manage linux tc qdisc

version_added: "2.4"

description:
    - Manage Linux Traffic Control queue disciplines
notes:
    - Currently only supports management of 1 qdisc master per interface
options:
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
    handle:
        description:
            - Unique identifier for the qdisc
            - Minor number (after the colon) must be empty or 0
        required: false
        default: "1:0"
    state:
        description:
            - Whether the qdisc should exist or not, taking action if the state is different from what is stated.
        required: false
        default: present
        choices: [ present, absent ]
    qdisc:
        description:
            - Whether the qdisc applies to egress (root) or ingress
        required: false
        default: root
        choices: [ root, ingress ]
'''

EXAMPLES = '''
- name: Create new qdisc
  tc_qdisc:
    handle: "2:0"

- name: Create new qdisc on different interface
  tc_qdisc:
    handle: "1:0"
    device: eth4
    qdisc: root

- name: Create new ingress qdisc
  tc_qdisc:
    handle: "3:0"
    qdisc: ingress
'''

RETURN = '''
none
'''


DEFAULT_QDISC = "pfifo_fast"
STR_DEFAULT = "DEFAULT"
STR_MATCH = "MATCH"
STR_CHANGE = "CHANGE"


def _check_current_qdisc(module):
    """ Check what the current qdisc for the specicified device is """
    qdisc_set = tc_utils.get_current("qdisc", module).split("\n")[-2].split(" ")

    (major, sep, _) = module.params["handle"].partition(":")

    if qdisc_set[1] == DEFAULT_QDISC:
        return STR_DEFAULT
    elif qdisc_set[1] == module.params["discipline"]:
        if qdisc_set[2] == "".join([major, sep]):
            return STR_MATCH

    return STR_CHANGE


def main():
    """ Main """

    argument_spec = tc_utils.common_argument_spec()
    argument_spec.update(
        dict(
            handle=dict(required=False, default="1:0", type="str"),
            qdisc=dict(required=False, default="root", choices=["root", "ingress"], type="str"),
            discipline=dict(required=False, default="htb", type="str")
        )
    )

    # Instantiate the module
    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    # Validate our input
    if not tc_utils.validate_device(module):
        module.fail_json(device=module.params["device"], msg="Device doesn't exist on machine")

    if not tc_utils.validate_handle(module.params["handle"]):
        module.fail_json(
            handle=module.params["handle"],
            msg="Invalid handle syntax, check http://tldp.org/HOWTO/Traffic-Control-HOWTO/components.html#c-handle to see valid syntax"
            )

    # Get action based on state
    state = module.params["state"]
    action = tc_utils.set_action(state)

    # Skip task with debufg output if check_mode is enabled
    if module.check_mode:
        cmd = tc_utils.build_qdisc_command(module, action)
        module.debug("Running in check mode, would have run: %s" % " ".join(cmd))
        module.exit_json(skipped=True, command=cmd)

    # Check if there is anything setup already, and compare that with user input
    current_qdisc = _check_current_qdisc(module)

    if current_qdisc == STR_MATCH and module.params["state"] == "present":
        module.exit_json(changed=False)

    if current_qdisc == STR_CHANGE and module.params["state"] == "present":
        cmd = tc_utils.build_qdisc_command(module, "del")
        (rco, out, err) = module.run_command(cmd)
        if rco is not None and rco != 0:
            module.fail_json(msg=err, rc=rco)

    if current_qdisc == STR_DEFAULT and module.params["state"] == "absent":
        module.exit_json(changed=False)

    cmd = tc_utils.build_qdisc_command(module, action)
    (rco, out, err) = module.run_command(cmd)
    if rco is not None and rco != 0:
        module.fail_json(msg=err, rc=rco)

    module.exit_json(changed=True, msg=out)

main()
