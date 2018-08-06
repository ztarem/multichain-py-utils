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
CHAIN_NAME = "chain1"

HEADER = r"""
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
    """ Get the folder containing chain `chain_name`. """
    return MULTICHAIN_HOME / chain_name


def dq(s: str) -> str:
    """ Wrap string `s` in double quotes. Escape double quotes inside the string. """
    s = s.replace('"', r'\"')
    return f'"{s}"'


def sq(s: str) -> str:
    """ Wrap string `s` in single quotes. Escape single quotes inside the string. """
    s = s.replace("'", r"\'")
    return f"'{s}'"


def hex_data(length: int = 50) -> str:
    """ Generate a random string with `length` hexadecimal characters. """
    return ''.join(random.choices(string.hexdigits, k=length))


def text_data(length: int = 50) -> str:
    """ Generate a random multichain text data string with `length` characters. """
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return json.dumps({"text": message})


def json_data(length: int = 50) -> str:
    """ Generate a random multichain JSON data string with a message of `length` characters. """
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return json.dumps({"json": {"list": [1, 2, 3], "message": message}})


def raw_command(*cmd) -> str:
    """ Issue a JSON-API command to chain `CHAIN_NAME`.
    All other positional arguments are concatenated to form the command.
    """
    return f"multichain-cli {CHAIN_NAME} {' '.join(cmd)}"


def assign_command(var_name: str, *cmd) -> str:
    """ Assign the result of a JSON-API command to chain `CHAIN_NAME` to shell variable `var_name`.
    All other positional arguments are concatenated to form the command.
    """
    return f"{var_name}=`{raw_command(*cmd)}`"


def gen_commands(*cmd, var_name: str = None) -> List[str]:
    """ Issue JSON-API commands to chain `CHAIN_NAME`.
    All other positional arguments are concatenated to form the command.

    For example::

        gen_commands('publish', 'stream1', 'key2', '012345')

    Output::

        [
            multichain-cli chain1 publish stream1 key2 "012345"
        ]

    If `var_name` is provided, the result of the command is assigned to a shell variable by that name.

    For example::

        gen_commands('publish', 'stream1', 'key2', '012345', var_name='txout')

    Output::

        [
            txout=`multichain-cli chain1 publish stream1 key2 "012345"`
        ]

    Some command parts may contain the string "{DATA}". In this case, the functions emits separate commands with data
    of the types: hex, text, and JSON. Every occurrence of "{DATA}" is replaced with randomly generated data of the
    correct type.

    For example::

        gen_commands('publish', 'stream1', 'key2', '{DATA}')

    Output::

        [
            multichain-cli chain1 publish stream1 key2 "a2fecf4afc0adfcafa23bccca61d4c2dee776c3d79dcfa07ec",
            multichain-cli chain1 publish stream1 key2 '{"text": "aQCMKovbgkjZbuQnZaCopFIzCbXdJXxMKNLwMOGnBIIJkoXMPa"}',
            multichain-cli chain1 publish stream1 key2 '{"json": {"list": [1, 2, 3], "message": "pvCfvbGLrXFMNoICmfMcINxrJOwXIyTdVbVIOxHXcZVSfuIelV"}}'
        ]
    """
    command_list = []
    cmd_parts = list(cmd)
    data_indexes = [i for i, v in enumerate(cmd_parts) if '{DATA}' in v]
    if data_indexes:
        templates = [cmd_parts[index] for index in data_indexes]
        # for f in (lambda: f'"{hex_data().lower()}"', lambda: text_data(), lambda: json_data()):
        for i, s in enumerate((dq(hex_data().lower()), text_data(), json_data())):
            for data_index, template in zip(data_indexes, templates):
                data = template.replace('{DATA}', s)
                if template != "{DATA}" or i > 0:
                    data = sq(data)
                cmd_parts[data_index] = data
            command_list.append(raw_command(*cmd_parts))
    else:
        if var_name:
            command_list.append(assign_command(var_name, *cmd_parts))
        else:
            command_list.append(raw_command(*cmd_parts))
    return command_list


def build_script(pause: bool) -> List[str]:
    _logger.debug(f"build_script(pause={pause})")
    key_names = [f"key{i}" for i in range(10, 20)]
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')
    multi_items = [
        {"for": "stream1", "keys": ["key3"], "data": {"text": ''.join(random.choices(string.ascii_letters, k=50))}},
        {"for": "stream1", "keys": ["key4"], "data": {"text": ''.join(random.choices(string.ascii_letters, k=50))}},
    ]

    commands = (
            [HEADER.format(MCFOLDER=MULTICHAIN_BIN_DIR.resolve(), CHAIN=CHAIN_NAME,
                           MCPARAMS=str(chain_path(CHAIN_NAME) / "params.dat"),
                           MCCONF=str(chain_path(CHAIN_NAME) / "multichain.conf")).strip()]
            + gen_commands('listpermissions', 'issue', '|', address_sed, var_name='address1')
            + gen_commands('createkeypairs', '|', address_sed, var_name='address2')
            + gen_commands('importaddress', '$address2', 'external')
            + gen_commands('grant', '$address2', 'receive')
            + gen_commands('create', 'stream', 'stream1', 'true')
            + gen_commands('sendfrom', '$address1', '$address2', sq('{"": 0}'))
            + gen_commands('issue', '$address1', sq('{"name": "asset1", "open": true, "restrict": "send"}'),
                           '1000', '1', '0', sq(json_data()))
            + gen_commands('issuemore', '$address1', 'asset1', '1000', '0', sq(json_data()))
            + gen_commands('sendfrom', '$address1', '$address2', sq('{"asset1": 10}'))
            + gen_commands('sendfrom', '$address1', '$address2', '{"asset1": 10, "data": {DATA}}')
            + gen_commands('sendwithdatafrom', '$address1', '$address2', sq('{"asset1": 10}'), '{DATA}')
            + gen_commands('sendwithdatafrom', '$address1', '$address2', sq('{"asset1": 10}'),
                           '{"for": "stream1", "keys": ["key20"], "data": {DATA}}')
            + gen_commands('sendwithdatafrom', '$address1', '$address2', sq('{"asset1": 10}'),
                           '{"for": "stream1", "keys": ["key21"], "options": "offchain", "data": {DATA}}')
            + gen_commands('listassettransactions', 'asset1', 'true')

            + gen_commands('publish', 'stream1', 'key1', '{DATA}')
            + gen_commands('publish', 'stream1', 'key2', '{DATA}', 'offchain')
            + gen_commands('createrawsendfrom', '$address1', dq('{"$address2": 0}'), sq(json.dumps(multi_items)),
                           'send')
            + gen_commands('publish', 'stream1', sq(json.dumps(key_names)), '{DATA}')
            + gen_commands('liststreamitems', 'stream1', 'true')

            # + gen_commands('create', 'stream', 'stream2', 'true', sq(json_data()))
            # + gen_commands('liststreams', '"*"', 'true')

            + gen_commands('grant', '$address2', 'asset1.issue')
            + gen_commands('grant', '$address2', 'stream1.write')
            + gen_commands('listpermissions', '"asset1.*"', '"*"', 'true')
            + gen_commands('listpermissions', '"stream1.*"', '"*"', 'true')

            + gen_commands('create', 'upgrade', 'upgradeStuff', 'false',
                           sq(json.dumps({"max-std-element-size": 60000, "max-std-op-drops-count": 7})))
            + gen_commands('listupgrades')
            + gen_commands('approvefrom', '$address1', 'upgradeStuff', 'true')
            + gen_commands('listupgrades')
    )

    return commands


def write_script(script_name: str, commands: List[str]):
    _logger.debug(f"write_script(script_name={script_name!r})")
    with open(script_name, 'w') as f:
        for cmd in commands:
            f.write(cmd + '\n')
    os.chmod(str(Path(script_name)), Path(script_name).stat().st_mode | stat.S_IXUSR)


def get_options():
    global MULTICHAIN_BIN_DIR, CHAIN_NAME

    parser = argparse.ArgumentParser(description="Build a script that builds a new chain")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcfolder", metavar="DIR", default=MULTICHAIN_BIN_DIR,
                        help="folder with multichain binaries (default: %(default)s)")
    parser.add_argument("-c", "--chain", metavar="NAME", default=CHAIN_NAME,
                        help="chain name (default: %(default)s)")
    parser.add_argument("-s", "--script", metavar="FILE", default="make_chain.sh", help="name of the output script")
    parser.add_argument("-p", "--pause", action="store_true",
                        help="Pause mining so all transactions are on the mempool")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    MULTICHAIN_BIN_DIR = Path(options.mcfolder)
    CHAIN_NAME = options.chain

    _logger.info(f"{module_name} - {parser.description}")
    if options.mcfolder:
        _logger.info(f"  MC Folder: {options.mcfolder}")
    _logger.info(f"  Chain:     {options.chain}")
    _logger.info(f"  Script:    {options.script}")
    _logger.info(f"  Pause:     {options.pause}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()
    commands = build_script(options.pause)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
