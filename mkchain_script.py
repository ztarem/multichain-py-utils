import argparse
import json
import logging
import os
import stat
import sys
from pathlib import Path
from typing import List

module_name = Path(__file__).stem
_logger = logging.getLogger(module_name)
_mc_bin_folder = Path("usr", "local", "bin")
MULTICHAIN_HOME = Path.home() / ".multichain"

header = """
#!/usr/bin/env bash
export PATH={mcfolder}:${{PATH}}
multichain-cli {chain} stop
sleep 1
rm -rf ~/.multichain/{chain}
multichain-util create {chain}
sleep 1
multichaind {chain} -daemon -autosubscribe=assets,streams -debug
sleep 1
"""


def chain_path(chain_name: str) -> Path:
    return MULTICHAIN_HOME / chain_name


def raw_command(chain_name: str, *cmd) -> str:
    return f"multichain-cli {chain_name} {' '.join(cmd)}"


def assign_command(chain_name: str, var_name: str, *cmd) -> str:
    return f"{var_name}=`{raw_command(chain_name, *cmd)}`"


def build_script(chain_name: str) -> List[str]:
    _logger.debug(f"build_script( chain_name={chain_name!r}")
    appendbinarycache_cmd = ["appendbinarycache", "$cache_ident",
                             b'This is a pretty long ASCII chunk in the binary cache'.hex()]
    keys = [f"key{i}" for i in range(10, 20)]
    address_sed = r"""sed -n -E 's/.*"address"\s*:\s*"(\w+)".*/\1/p'"""

    return [
        header.format(mcfolder=_mc_bin_folder, chain=chain_name).strip(),
        assign_command(chain_name, 'cache_ident', 'createbinarycache'),
        raw_command(chain_name, *appendbinarycache_cmd),
        assign_command(chain_name, 'txid', 'create', 'stream', 'stream1_restrict',
                       '\'{"restrict": "offchain,write"}\''),
        raw_command(chain_name, 'getrawtransaction', '$txid', '1'),
        raw_command(chain_name, 'create', 'stream', 'stream1', 'true'),
        raw_command(chain_name, 'publish', 'stream1', 'key1', os.urandom(100).hex()),
        raw_command(chain_name, 'publish', 'stream1', 'key2',
                    '\'{"text": "Hello there! I am a pretty long string, so it should be truncated on display"}\''),
        raw_command(chain_name, 'publish', 'stream1', 'key3', r'"{\"cache\": \"$cache_ident\"}"'),
        raw_command(chain_name, 'publish', 'stream1', 'key4', '\'{"text": "hello"}\'', 'offchain'),
        raw_command(chain_name, 'publish', 'stream1', f"'{json.dumps(keys)}'",
                    '\'{"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}}\''),
        raw_command(chain_name, 'liststreamitems', 'stream1'),
        assign_command(chain_name, 'address1', 'listpermissions', 'issue', '|', address_sed),
        assign_command(chain_name, 'address2', 'createkeypairs', '|', address_sed),
        assign_command(chain_name, 'address3', 'getnewaddress'),
        raw_command(chain_name, 'importaddress', '$address2', 'external'),
        raw_command(chain_name, 'grant', '$address2', 'receive'),
        raw_command(chain_name, 'grant', '$address3', 'send,receive'),
        raw_command(chain_name, 'issue', '$address1', 'asset1', '1000', '1', '0',
                    '\'{"x": ["ex", "X"], "y": "why?"}\''),
        raw_command(chain_name, 'sendfrom', '$address1', '$address3',
                    '\'{"asset1": 10, "data": {"json": [1, 2, 3]}}\''),
        raw_command(chain_name, 'sendfrom', '$address3', '$address1', '\'{"asset1": 10}\''),
        raw_command(chain_name, 'sendfrom', '$address1', '$address2', '\'{"asset1": 50}\''),
        raw_command(chain_name, 'sendwithdatafrom', '$address1', '$address2', '\'{"asset1": 10}\'',
                    os.urandom(100).hex()),
        raw_command(chain_name, 'sendfrom', '$address1', '$address2',
                    '\'{"asset1": 10, "data": "' + os.urandom(50).hex() + '"}\''),
        raw_command(chain_name, 'sendwithdatafrom', '$address1', '$address2', '\'{"asset1": 150}\'',
                    '\'{"text": "I just sent 100 asset1 units to the external address I created earlier"}\''),
        raw_command(chain_name, 'sendwithdatafrom', '$address1', '$address2', '\'{"asset1": 200}\'',
                    '\'{"json": {"name": "Zvi Tarem",'
                    '"message": "I just sent 200 more asset1 units to the same external address'
                    ' I created earlier"}}\''),
        raw_command(chain_name, 'issue', '$address1', '\'{"name": "asset1X", "open": true, "restrict": "send"}\'',
                    '5000', '0.01', '0'),
    ]


def write_script(script_name: str, commands: List[str]):
    _logger.debug(f"write_script(script_name={script_name!r}")
    with open(script_name, 'w') as f:
        for cmd in commands:
            f.write(cmd + '\n')
    os.chmod(str(Path(script_name)), Path(script_name).stat().st_mode | stat.S_IXUSR)


def get_options():
    global _mc_bin_folder

    parser = argparse.ArgumentParser(description="Build a script that builds a new chain")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcfolder", metavar="DIR", help="folder with multichain binaries")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name  (default: %(default)s)")
    parser.add_argument("-s", "--script", metavar="FILE", default="make_chain.sh", help="name of the output script")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    if options.mcfolder:
        _mc_bin_folder = Path(options.mcfolder)

    _logger.info(f"{module_name} - {parser.description}")
    if options.mcfolder:
        _logger.info(f"  MC Folder: {options.mcfolder}")
    _logger.info(f"  Chain:     {options.chain}")
    _logger.info(f"  Script:    {options.script}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()
    commands = build_script(options.chain)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
