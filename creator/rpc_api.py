import logging
import pprint
from time import sleep
from typing import Dict

from Savoir import Savoir

from .chain import Chain


class RpcApi:
    def __init__(self, logger: logging.Logger, chain_name: str, verbose=False):
        self.logger = logger
        self.chain = Chain(self.logger, chain_name)
        self.config = self.load_config("multichain.conf")
        self.params = self.load_config("params.dat")
        self.api = Savoir(self.config["rpcuser"], self.config["rpcpassword"], "localhost",
                          self.params["default-rpc-port"], self.chain.name)
        logging.getLogger("Savoir").setLevel(logging.INFO if verbose else logging.WARNING)

    def load_config(self, config_name: str) -> Dict[str, str]:
        self.logger.debug(f"load_config(config_name={config_name!r})")
        path = self.chain.path / config_name
        config = {}
        with open(str(path)) as f:
            for line in f:
                parts = line.split('#', 1)[0].split('=', 1)
                if len(parts) == 2:
                    config[parts[0].strip()] = parts[1].strip()
        return config

    def adjust_config(self):
        self.logger.debug(f"adjust_config()")
        port = self.params['default-rpc-port']
        self.logger.debug(f"rpc port = {port}")
        with open(str(self.chain.path / "multichain.conf"), "a") as f:
            f.write(f"rpcport={port}\n")

    def command(self, cmd: str, *args, **kwargs):
        return getattr(self.api, cmd)(*args, **kwargs)

    def print_command(self, cmd: str, *args, **kwargs):
        result = self.command(cmd, *args, **kwargs)
        if self.logger.isEnabledFor(logging.DEBUG) and 'error' not in result:
            for line in pprint.pformat(result).split('\n'):
                self.logger.debug(line)
        return result

    def print_tx_id(self, tx_id: str):
        if isinstance(tx_id, str):
            self.print_command("getrawtransaction", tx_id, 1, is_log=False)

    def print_tx(self, cmd: str, *args, **kwargs):
        tx_id = self.command(cmd, *args, **kwargs)
        self.print_tx_id(tx_id)
        return tx_id

    def wait_for_mining(self):
        current_blocks = self.api.getblockcount()
        self.logger.info(f"Current blocks: {current_blocks}, mining:")
        while self.api.getblockcount(is_log=False) <= current_blocks:
            print('.', end='', flush=True)
            sleep(1)
        print()
