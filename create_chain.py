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
from typing import Dict

import psutil
from Savoir import Savoir

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)

MULTICHAIN_BINDIR = None
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


# def create_chain(chain_name: str, warn: bool, custom_datadir: bool, verbose: bool):
def create_chain(options: Namespace):
    logger.debug(f"create_chain(chain_name={options.chain!r}, warn={options.warn})")
    if MULTICHAIN_BINDIR:
        os.environ["PATH"] = MULTICHAIN_BINDIR + os.pathsep + os.environ["PATH"]
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

    cmd = ["multichaind", options.chain, "-daemon", "-autosubscribe=assets,streams", f"--datadir={MULTICHAIN_DATADIR}"]
    if options.verbose:
        cmd.append("-debug")
    logger.info(f">>> {' '.join(cmd)}")
    Popen(cmd, stderr=STDOUT, close_fds=True)
    sleep(2)


def create_chain_options_parser() -> ArgumentParser:
    parser = ArgumentParser(add_help=False)
    parser.add_argument("--datadir", metavar="DIR", help="folder with MultiChain chain data")
    parser.add_argument("--bindir", metavar="DIR", help="folder with MultiChain binaries")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name  (default: %(default)s)"
                             " (will overwrite existing unless -w/--warn is also specified)")
    parser.add_argument("-w", "--warn", action="store_true", help="warn and exit if chain name already exists")
    parser.add_argument("--nostop", action="store_true", help="don't stop daemon at end of script")
    return parser


def create_chain_update_options(options: Namespace):
    global MULTICHAIN_BINDIR, MULTICHAIN_DATADIR

    if options.verbose:
        logger.setLevel(logging.DEBUG)
    if options.datadir:
        MULTICHAIN_DATADIR = options.datadir
        logger.info(f"  Data dir: {options.datadir}")
    if options.bindir:
        MULTICHAIN_BINDIR = options.bindir
        logger.info(f"  Binaries: {options.bindir}")
    logger.info(f"  Chain:    {options.chain}")
    logger.info(f"  Warn:     {options.warn}")
    logger.info(f"  Stop:     {not options.nostop}")


def load_config(chain_name: str, config_name: str) -> Dict[str, str]:
    logger.debug(f"load_config(chain_name={chain_name}, config_name={config_name})")
    path = chain_path(chain_name) / config_name
    config = {}
    with open(path) as f:
        for line in f:
            parts = line.split('#', 1)[0].split('=', 1)
            if len(parts) == 2:
                config[parts[0].strip()] = parts[1].strip()
    return config


def rpc_api(chain_name: str) -> Savoir:
    logger.debug(f"rpc_api(chain_name={chain_name!r})")
    config = load_config(chain_name, "multichain.conf")
    params = load_config(chain_name, "params.dat")
    return Savoir(config["rpcuser"], config["rpcpassword"], "localhost", params["default-rpc-port"], chain_name)


def adjust_config(chain_name: str):
    logger.debug(f"adjust_config(chain_name={chain_name!r})")
    params = load_config(chain_name, "params.dat")
    logger.debug(f"rpc port = {params['default-rpc-port']}")
    with open(chain_path(chain_name) / "multichain.conf", "a") as f:
        f.write(f"rpcport={params['default-rpc-port']}\n")


if __name__ == '__main__':
    def get_options():
        parser = ArgumentParser(description="Create a new chain", parents=[create_chain_options_parser()])
        parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")

        logger.info(f"{module_name} - {parser.description}")
        options = parser.parse_args()
        create_chain_update_options(options)

        return options


    def main():
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
        options = get_options()
        create_chain(options)
        return 0


    sys.exit(main())
