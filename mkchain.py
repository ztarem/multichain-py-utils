import logging
import os
import pprint
import sys
from argparse import ArgumentParser
from time import sleep

from Savoir import Savoir

from create_chain import adjust_config, create_chain, create_chain_options_parser, create_chain_update_options, rpc_api

logger = logging.getLogger("mkchain")

address1 = None
address2 = None


def create_cache(chain_name: str, api: Savoir, data: bytes) -> str:
    logger.debug(f"create_cache(chain_name={chain_name!r})")

    cache_ident = api.createbinarycache()
    logger.debug(f"create_cache(chain_name={chain_name!r}, data={data!r}) -> cache_ident={cache_ident!r}")
    api.appendbinarycache(cache_ident, data.hex())
    return cache_ident


def print_tx(api: Savoir, tx_id: str):
    if logger.isEnabledFor(logging.DEBUG) and isinstance(tx_id, str):
        pprint.pprint(api.getrawtransaction(tx_id, 1, is_log=False))


def create_stream(chain_name: str, api: Savoir, stream_name: str, cache_ident: str):
    logger.debug(f"create_stream(chain_name={chain_name!r}, stream_name={stream_name!r}, cache_ident={cache_ident!r})")

    restrict_stream_name = stream_name + "_restrict"
    print_tx(api, api.create("stream", restrict_stream_name, {"restrict": "offchain,write"}))

    api.create("stream", stream_name, True)
    api.publish(stream_name, "key1", os.urandom(100).hex())
    api.publish(stream_name, "key2",
                {"text": "Hello there! I am a pretty long string, so it should be truncated on display"})
    api.publish(stream_name, "key3", {"cache": cache_ident})
    print_tx(api, api.publish(stream_name, "key4", {"text": "hello"}, "offchain"))
    api.publish(stream_name, [f"key{i}" for i in range(10, 20)],
                {"json": {"First": 1, "second": ["one", "two", "three", "four", "five"]}})
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.liststreamitems(stream_name, is_log=False))


def create_asset(chain_name: str, api: Savoir, asset_name: str):
    global address1, address2

    logger.debug(f"create_asset(chain_name={chain_name!r}, asset_name={asset_name!r})")

    address1 = api.listpermissions("issue")[0]["address"]
    address2 = api.createkeypairs()[0]["address"]
    address3 = api.getnewaddress()
    api.importaddress(address2, "external")
    api.grant(address2, "receive")
    api.grant(address3, "send,receive")
    api.issue(address1, asset_name, 1000, 1, 0, {"x": ["ex", "X"], "y": "why?"})

    print_tx(api, api.sendfrom(address1, address3, {asset_name: 10, "data": {"json": [1, 2, 3]}}))
    print_tx(api, api.sendfrom(address3, address1, {asset_name: 10}))

    print_tx(api, api.sendfrom(address1, address2, {asset_name: 50}))
    print_tx(api, api.sendwithdatafrom(address1, address2, {asset_name: 10}, os.urandom(100).hex()))
    print_tx(api, api.sendfrom(address1, address2, {asset_name: 10, "data": os.urandom(50).hex()}))
    print_tx(api, api.sendwithdatafrom(address1, address2, {asset_name: 150}, {
        "text": "I just sent 100 asset1 units to the external address I created earlier"}))
    print_tx(api, api.sendwithdatafrom(address1, address2, {asset_name: 200}, {
        "json": {"name": "Zvi Tarem",
                 "message": "I just sent 200 more asset1 units to the same external address I created earlier"}}))
    print_tx(api, api.issue(address1, {"name": asset_name + "X", "open": True, "restrict": "send"}, 5000, 0.01, 0))


def create_upgrade(chain_name: str, api: Savoir):
    logger.debug(f"create_upgrade(chain_name={chain_name!r})")
    print_tx(api, api.create("upgrade", "upgradeStuff", False,
                             {"max-std-element-size": 60000, "max-std-op-drops-count": 7}))
    print_tx(api, api.approvefrom(address1, "upgradeStuff", True))
    if logger.isEnabledFor(logging.DEBUG):
        pprint.pprint(api.listupgrades(is_log=False))


def create_paused_transaction(chain_name: str, api: Savoir, stream_name: str):
    logger.debug(f"create_paused_transaction(chain_name={chain_name!r})")
    logger.info("Pausing 20 seconds")
    sleep(20)
    tx_id = api.publish(stream_name, "key100", {"json": {"message": "Transaction in the mempool"}})
    api.pause("mining")
    sleep(1)
    print_tx(api, tx_id)


def get_options():
    parser = ArgumentParser(description="Build a new chain with a stream", parents=[create_chain_options_parser()])
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--nostream", action="store_true", help="do not create a stream")
    parser.add_argument("-s", "--stream", metavar="NAME", default="stream1", help="stream name (default: %(default)s)")
    parser.add_argument("--noasset", action="store_true", help="do not create an asset")
    parser.add_argument("-a", "--asset", metavar="NAME", default="asset1", help="asset name (default: %(default)s)")
    parser.add_argument("-p", "--pause", action="store_true", help="Create transaction and pause mining")

    logger.info(f"mkchain.py - {parser.description}")
    options = parser.parse_args()

    if options.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("Savoir").setLevel(logging.INFO)
    create_chain_update_options(options)

    logger.info(f"  Stream:    {'None' if options.nostream else options.stream}")
    logger.info(f"  Asset:     {'None' if options.noasset else options.asset}")
    logger.info(f"  Pause:     {options.pause}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    logging.getLogger("Savoir").setLevel(logging.WARNING)
    options = get_options()

    create_chain(options)
    api = rpc_api(options.chain)
    adjust_config(options.chain)
    cache_ident = create_cache(options.chain, api, "This is a pretty long ASCII chunk in the binary cache".encode())
    if not options.nostream:
        create_stream(options.chain, api, options.stream, cache_ident)
    if not options.noasset:
        create_asset(options.chain, api, options.asset)
    create_upgrade(options.chain, api)
    if options.pause:
        create_paused_transaction(options.chain, api, options.stream)
    return 0


if __name__ == '__main__':
    sys.exit(main())
