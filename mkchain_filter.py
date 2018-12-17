import logging
import os
import pprint
import sys
from argparse import ArgumentParser
from pathlib import Path

from Savoir import Savoir

from create_chain import adjust_config, create_chain, create_chain_options_parser, create_chain_update_options, rpc_api

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)


def print_tx(api: Savoir, tx_id: str):
    if logger.isEnabledFor(logging.DEBUG) and isinstance(tx_id, str):
        pprint.pprint(api.getrawtransaction(tx_id, 1, is_log=False))


def create_stream(chain_name: str, api: Savoir, stream_name: str) -> str:
    logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r})")

    api.create("stream", stream_name, True)
    tx_id = api.publish(stream_name, "key1", os.urandom(500).hex())
    print_tx(api, tx_id)
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.liststreamitems(stream_name))
    return api.getrawtransaction(tx_id)


def test_filter(chain_name: str, api: Savoir, stream_name: str, jsfilter: str, tx: str):
    logger.debug(f"test_filter(chain_name={chain_name!r}, stream_name={stream_name!r})")

    result = api.testtxfilter({"for": stream_name}, jsfilter, tx)
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(result)


def get_options():
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[create_chain_options_parser()])
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")

    logger.info(f"{module_name} - {parser.description}")
    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("Savoir").setLevel(logging.INFO)
    create_chain_update_options(options)

    logger.info(f"  Create: {options.init}")
    logger.info(f"  Stream: {options.stream}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    logging.getLogger("Savoir").setLevel(logging.WARNING)
    options = get_options()

    good_script = """
var filtertransaction = function () {
    var tx = getfiltertransaction();
    //var streaminfo = getstreaminfo('stream1');
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
};
"""
    bad_script = """
function filtertransaction()
{
    var tx = getfiltertransaction();
    if (tx.version != 1) {
        return "typeof(tx.version)=" + typeof(tx.version) + " tx.version=" + tx.version;
    }
}
"""
    infinite_script = "var filtertransaction = function () { while (true) {}; };"

    if options.init:
        create_chain(options)
    api = rpc_api(options.chain)
    adjust_config(options.chain)
    tx = create_stream(options.chain, api, options.stream)
    test_filter(options.chain, api, options.stream, good_script, tx)
    test_filter(options.chain, api, options.stream, bad_script, tx)
    for i in range(5):
        # test_filter(options.chain, api, options.stream, infinite_script, tx)
        api.testtxfilter({"for": options.stream}, infinite_script, tx)
    api.stop()
    return 0


if __name__ == '__main__':
    sys.exit(main())
