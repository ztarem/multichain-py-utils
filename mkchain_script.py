import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import mkchain_utils
from creator.chain import Chain
from mkchain_utils import dq, gen_commands, j, json_data, sq, text_data, write_script, HEADER2, PROTOCOL, HEADER1, \
    DATA_MARKER

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)


def build_script(chain: Chain) -> List[str]:
    logger.debug("build_script()")
    key_names = [f"key{i}" for i in range(10, 20)]
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')
    multi_items = [{"for": "stream1", "keys": [f"key{i}"], "data": text_data()} for i in (3, 4, 5)]

    commands = [HEADER1.format(MCFOLDER=Path(chain.bindir).resolve(), NOW=datetime.now()),
                HEADER2.format(
                    CHAIN=chain.name,
                    PROTOCOL=PROTOCOL,
                    DEBUG="-debug" if chain.debug else "",
                    MCPARAMS=str(chain.path / "params.dat"),
                    MCCONF=str(chain.path / "multichain.conf")).strip()]
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
    commands.extend(gen_commands('sendfrom', '$address1', '$address2',
                                 j({"asset1": 10, "data": DATA_MARKER})))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2',
                                 j({"asset1": 10}), dq(DATA_MARKER)))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2', j({"asset1": 10}),
                                 j({"for": "stream1", "keys": ["key20"], "data": DATA_MARKER})))
    commands.extend(gen_commands('sendwithdatafrom', '$address1', '$address2', j({"asset1": 10}),
                                 j({"for": "stream1", "keys": ["key21"], "options": "offchain",
                                    "data": DATA_MARKER})))
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


def get_options(chain: Chain):
    parser = argparse.ArgumentParser(description="Build a script that builds a new chain",
                                     parents=[chain.options_parser()])
    parser.add_argument("-s", "--script", metavar="FILE", default="make_chain.sh", help="name of the output script")
    parser.add_argument("-p", "--protocol", metavar="VER", type=int, default=PROTOCOL,
                        help="protocol version (default: %(default)s)")

    options = parser.parse_args()

    mkchain_utils.CHAIN_NAME = options.chain
    mkchain_utils.PROTOCOL = options.protocol

    option_display = chain.process_options(options)
    option_display.append(("Script file", options.script))
    option_display.append(("Protocol", options.protocol))
    chain.log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    chain = Chain(logger)
    options = get_options(chain)
    commands = build_script(chain)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
