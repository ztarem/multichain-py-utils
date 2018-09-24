import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import mkchain_utils
from mkchain_utils import chain_path, dq, gen_commands, j, sq, write_script

module_name = Path(__file__).stem
_logger = logging.getLogger(module_name)


def build_script(options) -> List[str]:
    _logger.debug(f"build_script(pause={options.pause})")
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')
    good_script = \
"""var filtertransaction = function () {
    var tx = getfiltertransaction();
    var streaminfo = getstreaminfo('stream1');
    mcprint('streaminfo.createtxid=' + streaminfo.createtxid);
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
};"""
    exception_script = \
"""var filtertransaction = function () {
    var tx = getfiltertransaction('12345');
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
};"""

    commands = [mkchain_utils.HEADER1.format(MCFOLDER=mkchain_utils.MULTICHAIN_BIN_DIR.resolve(), NOW=datetime.now())]
    if options.init:
        commands.append(mkchain_utils.HEADER2.format(
            CHAIN=mkchain_utils.CHAIN_NAME,
            MCPARAMS=str(chain_path(mkchain_utils.CHAIN_NAME) / "params.dat"),
            MCCONF=str(chain_path(mkchain_utils.CHAIN_NAME) / "multichain.conf")
        ).strip())
    commands.extend(gen_commands('listpermissions', 'issue', '|', address_sed, var_name='address1'))
    commands.extend(gen_commands('create', 'stream', 'stream1', 'true'))
    commands.extend(["read -r -d '' good_script <<- END", good_script, "END"])
    commands.extend(gen_commands('publish', 'stream1', sq('["key1"]'), j({"text": "Hello from Zvi"}), var_name='key1_txid'))
    commands.extend(gen_commands('getrawtransaction', '$key1_txid', var_name='key1_tx'))
    commands.extend(gen_commands('create', 'txfilter', 'filter1', j({"for": "stream1"}), dq('$good_script')))
    commands.extend(gen_commands('approvefrom', '$address1', 'filter1', 'true'))
    commands.extend(gen_commands('runtxfilter', 'filter1', '$key1_tx'))
    commands.append('no_filter_script=' + dq("var foo = 'bar';"))
    commands.extend(gen_commands('create', 'txfilter', 'filter2', j({"for": "stream1"}), dq('$no_filter_script')))
    commands.extend(gen_commands('approvefrom', '$address1', 'filter2', 'true'))
    commands.extend(gen_commands('runtxfilter', 'filter2', '$key1_tx'))
    # commands.extend(gen_commands('publish', 'stream1', sq('["key2"]'), j({"text": "Hello from Zvi"})))
    commands.append('syntax_error_script=' + dq("var foo 'bar';"))
    commands.extend(gen_commands('create', 'txfilter', 'filter3', j({"for": "stream1"}), dq('$syntax_error_script')))
    commands.extend(gen_commands('approvefrom', '$address1', 'filter3', 'true'))
    commands.extend(gen_commands('runtxfilter', 'filter3', '$key1_tx'))
    # commands.extend(gen_commands('publish', 'stream1', sq('["key3"]'), j({"text": "Hello from Zvi"})))
    commands.extend(["read -r -d '' exception_script <<- END", exception_script, "END"])
    commands.extend(gen_commands('create', 'txfilter', 'filter4', j({"for": "stream1"}), dq('$exception_script')))
    commands.extend(gen_commands('approvefrom', '$address1', 'filter4', 'true'))
    commands.extend(gen_commands('runtxfilter', 'filter4', '$key1_tx'))
    # commands.extend(gen_commands('publish', 'stream1', sq('["key4"]'), j({"text": "Hello from Zvi"})))

    return commands


def get_options():
    parser = argparse.ArgumentParser(description="Build a script that builds a new chain")
    parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to log")
    parser.add_argument("--mcbin", metavar="DIR", default=mkchain_utils.MULTICHAIN_BIN_DIR,
                        help="folder with multichain binaries (default: %(default)s)")
    parser.add_argument("--mcchain", metavar="DIR", default=mkchain_utils.MULTICHAIN_HOME,
                        help="base folder for multichain chain data (default: %(default)s)")
    parser.add_argument("-c", "--chain", metavar="NAME", default=mkchain_utils.CHAIN_NAME,
                        help="chain name (default: %(default)s)")
    parser.add_argument("-s", "--script", metavar="FILE", default="make_filter_chain.sh",
                        help="name of the output script")
    parser.add_argument("-i", "--init", action="store_true", help="initialize the chain before poulating it")
    parser.add_argument("-p", "--pause", action="store_true",
                        help="Pause mining so all transactions are on the mempool")

    options = parser.parse_args()

    if options.verbose:
        _logger.setLevel(logging.DEBUG)
    mkchain_utils.CHAIN_NAME = options.chain

    _logger.info(f"{module_name} - {parser.description}")
    if options.mcbin != mkchain_utils.MULTICHAIN_BIN_DIR:
        mkchain_utils.MULTICHAIN_BIN_DIR = Path(options.mcbin)
        _logger.info(f"  MC Folder:   {options.mcbin}")
    if options.mcchain != mkchain_utils.MULTICHAIN_HOME:
        mkchain_utils.MULTICHAIN_HOME = options.mcchain
        _logger.info(f"  MC Chains:   {options.mcchain}")
    _logger.info(f"  Chain name:  {options.chain}")
    _logger.info(f"  Script file: {options.script}")
    _logger.info(f"  Init chain:  {options.init}")
    _logger.info(f"  Pause:       {options.pause}")

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    options = get_options()
    commands = build_script(options)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
