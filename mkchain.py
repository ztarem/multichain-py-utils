import logging
import os
import pprint
import shlex
import shutil
import signal
import sys
from argparse import ArgumentParser
from pathlib import Path
from subprocess import Popen, STDOUT
from time import sleep
from typing import Dict

import psutil
from Savoir import Savoir

_logger = logging.getLogger("mkchain")
_mc_bin_folder = None
MULTICHAIN_HOME = Path.home() / ".multichain"

address1 = None
address2 = None


def chain_path(chain_name: str) -> Path:
    return MULTICHAIN_HOME / chain_name


def load_config(chain_name: str, config_name: str) -> Dict[str, str]:
    _logger.debug(f"load_config(chain_name={chain_name}, config_name={config_name})")
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

    procs = [p for p in psutil.process_iter(attrs=("cmdline",)) if p.info["cmdline"][:2] == ["multichaind", chain_name]]
    for p in procs:
        _logger.info(f"Terminating process {p.pid}: {cmdline2str(p)}")
        p.send_signal(signal.SIGTERM)
    gone, alive = psutil.wait_procs(procs, timeout=2)
    for p in alive:
        _logger.info(f"Killing process {p.pid}: {cmdline2str(p)}")
        p.kill()


def create_chain(chain_name: str, warn: bool):
    _logger.debug(f"create_chain(chain_name={chain_name!r}, warn={warn})")
    if _mc_bin_folder:
        os.environ["PATH"] = _mc_bin_folder + os.pathsep + os.environ["PATH"]
        _logger.info(f'>>> Set $PATH={os.environ["PATH"]}')
    if chain_path(chain_name).exists():
        if warn:
            message = f"Chain '{chain_name}' already exists. Please choose another name."
            _logger.error(message)
            raise ValueError(message)
        kill_multichaind_processes(chain_name)

        _logger.info(f">>> Remove {chain_path(chain_name)}")
        shutil.rmtree(chain_path(chain_name))

    cmd = f"multichain-util create {chain_name}"
    _logger.info(f">>> {cmd}")
    os.system(cmd)

    cmd = ["multichaind", chain_name, "-daemon", "-autosubscribe=assets,streams", "-debug"]
    _logger.info(f">>> {' '.join(cmd)}")
    Popen(cmd, stderr=STDOUT, close_fds=True)
    sleep(1)


def adjust_config(chain_name: str):
    _logger.debug(f"adjust_config(chain_name={chain_name!r})")
    params = load_config(chain_name, "params.dat")
    _logger.debug(f"rpc port = {params['default-rpc-port']}")
    with open(chain_path(chain_name) / "multichain.conf", "a") as f:
        f.write(f"rpcport={params['default-rpc-port']}\n")


def create_cache(chain_name: str, api: Savoir, data: bytes) -> str:
    cache_ident = api.createbinarycache()
    _logger.debug(f"create_cache(chain_name={chain_name!r}, data={data!r}) -> cache_ident={cache_ident!r}")
    api.appendbinarycache(cache_ident, data.hex())
    return cache_ident


