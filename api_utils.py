import logging
import pprint
import random
import string
from argparse import Namespace
from time import sleep
from typing import Dict

from Savoir import Savoir

from create_chain import chain_path

logger: logging.Logger = None
savoir: Savoir = None


def api_command(cmd: str, *args, **kwargs):
    return getattr(savoir, cmd)(*args, **kwargs)


def print_command(cmd: str, *args, **kwargs):
    result = api_command(cmd, *args, **kwargs)
    if logger.isEnabledFor(logging.DEBUG) and 'error' not in result:
        for line in pprint.pformat(result).split('\n'):
            logger.debug(line)
    return result


def print_tx(cmd: str, *args, **kwargs):
    tx_id = api_command(cmd, *args, **kwargs)
    if isinstance(tx_id, str):
        print_command("getrawtransaction", tx_id, 1, is_log=False)
    return tx_id


def print_tx_id(tx_id: str):
    if isinstance(tx_id, str):
        print_command("getrawtransaction", tx_id, 1, is_log=False)


def wait_for_mining(options: Namespace):
    current_blocks = savoir.getblockcount()
    logger.info(f"current_blocks: {current_blocks}")
    while savoir.getblockcount() <= current_blocks:
        sleep(1)


def load_config(logger_: logging.Logger, chain_name: str, config_name: str) -> Dict[str, str]:
    logger_.debug(f"load_config(chain_name={chain_name}, config_name={config_name})")
    path = chain_path(chain_name) / config_name
    config = {}
    with open(path) as f:
        for line in f:
            parts = line.split('#', 1)[0].split('=', 1)
            if len(parts) == 2:
                config[parts[0].strip()] = parts[1].strip()
    return config


def rpc_api(logger_: logging.Logger, chain_name: str) -> Savoir:
    global logger, savoir

    logger = logger_
    logger.debug(f"rpc_api(chain_name={chain_name!r})")
    config = load_config(logger, chain_name, "multichain.conf")
    params = load_config(logger, chain_name, "params.dat")
    savoir = Savoir(config["rpcuser"], config["rpcpassword"], "localhost", params["default-rpc-port"], chain_name)
    return savoir


def adjust_config(logger_: logging.Logger, chain_name: str):
    logger_.debug(f"adjust_config(chain_name={chain_name!r})")
    params = load_config(logger_, chain_name, "params.dat")
    logger_.debug(f"rpc port = {params['default-rpc-port']}")
    with open(chain_path(chain_name) / "multichain.conf", "a") as f:
        f.write(f"rpcport={params['default-rpc-port']}\n")


def rand_string(size: int, is_hex: bool) -> str:
    chars = string.hexdigits if is_hex else string.printable
    return ''.join(random.choices(chars, k=size))
