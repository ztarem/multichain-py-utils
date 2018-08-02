import argparse
import json
import logging
import os
import random
import stat
import string
import sys
from pathlib import Path
from typing import List

module_name = Path(__file__).stem
_logger = logging.getLogger(module_name)
MULTICHAIN_BIN_DIR = Path("usr", "local", "bin")
MULTICHAIN_HOME = Path.home() / ".multichain"

header = r"""
#!/usr/bin/env bash
export PATH={MCFOLDER}:${{PATH}}
multichain-cli {CHAIN} stop
sleep 1
rm -rf ~/.multichain/{CHAIN}
multichain-util create {CHAIN}
sleep 1
multichaind {CHAIN} -daemon -autosubscribe=assets,streams -debug
sleep 1
rpc_port=`sed -n -E 's/.*default-rpc-port\s*=\s*(\w+)\s*.*/\1/p' {MCPARAMS}`
echo "rpcport=$rpc_port"
echo "rpcport=$rpc_port" >> {MCCONF}
"""


def chain_path(chain_name: str) -> Path:
    return MULTICHAIN_HOME / chain_name


def dq(s: str) -> str:
    s = s.replace('"', r'\"')
    return f'"{s}"'


def sq(s: str) -> str:
    s = s.replace("'", r"\'")
    return f"'{s}'"


def hex_data(length: int = 50) -> str:
    return ''.join(random.choices(string.hexdigits, k=length))


def text_data(length: int = 50) -> str:
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return json.dumps({"text": message})


def json_data(length: int = 50) -> str:
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return json.dumps(
        {"json": {"list": [1, 2, 3], "message": message}})


def raw_command(chain_name: str, *cmd) -> str:
    return f"multichain-cli {chain_name} {' '.join(cmd)}"


def assign_command(chain_name: str, var_name: str, *cmd) -> str:
    return f"{var_name}=`{raw_command(chain_name, *cmd)}`"


def raw_data_commands(chain_name: str, *cmd) -> List[str]:
    cmd_list = list(cmd)
    data_index = next(i for i, v in enumerate(cmd_list) if '{DATA}' in v)
    template = cmd_list[data_index]
    data_list = []
    for f in (lambda: f'"{hex_data().lower()}"', lambda: text_data(), lambda: json_data()):
        data = template.replace('{DATA}', f())
        if not all(c in string.hexdigits for c in data[1:-1]):
            data = sq(data)
        cmd_list[data_index] = data
        data_list.append(raw_command(chain_name, *cmd_list))
    return data_list


def build_script(chain_name: str) -> List[str]:
    _logger.debug(f"build_script(chain_name={chain_name!r})")
    key_names = [f"key{i}" for i in range(10, 20)]
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')

    return \
        [
            header.format(MCFOLDER=MULTICHAIN_BIN_DIR.resolve(), CHAIN=chain_name,
                          MCPARAMS=str(chain_path(chain_name) / "params.dat"),
                          MCCONF=str(chain_path(chain_name) / "multichain.conf")).strip(),
            assign_command(chain_name, 'cache_ident', 'createbinarycache'),
            raw_command(chain_name, "appendbinarycache", "$cache_ident",
                        b'This is a pretty long ASCII chunk in the binary cache'.hex()),
            assign_command(chain_name, 'txid', 'create', 'stream', 'stream1_restrict',
                           sq('{"restrict": "offchain,write"}')),
            raw_command(chain_name, 'getrawtransaction', '$txid', '1'),
            raw_command(chain_name, 'create', 'stream', 'stream1', 'true'),
            raw_command(chain_name, 'publish', 'stream1', 'key1', dq('{"cache": "$cache_ident"}')),
        ] + \
        raw_data_commands(chain_name, 'publish', 'stream1', 'key2', '{DATA}') + \
        raw_data_commands(chain_name, 'publish', 'stream1', 'key3', '{DATA}', 'offchain') + \
        raw_data_commands(chain_name, 'publish', 'stream1', sq(json.dumps(key_names)), '{DATA}') + \
        [
            raw_command(chain_name, 'liststreamitems', 'stream1', 'true'),
            assign_command(chain_name, 'address1', 'listpermissions', 'issue', '|', address_sed),
            assign_command(chain_name, 'address2', 'createkeypairs', '|', address_sed),
            assign_command(chain_name, 'address3', 'getnewaddress'),
            raw_command(chain_name, 'importaddress', '$address2', 'external'),
            raw_command(chain_name, 'grant', '$address2', 'receive'),
            raw_command(chain_name, 'grant', '$address3', 'send,receive'),
            raw_command(chain_name, 'issue', '$address1', 'asset1', '1000', '1', '0',
                        sq('{"x": ["ex", "X"], "y": "why?"}')),
            raw_command(chain_name, 'sendfrom', '$address1', '$address3',
                        sq('{"asset1": 10, "data": {"json": [1, 2, 3]}}')),
            raw_command(chain_name, 'sendfrom', '$address3', '$address1', sq('{"asset1": 10}')),
            raw_command(chain_name, 'sendfrom', '$address1', '$address2', sq('{"asset1": 50}')),
        ] + \
        raw_data_commands(chain_name, 'sendwithdatafrom', '$address1', '$address2', sq('{"asset1": 10}'), '{DATA}') + \
        raw_data_commands(chain_name, 'sendfrom', '$address1', '$address2', '{"asset1": 10, "data": {DATA}}') + \
        [
            raw_command(chain_name, 'issue', '$address1',
                        sq('{"name": "asset1X", "open": true, "restrict": "send"}'), '5000', '0.01', '0'),
        ]


def write_script(script_name: str, commands: List[str]):
    _logger.debug(f"write_script(script_name={script_name!r})")
    with open(script_name, 'w') as f:
        for cmd in commands:
            f.write(cmd + '\n')
    os.chmod(str(Path(script_name)), Path(script_name).stat().st_mode | stat.S_IXUSR)


def get_options():
    global MULTICHAIN_BIN_DIR

    parser = argparse.ArgumentParser(description="Build a script that builds a new chain")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcfolder", metavar="DIR", default=MULTICHAIN_BIN_DIR,
                        help="folder with multichain binaries (default: %(default)s)")
    parser.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                        help="chain name (default: %(default)s)")
    parser.add_argument("-s", "--script", metavar="FILE", default="make_chain.sh", help="name of the output script")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    if options.mcfolder:
        MULTICHAIN_BIN_DIR = Path(options.mcfolder)

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
