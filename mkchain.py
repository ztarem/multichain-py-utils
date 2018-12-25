import logging
import os
import sys
from argparse import ArgumentParser
from time import sleep

from creator.chain import Chain
from creator.rpc_api import RpcApi

logger = logging.getLogger("mkchain")

address1 = None


def create_cache(api: RpcApi, data: bytes) -> str:
    logger.debug(f"create_cache()")

    cache_ident = api.command("createbinarycache")
    logger.debug(f"create_cache(chain_name={api.chain.name!r}, data={data!r}) -> cache_ident={cache_ident!r}")
    api.command("appendbinarycache", cache_ident, data.hex())
    return cache_ident


def create_stream(api: RpcApi, stream_name: str, cache_ident: str):
    logger.debug(f"create_stream(stream_name={stream_name!r}, cache_ident={cache_ident!r})")

    restrict_stream_name = stream_name + "_restrict"
    api.api.print_tx("create", "stream", restrict_stream_name, {"restrict": "offchain,write"})

    api.command("create", "stream", stream_name, True)
    api.command("publish", stream_name, "key1", os.urandom(100).hex())
    api.command("publish", stream_name, "key2",
                {"text": "Hello there! I am a pretty long string, so it should be truncated on display"})
    api.command("publish", stream_name, "key3", {"cache": cache_ident})
    api.api.print_tx("publish", stream_name, "key4", {"text": "hello"}, "offchain")
    api.command("publish", stream_name, [f"key{i}" for i in range(10, 20)],
                {"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}})
    api.print_command("liststreamitems", stream_name, is_log=False)


def create_asset(api: RpcApi, asset_name: str):
    global address1

    logger.debug(f"create_asset(asset_name={asset_name!r})")

    address1 = api.command("listpermissions", "issue")[0]["address"]
    address2 = api.command("createkeypairs")[0]["address"]
    address3 = api.command("getnewaddress")
    api.command("importaddress", address2, "external")
    api.command("grant", address2, "receive")
    api.command("grant", address3, "send,receive")
    api.command("issue", address1, asset_name, 1000, 1, 0, {"x": ["ex", "X"], "y": "why?"})

    api.print_tx("sendfrom", address1, address3, {asset_name: 10, "data": {"json": [1, 2, 3]}})
    api.print_tx("sendfrom", address3, address1, {asset_name: 10})

    api.print_tx("sendfrom", address1, address2, {asset_name: 50})
    api.print_tx("sendwithdatafrom", address1, address2, {asset_name: 10}, os.urandom(100).hex())
    api.print_tx("sendfrom", address1, address2, {asset_name: 10, "data": os.urandom(50).hex()})
    api.print_tx("sendwithdatafrom", address1, address2, {asset_name: 150},
                 {"text": "I just sent 100 asset1 units to the external address I created earlier"})
    api.print_tx("sendwithdatafrom", address1, address2, {asset_name: 200}, {"json": {
        "name": "Zvi Tarem",
        "message": "I just sent 200 more asset1 units to the same external address I created earlier"
    }})
    api.print_tx("issue", address1, {"name": asset_name + "X", "open": True, "restrict": "send"}, 5000, 0.01, 0)


def create_upgrade(api: RpcApi):
    logger.debug(f"create_upgrade()")
    api.print_tx("create", "upgrade", "upgradeStuff", False,
                 {"max-std-element-size": 60000, "max-std-op-drops-count": 7})
    api.print_tx("approvefrom", address1, "upgradeStuff", True)
    api.print_command("listupgrades", is_log=False)


def create_paused_transaction(api: RpcApi, stream_name: str):
    logger.debug(f"create_paused_transaction()")
    logger.info("Pausing 20 seconds")
    sleep(20)
    tx_id = api.command("publish", stream_name, "key100", {"json": {"message": "Transaction in the mempool"}})
    api.command("pause", "mining")
    sleep(1)
    api.print_tx_id(tx_id)


def get_options(chain: Chain):
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[chain.options_parser()])
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

    option_display = chain.process_options(options)
    option_display.append(("Stream", options.stream))
    option_display.append(("Asset", options.asset))
    option_display.append(("Pause", options.pause))
    chain.log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")

    chain = Chain(logger)
    options = get_options(chain)

    chain.create()
    api = RpcApi(logger, chain.name, options.verbose)
    api.adjust_config()
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
