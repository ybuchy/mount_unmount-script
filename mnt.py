#!/usr/bin/env python3
from os import getuid, path, listdir
from subprocess import run, PIPE, Popen
from ast import literal_eval
from pathlib import Path
"""
This script can be used to mount or unount devices like usb sticks.
"""

# recursive function that checks if a partition of the device is 
# mounted to "/"
# input: the output of lsblk --json for a device (as a dict or list of dicts)
def checkChildren(children):
    # check if a partition is mounted to root
    for child in children:
        if isinstance(child, str):
            if children["mountpoint"] == "/":
                return 0
            break
        else:
            if child["mountpoint"] == "/":
                return 0
    # check if there are more nested children than the partitions
    # if there are, check for these children also
    if isinstance(children, list):
        for child in children:
            if "children" in child.keys():
                return checkChildren(child["children"])
    else:
        if "children" in children.keys():
            return checkChildren(children["children"])
    return 1
      
# needs to be executed as root
if getuid() != 0:
    print("Please execute as root")
    exit(1)

# get names of devices / partitions and the mountpoints as json
output = run(["lsblk", "--json", "-o", "name,mountpoint"], capture_output=True)
output = output.stdout.decode("UTF-8")
formatted_output = output.replace(" ", "").replace("\n", "").replace("true", "True").replace("false", "False").replace("null", "None")
bd = literal_eval(formatted_output)
# remove the device where some partition is mounted at "/" from the list
for blockdevice in bd["blockdevices"]:
    if not checkChildren(blockdevice):
        bd["blockdevices"].remove(blockdevice)

# check if there are any devices left
if bd["blockdevices"] == []:
    print("No device found")
    exit(1)

# go through partitions and check if and where they are mounted
partitions = {}
for blockdevice in bd["blockdevices"]:
    for child in blockdevice["children"]:
        if child["mountpoint"] is None:
            partitions[f"/dev/{child['name']}"] = "not mounted"
        else:
            partitions[f"/dev/{child['name']}"] = child["mountpoint"]

# format string for dmenu
dmenu_string = "\n".join(f"{key} ({partitions[key]})" for key in partitions.keys())
dmenu_string += "\nmount all"
dmenu_string += "\nunmount all"

# using dmenu, ask user what partition to use
echo = Popen(["echo", dmenu_string], stdout = PIPE)
try:
    partition = run(["dmenu", "-p", "Which device to (un)mount?"], capture_output=True, stdin=echo.stdout)
except OSError:
    print("Please make sure dmenu is installed!")
    exit(1)
partition = partition.stdout.decode("UTF-8")
if partition == "":
    exit(1)
partition = partition.replace("\n", "").split(" ")[0]

parts = []

# get what needs to be mounted or unmounted
if "mount" in partition:
    for part in partitions.keys():
        if partition == "mount" and partitions[part] == "not mounted":
            parts.append(part)
        elif partition == "unmount" and partitions[part] != "not mounted":
            parts.append(part)
else:
    parts.append(partition)

used = []
for part in parts:
    # if it is mounted, unmount it
    if partitions[part] != "not mounted":
        run(["umount", part])
        Path(partitions[part]).rmdir()
    else:
    # if a device is already mounted to /mnt/usb, make a new directory to mount the device to
        dest = "/mnt/usb"
        i = 2
        while dest in partitions.values() or dest in used:
            dest = f"/mnt/usb{i}"    
            i += 1
        Path(dest).mkdir(parents=True, exist_ok=True)
        run(["mount", part, dest])
        used.append(dest)