def create_stream(chain_name: str, api: Savoir, stream_name: str, cache_ident: str):
    _logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r}, cache_ident={cache_ident!r})")
    restrict_stream_name = stream_name + "_restrict"
    tx_id = api.create("stream", restrict_stream_name, {"restrict": "offchain,write"})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))

    api.create("stream", stream_name, True)
    api.publish(stream_name, "key1", os.urandom(500).hex())
    api.publish(stream_name, "key2",
                {"text": "Hello there! I am a pretty long string, so it should be truncated on display"})
    api.publish(stream_name, "key3", {"cache": cache_ident})
    tx_id = api.publish(stream_name, "key4", {"text": "hello"}, "offchain")
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    api.publish(stream_name, [f"key{i}" for i in range(10, 20)],
                {"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.liststreamitems(stream_name))


def create_asset(chain_name: str, api: Savoir, asset_name: str):
    global address1, address2

    _logger.debug(f"create_asset(chain_name={chain_name!r}, asset_name={asset_name!r})")
    address1 = api.listpermissions("issue")[0]["address"]
    address2 = api.createkeypairs()[0]["address"]
    address3 = api.getnewaddress()
    api.importaddress(address2, "external")
    api.grant(address2, "receive")
    api.grant(address3, "send,receive")
    api.issue(address1, asset_name, 1000, 1, 0, {"x": ["ex", "X"], "y": "why?"})

    tx_id = api.sendfrom(address1, address3, {asset_name: 10, "data": {"json": [1, 2, 3]}})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.sendfrom(address3, address1, {asset_name: 10})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))

    tx_id = api.sendfrom(address1, address2, {asset_name: 50})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.sendwithdatafrom(address1, address2, {asset_name: 10}, os.urandom(500).hex())
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.sendfrom(address1, address2, {asset_name: 10, "data": os.urandom(50).hex()})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.sendwithdatafrom(address1, address2, {asset_name: 150},
                                 {"text": "I just sent 100 asset1 units to the external address I created earlier"})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.sendwithdatafrom(address1, address2, {asset_name: 200},
                                 {"json": {"name": "Zvi Tarem",
                                           "message": "I just sent 200 more asset1 units to the same external address"
                                                      " I created earlier"}})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.issue(address1, {"name": asset_name + "X", "open": True, "restrict": "send"}, 5000, 0.01, 0)
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))


def create_upgrade(chain_name: str, api: Savoir):
    _logger.debug(f"create_upgrade(chain_name={chain_name!r})")
    tx_id = api.create("upgrade", "upgradeStuff", False,
                       {"max-std-element-size": 60000, "max-std-op-drops-count": 7})
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
    tx_id = api.approvefrom(address1, "upgradeStuff", True)
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))
        pprint.pprint(api.listupgrades())


def create_paused_transaction(chain_name: str, api: Savoir, stream_name: str):
    _logger.debug(f"create_paused_transaction(chain_name={chain_name!r})")
    _logger.info("Pausing 20 seconds")
    sleep(20)
    tx_id = api.publish(stream_name, "key100", {"json": {"message": "Transaction in the mempool"}})
    api.pause("mining")
    sleep(1)
    if _logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.getrawtransaction(tx_id, 1))


def get_options():
    global _mc_bin_folder

    parser = ArgumentParser(description="Build a new chain with a stream")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcfolder", metavar="DIR", help="folder with multichain binaries")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name  (default: %(default)s)"
                             " (will overwrite existing unless -w/--warn is also specified)")
    parser.add_argument("-w", "--warn", action="store_true", help="warn and exit if chain name already exists")
    parser.add_argument("--nostream", action="store_true", help="do not create a stream")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")
    parser.add_argument("--noasset", action="store_true", help="do not create an asset")
    parser.add_argument("-a", "--asset", metavar="NAME", default="asset1", help="asset name (default: %(default)s)")
    parser.add_argument("-p", "--pause", action="store_true", help="Create transaction and pause mining")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    if options.mcfolder:
        _mc_bin_folder = options.mcfolder

    _logger.info(f"mkchain.py - {parser.description}")
    _logger.info(f"  Chain:     {options.chain}")
    _logger.info(f"  Warn:      {options.warn}")
    _logger.info(f"  Stream:    {'None' if options.nostream else options.stream}")
    _logger.info(f"  Asset:     {'None' if options.noasset else options.asset}")
    _logger.info(f"  Pause:     {options.pause}")
    if options.mcfolder:
        _logger.info(f"  MC Folder: {options.mcfolder}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()

    create_chain(options.chain, options.warn)
    api = rpc_api(options.chain)
    adjust_config(options.chain)
    cache_ident = create_cache(options.chain, api, "This is a pretty long ASCII chunk in the binary cache".encode())
    if not options.nostream:
        create_stream(options.chain, api, options.stream, cache_ident)
    if not options.noasset:
        create_asset(options.chain, api, options.asset)
    create_upgrade(options.chain, api)
    if options.pause:
        create_paused_transaction(options.chain, api, options.stream)
    return 0


if __name__ == '__main__':
    sys.exit(main())
