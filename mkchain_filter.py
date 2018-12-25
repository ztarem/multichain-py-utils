import logging
import os
import sys
from argparse import ArgumentParser
from pathlib import Path

from creator.chain import Chain
from creator.rpc_api import RpcApi

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)


def create_stream(api: RpcApi, stream_name: str) -> str:
    logger.debug(f"create_stream(stream_name={stream_name!r})")

    api.command("create", "stream", stream_name, True)
    tx_id = api.print_tx("publish", stream_name, "key1", os.urandom(500).hex())
    api.print_command("liststreamitems", stream_name)
    return api.command("getrawtransaction", tx_id)


def get_options(chain: Chain):
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[chain.options_parser()])
    parser.add_argument("-i", "--init", action="store_true", help="(re)create a chain")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")

    options = parser.parse_args()

    option_display = chain.process_options(options)
    option_display.append(("Create", options.init))
    option_display.append(("Stream", options.stream))
    chain.log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    logging.getLogger("Savoir").setLevel(logging.WARNING)
    chain = Chain(logger)
    options = get_options(chain)

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

    _proc = None
    if options.init:
        _proc = chain.create()
        api = RpcApi(logger, chain.name, options.verbose)
        api.adjust_config()
    else:
        api = RpcApi(logger, chain.name, options.verbose)
    tx = create_stream(api, options.stream)
    api.print_command("testtxfilter", {"for": options.stream}, good_script, tx)
    api.print_command("testtxfilter", {"for": options.stream}, bad_script, tx)
    for i in range(5):
        api.command("testtxfilter", {"for": options.stream}, infinite_script, tx)
    api.command("stop")
    return 0


if __name__ == '__main__':
    sys.exit(main())
