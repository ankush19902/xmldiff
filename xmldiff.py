"""Diff XML files ignoring the order of attributes and elements.

The approach is to sort both files by attribute and element, and then reuse an
existing diff implementation on the sorted files.

Background: http://dalelane.co.uk/blog/?p=3225
"""
import argparse
import os
import platform
import subprocess
from operator import attrgetter

import lxml.etree as le

__author__ = 'Dale Lane <email@dalelane.co.uk>'


def create_file_obj(prefix, name):
    """Prepare the location of the temporary file for 'xmldiff'."""
    return {
        "filename": os.path.abspath(name),
        "tmpfilename": "." + prefix + "." + os.path.basename(name)
    }


def sort_by_id(elem):
    """Sort elements by ID if the 'id' attribute can be cast to an int."""
    id = elem.get('id')
    if id:
        try:
            return int(id)
        except ValueError:
            return 0
    return 0


def sort_by_text(elem):
    """Sort XML elements by their text contents."""
    text = elem.text
    if text:
        return text
    else:
        return ''


def sort_attrs(item, sorteditem):
    """Sort XML attributes alphabetically by key.

    The original item is left unmodified and its attributes are copied to the
    provided `sorteditem`.
    """
    attrkeys = sorted(item.keys())
    for key in attrkeys:
        sorteditem.set(key, item.get(key))


def sort_elements(items, newroot):
    """Sort XML elements.

    The sorted elements will be added as children of the provided `newroot`.
    This is a recursive function, and will be called on each of the children of
    `items`.

    The intended sort order is to sort by XML element name.
    If more than one element has the same name, we want to sort by their text
    contents.
    If more than one element has the same name and they do not contain any text
    contents, we want to sort by the value of their ID attribute.
    If more than one element has the same name, but has no text contents or ID
    attribute, their order is left unmodified.
    We do this by performing three sorts in the reverse order.
    """
    items = sorted(items, key=sort_by_id)
    items = sorted(items, key=sort_by_text)
    items = sorted(items, key=attrgetter('tag'))

    # Once sorted, we sort each of the items
    for item in items:
        # Create a new item to represent the sorted version of the next item,
        # and copy the tag name and contents
        newitem = le.Element(item.tag)
        if item.text and item.text.isspace() is False:
            newitem.text = item.text

        # Copy the attributes (sorted by key) to the new item
        sort_attrs(item, newitem)

        # Copy the children of item (sorted) to the new item
        sort_elements(list(item), newitem)

        # Append this sorted item to the sorted root
        newroot.append(newitem)


def sort_file(fileobj):
    """Sort the provided XML file.

    `fileobj.filename` will be left untouched. A new sorted copy of it will be
    created at `fileobj.tmpfilename`.
    """
    with open(fileobj['filename'], 'r') as original:
        # Parse the XML file and get a pointer to the top
        xmldoc = le.parse(original)
        xmlroot = xmldoc.getroot()

        # Create a new XML element that will be the top of the sorted copy of
        # the XML file
        newxmlroot = le.Element(xmlroot.tag)

        # Create the sorted copy of the XML file
        sort_attrs(xmlroot, newxmlroot)
        sort_elements(list(xmlroot), newxmlroot)

        # Write the sorted XML file to the temp file
        newtree = le.ElementTree(newxmlroot)
        with open(fileobj['tmpfilename'], 'wb') as newfile:
            newtree.write(newfile, pretty_print=True)

if __name__ == '__main__':
    # Check required arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'diffcommand',
        help='the command that should be run to diff the sorted files')
    parser.add_argument('filename1', help='the first XML file to diff')
    parser.add_argument('filename2', help='the second XML file to diff')
    args = parser.parse_args()

    # Sort each of the specified files
    filefrom = create_file_obj("from", args.filename1)
    sort_file(filefrom)
    fileto = create_file_obj("to", args.filename2)
    sort_file(fileto)

    # Invoke the requested diff command to compare the two sorted files
    if platform.system() == "Windows":
        cmd = ' '.join(
            (args.diffcommand, filefrom["tmpfilename"], fileto["tmpfilename"]))
        popen_args = ["cmd", "/c", cmd]
    else:
        cmd = ' '.join(
            (args.diffcommand, os.path.abspath(filefrom['tmpfilename']),
             os.path.abspath(fileto['tmpfilename'])))
        popen_args = ["/bin/bash", "-i", "-c", cmd]

    sp = subprocess.Popen(popen_args)
    sp.communicate()

    # Cleanup - delete the temporary sorted files after the diff terminates
    os.remove(filefrom['tmpfilename'])
    os.remove(fileto['tmpfilename'])
