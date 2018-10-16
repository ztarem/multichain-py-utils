import json
import logging
import os
import random
import stat
import string
from pathlib import Path
from typing import List

module_name = Path(__file__).stem
_logger = logging.getLogger(module_name)

MULTICHAIN_BIN_DIR = Path("usr", "local", "bin")
MULTICHAIN_HOME = Path.home() / ".multichain"
CHAIN_NAME = "chain1"
PROTOCOL = 20005
DATA_MARKER = '$DATA'
HEADER1 = r"""#!/usr/bin/env bash
# Automatically generated at {NOW}
set -o verbose
export PATH={MCFOLDER}:$PATH
"""
HEADER2 = r"""
multichain-cli {CHAIN} stop
sleep 1
rm -rf ~/.multichain/{CHAIN}
multichain-util create {CHAIN} {PROTOCOL}
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


def j(o: object) -> str:
    """ Prepare object `o` to be passed to a JSON-API command.

    The function converts `o` to JSON and wraps it in single quotes.
    """
    return sq(json.dumps(o))


def hex_data(length: int = 50) -> str:
    """ Generate a random string with `length` hexadecimal characters. """
    return ''.join(random.choices(string.hexdigits, k=length)).lower()


def text_data(length: int = 50) -> object:
    """ Generate a random multichain text data string with `length` characters. """
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return {"text": message}


def json_data(length: int = 50) -> object:
    """ Generate a random multichain JSON data string with a message of `length` characters. """
    message = ''.join(random.choices(string.ascii_letters, k=length))
    return {"json": {"list": [1, 2, 3], "message": message}}


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

    Some command parts may contain the string `DATA_MARKER` = '$DATA'. In this case, the functions emits separate
    commands with data of the types: hex, text, and JSON. Every occurrence of "$DATA" is replaced with randomly
    generated data of the correct type.

    For example::

        gen_commands('sendfrom', '$address1', '$address2', j({"asset1": 10, "data": DATA_MARKER}))
        gen_commands('publish', 'stream1', 'key2', dq(DATA_MARKER))

    Output::

        [
            multichain-cli chain1 sendfrom $address1 $address2 '{"asset1": 10, "data": "feacfbd639b6a6fdcec72f34beca5c4d1fb99a5b456c5ccf1c"}'
            multichain-cli chain1 sendfrom $address1 $address2 '{"asset1": 10, "data": {"text": "oDtGVEBogHOuKnddgxMPclXmerNUNEQTFsJWsZhKXJKLtxFlod"}}'
            multichain-cli chain1 sendfrom $address1 $address2 '{"asset1": 10, "data": {"json": {"list": [1, 2, 3], "message": "edPbujxwdXZlHhzzxnvZcRvTFvextSKiUfctgjWJPXLnMWxJin"}}}'
        ]
        [
            multichain-cli chain1 publish stream1 key2 "a2fecf4afc0adfcafa23bccca61d4c2dee776c3d79dcfa07ec",
            multichain-cli chain1 publish stream1 key2 '{"text": "aQCMKovbgkjZbuQnZaCopFIzCbXdJXxMKNLwMOGnBIIJkoXMPa"}',
            multichain-cli chain1 publish stream1 key2 '{"json": {"list": [1, 2, 3], "message": "pvCfvbGLrXFMNoICmfMcINxrJOwXIyTdVbVIOxHXcZVSfuIelV"}}'
        ]
    """
    command_list = []
    cmd_parts = list(cmd)
    data_indexes = [i for i, v in enumerate(cmd_parts) if DATA_MARKER in v]
    if data_indexes:
        templates = [cmd_parts[index] for index in data_indexes]
        for i, jd in enumerate((hex_data(), text_data(), json_data())):
            for data_index, template in zip(data_indexes, templates):
                add_sq = (template == dq(DATA_MARKER) and i > 0)
                data = template.replace(dq(DATA_MARKER), json.dumps(jd))
                if add_sq:
                    data = sq(data)
                cmd_parts[data_index] = data
            command_list.append(raw_command(*cmd_parts))
    else:
        if var_name:
            command_list.append(assign_command(var_name, *cmd_parts))
        else:
            command_list.append(raw_command(*cmd_parts))
    return command_list


def write_script(script_name: str, commands: List[str]):
    _logger.debug(f"write_script(script_name={script_name!r})")
    with open(script_name, 'w') as f:
        for cmd in commands:
            f.write(cmd + '\n')
    os.chmod(str(Path(script_name)), Path(script_name).stat().st_mode | stat.S_IXUSR)
