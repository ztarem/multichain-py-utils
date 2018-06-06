import logging
import os
import pprint
import stat
import sys
from argparse import ArgumentParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict

from Savoir import Savoir

_logger = logging.getLogger("mkchain")
_api = None
_mc_folder = None


def load_config(chain_name: str, config_name: str) -> Dict[str, str]:
    _logger.debug(f"parse_config(chain_name={chain_name}, config_name={config_name}")
    path = Path.home() / ".multichain" / chain_name / config_name
    config = {}
    with open(path) as f:
        for line in f:
            parts = line.split('#', 1)[0].split('=', 1)
            if len(parts) == 2:
                config[parts[0].strip()] = parts[1].strip()
    return config


def create_api(chain_name: str):
    global _api
    if not _api:
        config = load_config(chain_name, "multichain.conf")
        params = load_config(chain_name, "params.dat")
        _api = Savoir(config["rpcuser"], config["rpcpassword"], "localhost", params["default-rpc-port"], chain_name)


def create_chain(chain_name: str, warn: bool):
    _logger.debug(f"create_chain(chain_name={chain_name!r}, warn={warn})")
    chain_path = Path.home() / ".multichain" / chain_name
    script = ["#! /usr/bin/env bash", ""]
    if _mc_folder:
        script.append(f"export PATH={_mc_folder}:$PATH")
    if chain_path.exists():
        if warn:
            message = f"Chain '{chain_name}' already exists. Please choose another name."
            _logger.error(message)
            raise ValueError(message)
        if os.system("ps -ef | grep multichaind | grep -v grep") != 0:
            cmd = f"multichain-cli {chain_name} stop"
            script += [f'echo ">>> {cmd}"', cmd, "sleep 1"]

        cmd = f"rm -rf {chain_path}"
        script += [f'echo ">>> {cmd}"', cmd]

    cmd = f"multichain-util create {chain_name}"
    script += [f'echo ">>> {cmd}"', cmd]

    cmd = f"multichaind {chain_name} -daemon -autosubscribe=assets,streams -debug=mcapi"
    script += [f'echo ">>> {cmd}"', cmd, "sleep 1"]

    tmpfile = NamedTemporaryFile(mode='w', delete=False)
    _logger.debug(f"Creating {tmpfile.name}:")
    for line in script:
        _logger.debug(f"  {line}")

    tmpfile.write('\n'.join(script) + '\n')
    tmpfile.close()
    os.chmod(tmpfile.name, os.stat(tmpfile.name).st_mode | stat.S_IEXEC)
    os.system(tmpfile.name)
    os.remove(tmpfile.name)


def adjust_config(chain_name: str) -> str:
    _logger.debug(f"adjust_config(chain_name={chain_name!r})")
    params = load_config(chain_name, "params.dat")
    _logger.info(f"rpc port = {params['default-rpc-port']}")
    with open(Path.home() / ".multichain" / chain_name / "multichain.conf", "a") as f:
        f.write(f"rpcport={params['default-rpc-port']}\n")
    return params['default-rpc-port']


def create_stream(chain_name: str, stream_name: str):
    _logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r})")
    _api.create("stream", stream_name, False)
    _api.publish(stream_name, "key1", "11223344aa")
    keys = [f"key{i}" for i in range(10, 20)]
    data = {"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}}
    _api.publish(stream_name, keys, data)
    _api.publish(stream_name, "key4",
                 {"text": "Hello there! I am a pretty long string, so it should be truncated on display"})
    _api.liststreamitems(stream_name)


def create_asset(chain_name: str, asset_name: str):
    _logger.debug(f"create_asset(chain_name={chain_name!r}, asset_name={asset_name!r})")
    result = _api.listpermissions("issue")
    address1 = result[0]["address"]
    result = _api.createkeypairs()
    address2 = result[0]["address"]
    _api.importaddress(address2, "external")
    _api.grant(address2, "receive")
    _api.issue(address1, asset_name, 1000)
    tx_id = _api.sendwithdatafrom(address1, address2, {asset_name: 100},
                                  {"text": "I just sent 100 asset1 units to the external address I created earlier"})
    if _logger.isEnabledFor(logging.DEBUG):
        result = _api.getassettransaction(asset_name, tx_id)
        pprint.pprint(result)
    tx_id = _api.sendwithdatafrom(address1, address2, {asset_name: 200},
                                  {"json": {"name": "Zvi Tarem",
                                            "message": "I just sent 200 more asset1 units to the same external address I created earlier"}})
    if _logger.isEnabledFor(logging.DEBUG):
        result = _api.getassettransaction(asset_name, tx_id)
        pprint.pprint(result)


def get_options():
    global _mc_folder

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

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    if options.mcfolder:
        _mc_folder = Path(options.mcfolder)

    _logger.info(f"mkchain.py - {parser.description}")
    _logger.info(f"  Chain:     {options.chain}")
    _logger.info(f"  Warn:      {options.warn}")
    _logger.info(f"  Stream:    {'None' if options.nostream else options.stream}")
    _logger.info(f"  Asset:     {'None' if options.noasset else options.asset}")
    if options.mcfolder:
        _logger.info(f"  MC Folder: {options.mcfolder}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()

    create_chain(options.chain, options.warn)
    create_api(options.chain)
    rpc_port = adjust_config(options.chain)
    if not options.nostream:
        create_stream(options.chain, options.stream)
    if not options.noasset:
        create_asset(options.chain, options.asset)
    return 0


if __name__ == '__main__':
    sys.exit(main())
