import os
import sys
from subprocess import Popen, STDOUT


def main():
    with open(os.devnull, 'r+b', 0) as devnull:
        p = Popen(["gedit", "mkchain.log"], stdout=devnull, stdin=devnull, stderr=STDOUT, close_fds=True)
    return 0


sys.exit(main())
