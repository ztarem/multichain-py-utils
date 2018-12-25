import logging
import os
import shlex
import shutil
import signal
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path
from subprocess import Popen, call, STDOUT
from time import sleep
from typing import Any, Tuple, List

import psutil


class Chain:
    def __init__(self, logger: logging.Logger, name: str = None):
        self.name = name
        self.logger = logger
        self.bindir: str = None
        self.datadir = Path(os.environ["APPDATA"]) / "MultiChain" \
            if sys.platform == "win32" else Path.home() / ".multichain"
        self.warn = False
        self.stop = True
        self.debug: str = None

    @property
    def path(self) -> Path:
        return self.datadir / self.name

    def kill_multichaind_processes(self):
        def cmdline2str(p: psutil.Process) -> str:
            return ' '.join(shlex.quote(arg) for arg in p.cmdline())

        processes = [p for p in psutil.process_iter(attrs=("cmdline",)) if
                     p.info["cmdline"] and p.info["cmdline"][:2] == ["multichaind", self.name]]
        for p in processes:
            self.logger.info(f"Terminating process {p.pid}: {cmdline2str(p)}")
            p.send_signal(signal.SIGTERM)
        gone, alive = psutil.wait_procs(processes, timeout=2)
        for p in alive:
            self.logger.info(f"Killing process {p.pid}: {cmdline2str(p)}")
            p.kill()

    @staticmethod
    def options_parser() -> ArgumentParser:
        parser = ArgumentParser(add_help=False)
        group = parser.add_argument_group(title="MultiChain options")
        group.add_argument("--datadir", metavar="DIR", help="folder with MultiChain chain data")
        group.add_argument("--bindir", metavar="DIR", help="folder with MultiChain binaries")
        group.add_argument("-c", "--chain", metavar="NAME", default="chain1",
                           help="chain name  (default: %(default)s)"
                                " (will overwrite existing unless -w/--warn is also specified)")
        group.add_argument("-w", "--warn", action="store_true", help="warn and exit if named chain already exists")
        parser.add_argument("--no-stop", dest="stop", action="store_false", help="don't stop daemon at end of script")
        parser.add_argument("-v", "--verbose", action="store_true", help="write debug messages to Python log")
        parser.add_argument("-d", "--debug", metavar="CATEGORIES", nargs="?", default=None, const="all",
                            help="enable debug messages in MultiChain log")
        return parser

    def process_options(self, options: Namespace) -> List[Tuple[str, Any]]:
        option_display = []
        if options.verbose:
            self.logger.setLevel(logging.DEBUG)
        if options.datadir:
            self.datadir = options.datadir
        if options.bindir:
            self.bindir = options.bindir
        self.name = options.chain
        self.warn = options.warn
        self.stop = options.stop
        self.debug = options.debug

        if self.bindir:
            option_display.append(("Binaries", self.bindir))
        option_display.append(("Data dir", self.datadir))
        option_display.append(("Chain", self.name))
        option_display.append(("Warn", self.warn))
        option_display.append(("Stop daemon", self.stop))
        option_display.append(("Debug", self.debug))
        return option_display

    def log_options(self, parser: ArgumentParser, option_display: List[Tuple[str, Any]]):
        label_width = max(len(label) for label, _ in option_display) + 1
        self.logger.info(f"{parser.prog} - {parser.description}")
        for label, value in option_display:
            self.logger.info(f"  {label + ':':{label_width}} {value}")

    def create(self) -> Popen:
        self.logger.debug(f"create()")
        if self.bindir:
            os.environ["PATH"] = os.pathsep.join([self.bindir, os.environ["PATH"]])
            self.logger.info(f'>>> Set $PATH={os.environ["PATH"]}')
        if self.path.exists():
            if self.warn:
                message = f"Chain '{self.name}' already exists. Please choose another name."
                self.logger.error(message)
                raise ValueError(message)
            self.kill_multichaind_processes()

            self.logger.info(f">>> Remove {self.path}")
            shutil.rmtree(self.path)

        cmd = ["multichain-util", "create", self.name, f"--datadir={self.datadir}"]
        self.logger.info(f">>> {' '.join(cmd)}")
        call(cmd)
        sleep(1)

        cmd = ["multichaind", self.name, "-autosubscribe=assets,streams", f"--datadir={self.datadir}"]
        if sys.platform != "win32":
            cmd.append("-daemon")
        if self.debug:
            arg = "-debug"
            if self.debug != "all":
                arg += f"={self.debug}"
            cmd.append(arg)
        self.logger.info(f">>> {' '.join(cmd)}")
        proc = Popen(cmd, stderr=STDOUT, close_fds=True)
        sleep(5)
        return proc
