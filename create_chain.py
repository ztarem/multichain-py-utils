import logging
import os
import shlex
import shutil
import signal
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import Popen, STDOUT, call
from time import sleep
from typing import Any, List, Tuple

import psutil

from mkchain_utils import log_options

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)

MULTICHAIN_BINDIR: str = None
MULTICHAIN_DATADIR: str = None
if sys.platform == "win32":
    MULTICHAIN_DATADIR = Path(os.environ["APPDATA"]) / "MultiChain"
else:
    MULTICHAIN_DATADIR = Path.home() / ".multichain"


def chain_path(chain_name: str) -> Path:
    return MULTICHAIN_DATADIR / chain_name


def kill_multichaind_processes(chain_name: str):
    def cmdline2str(p: psutil.Process) -> str:
        return ' '.join(shlex.quote(arg) for arg in p.cmdline())

    processes = [p for p in psutil.process_iter(attrs=("cmdline",)) if
                 p.info["cmdline"] and p.info["cmdline"][:2] == ["multichaind", chain_name]]
    for p in processes:
        logger.info(f"Terminating process {p.pid}: {cmdline2str(p)}")
        p.send_signal(signal.SIGTERM)
    gone, alive = psutil.wait_procs(processes, timeout=2)
    for p in alive:
        logger.info(f"Killing process {p.pid}: {cmdline2str(p)}")
        p.kill()


def create_chain(options: Namespace) -> Popen:
    logger.debug(f"create_chain(chain_name={options.chain!r}, warn={options.warn})")
    if MULTICHAIN_BINDIR:
        os.environ["PATH"] = os.pathsep.join([MULTICHAIN_BINDIR, os.environ["PATH"]])
        logger.info(f'>>> Set $PATH={os.environ["PATH"]}')
    if chain_path(options.chain).exists():
        if options.warn:
            message = f"Chain '{options.chain}' already exists. Please choose another name."
            logger.error(message)
            raise ValueError(message)
        kill_multichaind_processes(options.chain)

        logger.info(f">>> Remove {chain_path(options.chain)}")
        shutil.rmtree(chain_path(options.chain))

    cmd = ["multichain-util", "create", options.chain, f"--datadir={MULTICHAIN_DATADIR}"]
    logger.info(f">>> {' '.join(cmd)}")
    call(cmd)
    sleep(1)

    cmd = ["multichaind", options.chain, "-autosubscribe=assets,streams", f"--datadir={MULTICHAIN_DATADIR}"]
    if sys.platform != "win32":
        cmd.append("-daemon")
    if options.debug:
        arg = "-debug"
        if options.debug != "all":
            arg += f"={options.debug}"
        cmd.append(arg)
    logger.info(f">>> {' '.join(cmd)}")
    proc = Popen(cmd, stderr=STDOUT, close_fds=True)
    sleep(5)
    return proc


def create_chain_options_parser() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--datadir", metavar="DIR", help="folder with MultiChain chain data")
    parser.add_argument("--bindir", metavar="DIR", help="folder with MultiChain binaries")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name  (default: %(default)s)"
                             " (will overwrite existing unless -w/--warn is also specified)")
    parser.add_argument("-w", "--warn", action="store_true", help="warn and exit if named chain already exists")
    parser.add_argument("--no-stop", dest="stop", action="store_false", help="don't stop daemon at end of script")
    parser.add_argument("-d", "--debug", nargs="?", default=None, const="all",
                        help="enable debug messages in MultiChain log")
    return parser


def create_chain_update_options(options: Namespace) -> List[Tuple[str, Any]]:
    global MULTICHAIN_BINDIR, MULTICHAIN_DATADIR

    option_display = []
    if options.verbose:
        logger.setLevel(logging.DEBUG)
    if options.datadir:
        MULTICHAIN_DATADIR = options.datadir
        option_display.append(("Data dir", options.datadir))
    if options.bindir:
        MULTICHAIN_BINDIR = options.bindir
        option_display.append(("Binaries", options.bindir))
    option_display.append(("Chain", options.chain))
    option_display.append(("Warn", options.warn))
    option_display.append(("Stop daemon", options.stop))
    option_display.append(("Debug", options.debug))
    return option_display


if __name__ == '__main__':
    def get_options():
        parser = ArgumentParser(description="Create a new chain", parents=[create_chain_options_parser()])
        parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")

        logger.info(f"{module_name} - {parser.description}")
        options = parser.parse_args()
        option_display = create_chain_update_options(options)
        log_options(parser, option_display)

        return options


    def main():
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
        options = get_options()
        create_chain(options)
        return 0


    sys.exit(main())
