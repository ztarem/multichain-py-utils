import logging
import os
import pprint
import shlex
import shutil
import signal
import sys
from argparse import ArgumentParser
from pathlib import Path
from subprocess import Popen, STDOUT, call
from time import sleep
from typing import Dict

import psutil
from Savoir import Savoir

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)
MULTICHAIN_BIN_DIR = None
if sys.platform == "win32":
    pass
    MULTICHAIN_HOME = Path(os.environ["APPDATA"]) / "MultiChain"
else:
    MULTICHAIN_HOME = Path.home() / ".multichain"

address1 = None
address2 = None


def chain_path(chain_name: str) -> Path:
    return MULTICHAIN_HOME / chain_name


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
    config = load_config(chain_name, "multichain.conf")
    params = load_config(chain_name, "params.dat")
    return Savoir(config["rpcuser"], config["rpcpassword"], "localhost", params["default-rpc-port"], chain_name)


def kill_multichaind_processes(chain_name: str):
    def cmdline2str(p: psutil.Process) -> str:
        return ' '.join(shlex.quote(arg) for arg in p.cmdline())

    # procs = []
    # for p in psutil.process_iter(attrs=("cmdline",)):
    #     if p.info["cmdline"] and p.info["cmdline"][:2] == ["multichaind", chain_name]:
    #         procs.append(p)
    procs = [p for p in psutil.process_iter(attrs=("cmdline",)) if
             p.info["cmdline"] and p.info["cmdline"][:2] == ["multichaind", chain_name]]
    for p in procs:
        logger.info(f"Terminating process {p.pid}: {cmdline2str(p)}")
        p.send_signal(signal.SIGTERM)
    gone, alive = psutil.wait_procs(procs, timeout=2)
    for p in alive:
        logger.info(f"Killing process {p.pid}: {cmdline2str(p)}")
        p.kill()


def create_chain(chain_name: str, warn: bool):
    logger.debug(f"create_chain(chain_name={chain_name!r}, warn={warn})")
    if MULTICHAIN_BIN_DIR:
        os.environ["PATH"] = MULTICHAIN_BIN_DIR + os.pathsep + os.environ["PATH"]
        logger.info(f'>>> Set $PATH={os.environ["PATH"]}')
    if chain_path(chain_name).exists():
        if warn:
            message = f"Chain '{chain_name}' already exists. Please choose another name."
            logger.error(message)
            raise ValueError(message)
        kill_multichaind_processes(chain_name)

        logger.info(f">>> Remove {chain_path(chain_name)}")
        shutil.rmtree(chain_path(chain_name))

    cmd = ["multichain-util", "create", chain_name]
    logger.info(f">>> {' '.join(cmd)}")
    call(cmd)
    sleep(1)

    cmd = ["multichaind", chain_name, "-daemon", "-autosubscribe=assets,streams", "-debug"]
    logger.info(f">>> {' '.join(cmd)}")
    Popen(cmd, stderr=STDOUT, close_fds=True)
    sleep(5)


def adjust_config(chain_name: str):
    logger.debug(f"adjust_config(chain_name={chain_name!r})")
    params = load_config(chain_name, "params.dat")
    logger.debug(f"rpc port = {params['default-rpc-port']}")
    with open(chain_path(chain_name) / "multichain.conf", "a") as f:
        f.write(f"rpcport={params['default-rpc-port']}\n")


def create_cache(chain_name: str, api: Savoir, data: bytes) -> str:
    cache_ident = api.createbinarycache()
    logger.debug(f"create_cache(chain_name={chain_name!r}, data={data!r}) -> cache_ident={cache_ident!r}")
    api.appendbinarycache(cache_ident, data.hex())
    return cache_ident


def create_stream(chain_name: str, api: Savoir, stream_name: str) -> str:
    logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r})")

    api.create("stream", stream_name, True)
    tx_id = api.publish(stream_name, "key1", os.urandom(500).hex())
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.liststreamitems(stream_name))
    return api.getrawtransaction(tx_id)


def test_filter(chain_name: str, api: Savoir, stream_name: str, jsfilter: str, tx: str):
    logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r})")

    api.testtxfilter({"for": stream_name}, jsfilter, tx)


def get_options():
    global MULTICHAIN_BIN_DIR

    parser = ArgumentParser(description="Build a new chain with a stream")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcfolder", metavar="DIR", help="folder with multichain binaries")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name  (default: %(default)s)"
                             " (will overwrite existing unless -w/--warn is also specified)")
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-w", "--warn", action="store_true", help="warn and exit if chain name already exists")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")

    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
    if options.mcfolder:
        MULTICHAIN_BIN_DIR = options.mcfolder

    logger.info(f"{module_name} - {parser.description}")
    logger.info(f"  Chain:     {options.chain}")
    logger.info(f"  Create:    {options.init}")
    logger.info(f"  Warn:      {options.warn}")
    logger.info(f"  Stream:    {options.stream}")
    if options.init and MULTICHAIN_BIN_DIR:
        logger.info(f"  MC Folder: {MULTICHAIN_BIN_DIR}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()

    good_script = """
var filtertransaction = function () {
    var tx = getfiltertransaction();
    //var streaminfo = getstreaminfo('stream1');
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
};
"""

    if options.init:
        create_chain(options.chain, options.warn)
    api = rpc_api(options.chain)
    adjust_config(options.chain)
    tx = create_stream(options.chain, api, options.stream)
    test_filter(options.chain, api, options.stream, good_script, tx)
    api.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
