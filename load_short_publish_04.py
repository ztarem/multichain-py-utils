import logging
import os
import pprint
import random
import string
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from time import sleep

from Savoir import Savoir

from create_chain import adjust_config, create_chain, create_chain_options_parser, create_chain_update_options, rpc_api

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)
CONST_PUBLISH_KEY_SIZE = 16
CONST_PUBLISH_VALUE_SIZE = 32


def print_tx(api: Savoir, tx_id: str):
    if logger.isEnabledFor(logging.DEBUG) and isinstance(tx_id, str):
        for line in pprint.pformat(api.getrawtransaction(tx_id, 1, is_log=False)).split('\n'):
            logger.debug(line)


def rand_string(size: int, is_hex: bool) -> str:
    chars = string.hexdigits if is_hex else string.printable
    return ''.join(random.choices(chars, k=size))


def wait_for_mining(options: Namespace, api: Savoir):
    current_blocks = api.getblockcount()
    logger.info(f"current_blocks: {current_blocks}")
    while api.getblockcount() <= current_blocks:
        sleep(1)


def create_stream(options: Namespace, api: Savoir):
    logger.info(f"create_stream(chain_name={options.chain!r}, stream_name={options.stream!r})")

    api.create("stream", options.stream, True)


def create_tx_filter(options: Namespace, api: Savoir, jsfilter: str):
    logger.info(f"create_tx_filter(chain_name={options.chain!r}, stream_name={options.stream!r})")

    address = api.listaddresses()[0]["address"]
    print_tx(api, api.create("txfilter", "txflt1", {"for": options.stream}, jsfilter))
    print_tx(api, api.approvefrom(address, "txflt1", True))
    # wait_for_mining(options, api)


def create_stream_filter(options: Namespace, api: Savoir, jsfilter: str):
    logger.info(f"create_stream_filter(chain_name={options.chain!r}, stream_name={options.stream!r})")

    address = api.listaddresses()[0]["address"]
    print_tx(api, api.create("streamfilter", "strmflt1", {}, jsfilter))
    print_tx(api, api.approvefrom(address, "strmflt1", {"for": options.stream, "approve": True}))
    # wait_for_mining(options, api)


def create_permissions(_options: Namespace, api: Savoir):
    address = api.getnewaddress()
    print_tx(api, api.grant(address, "send,receive,high1,low3"))


def publish(options: Namespace, api: Savoir):
    logger.info(f"publish(chain_name={options.chain!r}, stream_name={options.stream!r}, repeat={options.repeat})")

    for counter in range(options.repeat):
        key = rand_string(CONST_PUBLISH_KEY_SIZE, is_hex=False)
        value = rand_string(CONST_PUBLISH_VALUE_SIZE, is_hex=True)
        api.publish(options.stream, key, value)
        if not logger.isEnabledFor(logging.DEBUG):
            if counter % 100 == 0:
                print()
                print(f"{counter:8,}: ", end='', flush=True)
            print('.', end='', flush=True)
    print()
    wait_for_mining(options, api)
    logger.info("publish done")


def get_options():
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[create_chain_options_parser()])
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to Python log")
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")

    parser.add_argument("-n", "--repeat", type=int, metavar="N", default=1000,
                        help="number of transactions to publish (default: %(default)s)")

    logger.info(f"{module_name} - {parser.description}")
    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("Savoir").setLevel(logging.INFO)
    create_chain_update_options(options)

    logger.info(f"  Create:    {options.init}")
    logger.info(f"  Stream:    {options.stream}")
    logger.info(f"  Repeats:   {options.repeat:,}")

    return options


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.FileHandler(f"{module_name}.log", mode='w'),
                                  logging.StreamHandler(sys.stdout)])
    logging.getLogger("Savoir").setLevel(logging.WARNING)
    options = get_options()
    good_tx_script = """
var filtertransaction = function () {
var tx = getfiltertransaction();
//var streaminfo = getstreaminfo('stream1');
//if (tx.vout.length < 2)
//{
//    return 'Two transaction outputs required';
//}
};
"""
    good_stream_script = """
var filterstreamitem = function () {
    var tx = getfilterstreamitem();
};
"""

    proc = None
    if options.init:
        proc = create_chain(options)
        adjust_config(options.chain)
    api = rpc_api(options.chain)
    create_permissions(options, api)
    create_stream(options, api)
    create_tx_filter(options, api, good_tx_script)
    create_stream_filter(options, api, good_stream_script)
    publish(options, api)
    if not options.nostop:
        api.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
