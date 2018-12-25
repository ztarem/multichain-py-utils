import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import mkchain_utils
from creator.chain import Chain
from mkchain_utils import dq, gen_commands, j, sq, write_script

module_name = Path(__file__).stem
logger = logging.getLogger(module_name)


def build_script(chain: Chain, init: bool) -> List[str]:
    logger.debug("build_script()")
    address_sed = "sed -n -E " + sq(r's/.*"address"\s*:\s*"(\w+)".*/\1/p')
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
    exception_script = """
var filtertransaction = function () {
    var tx = getfiltertransaction('12345');
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
};
"""
    math_script = """
var filtertransaction = function () {
    var tx = getfiltertransaction();
    if (tx.vout.length < 2)
    {
        return 'Two transaction outputs required';
    }
    var z = Date.now();
    var x = Math.abs(-1.23);
    var y = Math.sin(1.23);
}
"""

    commands = [mkchain_utils.HEADER1.format(MCFOLDER=Path(chain.bindir).resolve(), NOW=datetime.now())]
    if init:
        commands.append(mkchain_utils.HEADER2.format(
            CHAIN=mkchain_utils.CHAIN_NAME,
            PROTOCOL=mkchain_utils.PROTOCOL,
            DEBUG="-debug" if chain.debug else "",
            MCPARAMS=str(chain.path / "params.dat"),
            MCCONF=str(chain.path / "multichain.conf")
        ).strip())
    commands.extend(gen_commands('listpermissions', 'issue', '|', address_sed, var_name='address1'))
    commands.extend(gen_commands('create', 'stream', 'stream1', 'true'))
    commands.extend(gen_commands('publish', 'stream1', sq('["key1"]'), j({"text": "Hello from Zvi"}),
                                 var_name='key1_txid'))
    commands.extend(gen_commands('getrawtransaction', dq('$key1_txid'), var_name='key1_tx'))

    commands.extend(["read -r -d '' good_script <<- END", good_script.strip(), "END"])
    commands.extend(gen_commands('create', 'txfilter', 'filter1', j({"for": "stream1"}), dq('$good_script')))
    commands.extend(gen_commands('approvefrom', dq('$address1'), 'filter1', 'true'))
    commands.extend(gen_commands('runtxfilter', 'filter1', dq('$key1_tx')))

    commands.append('no_filter_script=' + dq("var foo = 'bar';"))
    commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$no_filter_script'), dq('$key1_tx')))

    commands.append('syntax_error_script=' + dq("var foo 'bar';"))
    commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$syntax_error_script'), dq('$key1_tx')))

    commands.extend(["read -r -d '' exception_script <<- END", exception_script.strip(), "END"])
    commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$exception_script'), dq('$key1_tx')))

    commands.extend(["read -r -d '' math_script <<- END", math_script.strip(), "END"])
    commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$math_script'), dq('$key1_tx')))

    commands.append('infinite_script=' + dq("var filtertransaction = function () { while (true) {}; }"))
    for i in range(5):
        # commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$good_script'), dq('$key1_tx')))
        commands.extend(gen_commands('testtxfilter', j({"for": "stream1"}), dq('$infinite_script'), dq('$key1_tx')))

    commands.extend(['sleep 1'])
    commands.extend(gen_commands('stop'))

    return commands


def get_options(chain: Chain):
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Build a script that builds a new chain", parents=[chain.options_parser()])
    parser.add_argument("-s", "--script", metavar="FILE", default="make_filter_chain.sh",
                        help="name of the output script")
    parser.add_argument("-i", "--init", action="store_true", help="initialize the chain before populating it")
    parser.add_argument("-p", "--protocol", metavar="VER", type=int, default=mkchain_utils.PROTOCOL,
                        help="protocol version (default: %(default)s)")

    options = parser.parse_args()

    mkchain_utils.CHAIN_NAME = options.chain
    mkchain_utils.PROTOCOL = options.protocol
    option_display = chain.process_options(options)
    option_display.append(("Script file", options.script))
    option_display.append(("Init chain", options.init))
    option_display.append(("Protocol", options.Protocol))
    chain.log_options(parser, option_display)

    return options


def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    chain = Chain(logger)
    options = get_options(chain)
    commands = build_script(chain, options.init)
    write_script(options.script, commands)
    return 0


if __name__ == '__main__':
    sys.exit(main())
