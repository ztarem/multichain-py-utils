import argparse
import logging
import sys
from pathlib import Path
from typing import List

import mkchain_utils
from mkchain_utils import CHAIN_NAME, DATA_MARKER, HEADER, MULTICHAIN_BIN_DIR, chain_path, dq, gen_commands, j, \
    json_data, sq, text_data, write_script

module_name = Path(__file__).stem
_logger = logging.getLogger(module_name)


def build_script(pause: bool) -> List[str]:
    _logger.debug("build_script()")
    key_names = [f"key{i}" for i in range(10, 20)]
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')
    multi_items = [{"for": "stream1", "keys": [f"key{i}"], "data": text_data()} for i in (3, 4, 5)]

    commands = [HEADER.format(MCFOLDER=MULTICHAIN_BIN_DIR.resolve(), CHAIN=CHAIN_NAME,
                              PROTOCOL=mkchain_utils.PROTOCOL,
                              MCPARAMS=str(chain_path(CHAIN_NAME) / "params.dat"),
                              MCCONF=str(chain_path(CHAIN_NAME) / "multichain.conf")).strip()]
    commands.extend(gen_commands('listpermissions', 'issue', '|', address_sed, var_name='address1'))
    commands.extend(gen_commands('createkeypairs', '|', address_sed, var_name='address2'))
    commands.extend(gen_commands('importaddress', '$address2', 'external'))
    commands.extend(gen_commands('grant', '$address2', 'receive'))
    commands.extend(gen_commands('create', 'stream', 'stream1', 'true'))
    commands.extend(gen_commands('sendfrom', '$address1', '$address2', j({"": 0})))
    commands.extend(gen_commands('issue', '$address1', j({"name": "asset1", "open": True, "restrict": "send"}),
                                 '1000', '1', '0', j(json_data())))
    commands.extend(gen_commands('issuemore', '$address1', 'asset1', '1000', '0', j(json_data())))
    commands.extend(gen_commands('sendfrom', '$address1', '$address2', j({"asset1": 10})))
    commands.extend(gen_commands('sendfrom', '$address1', '$address2', j({"asset1": 10, "data": DATA_MARKER})))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2', j({"asset1": 10}), dq(DATA_MARKER)))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2', j({"asset1": 10}),
                                 j({"for": "stream1", "keys": ["key20"], "data": DATA_MARKER})))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2', j({"asset1": 10}),
                                 j({"for": "stream1", "keys": ["key21"], "options": "offchain", "data": DATA_MARKER})))
    commands.extend(gen_commands('listassettransactions', 'asset1', 'true'))

    commands.extend(gen_commands('publish', 'stream1', 'key1', dq(DATA_MARKER)))
    commands.extend(gen_commands('publish', 'stream1', 'key2', dq(DATA_MARKER), 'offchain'))
    commands.extend(gen_commands('createrawsendfrom', '$address1', dq('{"$address2": 0}'), j(multi_items), 'send'))
    commands.extend(gen_commands('publish', 'stream1', j(key_names), dq(DATA_MARKER)))
    commands.extend(gen_commands('liststreamitems', 'stream1', 'true'))

    # commands.extend(gen_commands('create', 'stream', 'stream2', 'true', j(json_data())))
    # commands.extend(gen_commands('liststreams', '"*"', 'true'))

    commands.extend(gen_commands('grant', '$address2', 'asset1.issue'))
    commands.extend(gen_commands('grant', '$address2', 'stream1.write'))
    commands.extend(gen_commands('listpermissions', '"asset1.*"', '"*"', 'true'))
    commands.extend(gen_commands('listpermissions', '"stream1.*"', '"*"', 'true'))

    commands.extend(gen_commands('create', 'upgrade', 'upgradeStuff', 'false',
                                 j({"max-std-element-size": 60000, "max-std-op-drops-count": 7})))
    commands.extend(gen_commands('listupgrades'))
    commands.extend(gen_commands('approvefrom', '$address1', 'upgradeStuff', 'true'))
    commands.extend(gen_commands('listupgrades'))

    return commands


def get_options():
    parser = argparse.ArgumentParser(description="Build a script that builds a new chain")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcbin", metavar="DIR", default=mkchain_utils.MULTICHAIN_BIN_DIR,
                        help="folder with multichain binaries (default: %(default)s)")
    parser.add_argument("--mcchain", metavar="DIR", default =mkchain_utils.MULTICHAIN_HOME,
                        help="base folder for multichain chain data (default: %(default)s)")
    parser.add_argument("-c", "--chain", metavar="NAME", default=mkchain_utils.CHAIN_NAME,
                        help="chain name (default: %(default)s)")
    parser.add_argument("-s", "--script", metavar="FILE", default="make_chain.sh", help="name of the output script")
    parser.add_argument("-p", "--protocol", metavar="VER", type=int, default=mkchain_utils.PROTOCOL,
                        help="protocol version (default: %(default)s)")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    mkchain_utils.CHAIN_NAME = options.chain
    mkchain_utils.PROTOCOL = options.protocol

    _logger.info(f"{module_name} - {parser.description}")
    if options.mcbin != mkchain_utils.MULTICHAIN_BIN_DIR:
        mkchain_utils.MULTICHAIN_BIN_DIR = Path(options.mcbin)
        _logger.info(f"  MC Folder:   {options.mcbin}")
    if options.mcchain != mkchain_utils.MULTICHAIN_HOME:
        mkchain_utils.MULTICHAIN_HOME = options.mcchain
        _logger.info(f"  MC Chains:   {options.mcchain}")
    _logger.info(f"  Chain name:  {options.chain}")
    _logger.info(f"  Script file: {options.script}")
    _logger.info(f"  Protocol:    {mkchain_utils.PROTOCOL}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()
    commands = build_script(options.pause)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
