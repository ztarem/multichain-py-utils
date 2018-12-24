import logging
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from api_utils import adjust_config, api_command, print_command, print_tx, rand_string, rpc_api, wait_for_mining
from create_chain import create_chain, create_chain_options_parser, create_chain_update_options
from mkchain_utils import log_options

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)
CONST_PUBLISH_KEY_SIZE = 16
CONST_PUBLISH_VALUE_SIZE = 32


def create_tx_filter(options: Namespace, filter_name: str, jsfilter: str):
    logger.info(f"create_tx_filter(chain_name={options.chain!r}, stream_name={options.stream!r})")

    address = api_command("listaddresses")[0]["address"]
    print_tx("create", "txfilter", filter_name, {"for": options.stream}, jsfilter)
    print_tx("approvefrom", address, filter_name, True)
    # wait_for_mining(options, api)


def create_stream_filter(options: Namespace, filter_name: str, jsfilter: str):
    logger.info(f"create_stream_filter(chain_name={options.chain!r}, stream_name={options.stream!r})")

    address = api_command("listaddresses")[0]["address"]
    print_tx("create", "streamfilter", filter_name, {}, jsfilter)
    print_tx("approvefrom", address, filter_name, {"for": options.stream, "approve": True})
    # wait_for_mining(options, api)


def create_permissions(_options: Namespace):
    address = api_command("getnewaddress")
    print_tx("grant", address, "send,receive,high1,low3")


def publish(options: Namespace):
    logger.info(f"publish(chain_name={options.chain!r}, stream_name={options.stream!r}, repeat={options.repeat})")

    for counter in range(options.repeat):
        key = rand_string(CONST_PUBLISH_KEY_SIZE, is_hex=False)
        value = rand_string(CONST_PUBLISH_VALUE_SIZE, is_hex=True)
        api_command("publish", options.stream, key, value)
        if not logger.isEnabledFor(logging.DEBUG):
            if counter % 100 == 0:
                print()
                print(f"{counter:8,}: ", end='', flush=True)
            print('.', end='', flush=True)
    print()
    wait_for_mining(options)
    logger.info("publish done")


def get_options():
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[create_chain_options_parser()])
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to Python log")
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")
    parser.add_argument("-n", "--repeat", type=int, metavar="N", default=1000,
                        help="number of transactions to publish (default: %(default)s)")

    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("Savoir").setLevel(logging.INFO)
    option_display = create_chain_update_options(options)
    option_display.append(("Create", options.init))
    option_display.append(("Stream", options.stream))
    option_display.append(("Repeats", options.repeat))
    log_options(parser, option_display)

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
    if (tx.vout.length < 2) {
        return 'Two transaction outputs required';
    }
};
"""
    good_stream_script = """
function filterstreamitem () {
    var tx = getfilterstreamitem();
    if (tx.vout.length < 2) {
        return 'Two transaction outputs required';
    }
};
"""

    proc = None
    if options.init:
        proc = create_chain(options)
        adjust_config(logger, options.chain)
    rpc_api(logger, options.chain)
    create_permissions(options)
    api_command("create", "stream", options.stream, True)
    create_tx_filter(options, "txflt1", good_tx_script)
    create_stream_filter(options, "strmflt1", good_stream_script)
    filters = print_command("listtxfilters", is_log=False)
    for name in (flt["name"] for flt in filters):
        print_command("getfiltercode", name)
    filters = print_command("liststreamfilters", is_log=False)
    for name in (flt["name"] for flt in filters):
        print_command("getfiltercode", name)
    publish(options)
    if options.stop:
        api_command("stop")
    return 0


if __name__ == '__main__':
    sys.exit(main())
