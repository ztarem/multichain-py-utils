import logging
import os
import sys
from argparse import ArgumentParser
from time import sleep

from api_utils import adjust_config, api_command, print_command, print_tx, print_tx_id, rpc_api
from create_chain import create_chain, create_chain_options_parser, create_chain_update_options
from mkchain_utils import log_options

logger = logging.getLogger("mkchain")

address1 = None
address2 = None


def create_cache(chain_name: str, data: bytes) -> str:
    logger.debug(f"create_cache(chain_name={chain_name!r})")

    cache_ident = api_command("createbinarycache")
    logger.debug(f"create_cache(chain_name={chain_name!r}, data={data!r}) -> cache_ident={cache_ident!r}")
    api_command("appendbinarycache", cache_ident, data.hex())
    return cache_ident


def create_stream(chain_name: str, stream_name: str, cache_ident: str):
    logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r}, cache_ident={cache_ident!r})")

    restrict_stream_name = stream_name + "_restrict"
    print_tx("create", "stream", restrict_stream_name, {"restrict": "offchain,write"})

    api_command("create", "stream", stream_name, True)
    api_command("publish", stream_name, "key1", os.urandom(100).hex())
    api_command("publish", stream_name, "key2",
                {"text": "Hello there! I am a pretty long string, so it should be truncated on display"})
    api_command("publish", stream_name, "key3", {"cache": cache_ident})
    print_tx("publish", stream_name, "key4", {"text": "hello"}, "offchain")
    api_command("publish", stream_name, [f"key{i}" for i in range(10, 20)],
                {"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}})
    print_command("liststreamitems", stream_name, is_log=False)


def create_asset(chain_name: str, asset_name: str):
    global address1, address2

    logger.debug(f"create_asset(chain_name={chain_name!r}, asset_name={asset_name!r})")

    address1 = api_command("listpermissions", "issue")[0]["address"]
    address2 = api_command("createkeypairs")[0]["address"]
    address3 = api_command("getnewaddress")
    api_command("importaddress", address2, "external")
    api_command("grant", address2, "receive")
    api_command("grant", address3, "send,receive")
    api_command("issue", address1, asset_name, 1000, 1, 0, {"x": ["ex", "X"], "y": "why?"})

    print_tx("sendfrom", address1, address3, {asset_name: 10, "data": {"json": [1, 2, 3]}})
    print_tx("sendfrom", address3, address1, {asset_name: 10})

    print_tx("sendfrom", address1, address2, {asset_name: 50})
    print_tx("sendwithdatafrom", address1, address2, {asset_name: 10}, os.urandom(100).hex())
    print_tx("sendfrom", address1, address2, {asset_name: 10, "data": os.urandom(50).hex()})
    print_tx("sendwithdatafrom", address1, address2, {asset_name: 150},
             {"text": "I just sent 100 asset1 units to the external address I created earlier"})
    print_tx("sendwithdatafrom", address1, address2, {asset_name: 200},
             {"json": {"name": "Zvi Tarem",
                       "message": "I just sent 200 more asset1 units to the same external address I created earlier"}})
    print_tx("issue", address1, {"name": asset_name + "X", "open": True, "restrict": "send"}, 5000, 0.01, 0)


def create_upgrade(chain_name: str):
    logger.debug(f"create_upgrade(chain_name={chain_name!r})")
    print_tx("create", "upgrade", "upgradeStuff", False, {"max-std-element-size": 60000, "max-std-op-drops-count": 7})
    print_tx("approvefrom", address1, "upgradeStuff", True)
    print_command("listupgrades", is_log=False)


def create_paused_transaction(chain_name: str, stream_name: str):
    logger.debug(f"create_paused_transaction(chain_name={chain_name!r})")
    logger.info("Pausing 20 seconds")
    sleep(20)
    tx_id = api_command("publish", stream_name, "key100", {"json": {"message": "Transaction in the mempool"}})
    api_command("pause", "mining")
    sleep(1)
    print_tx_id(tx_id)


def get_options():
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[create_chain_options_parser()])
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    stream_group = parser.add_mutually_exclusive_group()
    stream_group.add_argument("-s", "--stream", metavar="NAME", default="stream1",
                              help="stream name (default: %(default)s)")
    stream_group.add_argument("--no-stream", dest="stream", action="store_const", const=None,
                              help="do not create a stream")
    asset_group = parser.add_mutually_exclusive_group()
    asset_group.add_argument("-a", "--asset", metavar="NAME", default="asset1",
                             help="asset name (default: %(default)s)")
    asset_group.add_argument("--no-asset", dest="asset", action="store_const", const=None,
                             help="do not create an asset")
    parser.add_argument("-p", "--pause", action="store_true", help="Create transaction and pause mining")

    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("Savoir").setLevel(logging.INFO)
    option_display = create_chain_update_options(options)
    option_display.append(("Stream", options.stream))
    option_display.append(("Asset", options.asset))
    option_display.append(("Pause", options.pause))
    log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    logging.getLogger("Savoir").setLevel(logging.WARNING)
    options = get_options()

    create_chain(options)
    adjust_config(logger, options.chain)
    rpc_api(logger, options.chain)
    cache_ident = create_cache(options.chain, "This is a pretty long ASCII chunk in the binary cache".encode())
    if options.stream:
        create_stream(options.chain, options.stream, cache_ident)
    if options.asset:
        create_asset(options.chain, options.asset)
    create_upgrade(options.chain)
    if options.pause:
        create_paused_transaction(options.chain, options.stream)
    return 0


if __name__ == '__main__':
    sys.exit(main())
