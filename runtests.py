#!/usr/bin/python2.1
"""run local tests.
"""

import sys
import os
import getopt

def main():

    usage_msg = """\
Usage: runtests.py [-d dir] [-f file]
Runs all tests, or only those in dir or file.
"""

    pathname = '.'
    filename = None

    options, arg = getopt.getopt(sys.argv[1:], 'hd:f:')
    for name, value in options:
        name = name[1:]
        if name == 'h':
            err_exit(usage_msg, 0)
        elif name == 'd':
            pathname = value.strip()
        elif name == 'f':
            filename = value.strip()
        else:
            err_exit(usage_msg)

    here = os.path.dirname(sys.argv[0])
    if not here.startswith('/'):
        here = os.getcwd()
    execfile = '%s/../../utilities/testrunner.py' % here
    execfile = os.path.normpath(execfile)

    args = [execfile, '-q']
    if filename:
        args.extend(['-f', filename])
    elif pathname:
        args.extend(['-d', pathname])

    args.insert(0, sys.executable)
    err = os.spawnv(os.P_WAIT, sys.executable, args)
    sys.exit(err)


def err_exit(message, rc=2):
    sys.stderr.write("\n%s\n" % message)
    sys.exit(rc)

if __name__ == '__main__':
    main()



