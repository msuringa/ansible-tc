# Ansible modules for Traffic Control

Manage the 3 different aspects required to set up traffic control (bandwidth throttling) on a Linux box: qdiscs, classes and filters.

## Features
Create and manage a single qdisc per network interface _(might change to allow multiple)_<br />
Create multiple classes with limited throughput speeds per qdisc.<br />
Configure a filter on a port and assign it to a created class.

## Examples
```yaml
- name: Create new qdisc
  tc_qdisc:
    handle: "1:0"
    device: eth0
    qdisc: root

- name: Create new class
  tc_class:
    parent: "1:0"
    classid: "1:6"
    device: eth1
    rate: 2Mbit

- name: Create new filter
  tc_filter:
    parent: "1:0"
    flowid: "1:6"
    port: 80
    priority: 5    
```

## Requirements
Requires access to the tc command (so must be run as root or equivalent).


## Installation
Clone the repository in the location of your choosing

Ensure the following 2 paramers are set in your ansible.cfg file:
```yaml
module_utils = /path/to/cloned/repo/library/tc_utils
library = /path/to/cloned/repo/library
```

## Dependencies
None

## License
GPLv3

## Author information
[Matt Suringa](https://github.com/msuringa)

## To Do
- Allow for more filter options in tc_filter, currently only port is supported
- Add some return values for the different modules
- Add unit tests
- Add installation using setuptools
