import logging
import sys
from argparse import ArgumentParser
from pathlib import Path

from creator.chain import Chain
from creator.rpc_api import RpcApi
from creator.utils import rand_string

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)
CONST_PUBLISH_KEY_SIZE = 16
CONST_PUBLISH_VALUE_SIZE = 32


def create_tx_filter(api: RpcApi, stream_name: str, filter_name: str, jsfilter: str):
    address = api.command("listaddresses")[0]["address"]
    api.print_tx("create", "txfilter", filter_name, {"for": stream_name}, jsfilter)
    api.print_tx("approvefrom", address, filter_name, True)
    # wait_for_mining(options, api)


def create_stream_filter(api: RpcApi, stream_name: str, filter_name: str, jsfilter: str):
    address = api.command("listaddresses")[0]["address"]
    api.print_tx("create", "streamfilter", filter_name, {}, jsfilter)
    api.print_tx("approvefrom", address, filter_name, {"for": stream_name, "approve": True})
    # wait_for_mining(options, api)


def create_permissions(api: RpcApi):
    address = api.command("getnewaddress")
    api.print_tx("grant", address, "send,receive,high1,low3")


def publish(api: RpcApi, repeats: int, stream_name: str):
    for counter in range(repeats):
        key = rand_string(CONST_PUBLISH_KEY_SIZE, is_hex=False)
        value = rand_string(CONST_PUBLISH_VALUE_SIZE, is_hex=True)
        api.command("publish", stream_name, key, value)
        if not logger.isEnabledFor(logging.DEBUG):
            if counter % 100 == 0:
                print()
                print(f"{counter:8,}: ", end='', flush=True)
            print('.', end='', flush=True)
    print()
    api.wait_for_mining()
    logger.info("publish done")


def get_options(chain: Chain):
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[chain.options_parser()])
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")
    parser.add_argument("-n", "--repeats", type=int, metavar="N", default=1000,
                        help="number of transactions to publish (default: %(default)s)")

    options = parser.parse_args()

    option_display = chain.process_options(options)
    option_display.append(("Create", options.init))
    option_display.append(("Stream", options.stream))
    option_display.append(("Repeats", options.repeats))
    chain.log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s",
                        handlers=[logging.FileHandler(f"{module_name}.log", mode='w'),
                                  logging.StreamHandler(sys.stdout)])
    chain = Chain(logger)
    options = get_options(chain)

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

    _proc = None
    if options.init:
        _proc = chain.create()
        api = RpcApi(logger, chain.name, options.verbose)
        api.adjust_config()
    else:
        api = RpcApi(logger, chain.name, options.verbose)
    create_permissions(api)
    api.command("create", "stream", options.stream, True)
    create_tx_filter(api, options.stream, "txflt1", good_tx_script)
    create_stream_filter(api, options.stream, "strmflt1", good_stream_script)

    filters = api.print_command("listtxfilters", is_log=False)
    for name in (flt["name"] for flt in filters):
        api.print_command("getfiltercode", name, is_log=False)

    filters = api.print_command("liststreamfilters", is_log=False)
    for name in (flt["name"] for flt in filters):
        api.print_command("getfiltercode", name, is_log=False)

    publish(api, options.repeats, options.stream)
    if chain.stop:
        api.command("stop")
    return 0


if __name__ == '__main__':
    sys.exit(main())
