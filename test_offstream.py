import logging
import os
import sys
from time import sleep

_logger = logging.getLogger(__name__)


def exec_command(cmd: str, force=False):
    print(f">>> {cmd}")
    exit_code = os.system(cmd)
    if exit_code != 0 and not force:
        raise ValueError(f"  -> Command retuned {exit_code}")
    
    
def main():
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    exec_command('multichain-cli chain1 stop', force=True)
    sleep(1)
    exec_command('rm -rf ~/.multichain/chain1')
    exec_command('multichain-util create chain1')
    sleep(1)
    exec_command('multichaind chain1 -daemon -autosubscribe=assets,streams -debug')
    sleep(1)
    exec_command('multichain-cli chain1 create stream stream1 true')
    exec_command('multichain-cli chain1 publish stream1 key1 1234')
    exec_command('multichain-cli chain1 liststreamitems stream1')
    exec_command('multichain-cli chain1 publish stream1 key2 \'{"json":{"foo":"bar"}}\' offchain')
    exec_command('multichain-cli chain1 liststreamitems stream1')
    exec_command('multichain-cli chain1 publish stream1 key3 \'{"text":"Hello"}\'')
    exec_command('multichain-cli chain1 liststreamitems stream1')
    # exec_command('multichain-cli chain1')
    # exec_command('multichain-cli chain1')
    # exec_command('multichain-cli chain1')

    return 0
    
    
if __name__ == '__main__':
    sys.exit(main())

# multichain-cli chain1 create stream stream1 true
# multichain-cli chain1 publish stream1 key1 1234
# multichain-cli chain1 liststreamitems stream1
# multichain-cli chain1 publish stream1 key2 \'{"json":{"foo":"bar"}}\' offchain
# multichain-cli chain1 liststreamitems stream1
# multichain-cli chain1 publish stream1 key3 \'{"text":"Hello"}\'
# multichain-cli chain1 liststreamitems stream1
