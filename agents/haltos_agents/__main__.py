import argparse
import sys

from .app import run

parser = argparse.ArgumentParser(prog="haltos-agents")
parser.add_argument("--tray", action="store_true", help="start hidden in the system tray")
parser.add_argument("--smoke", action="store_true", help="load the window, then exit")
sys.exit(run(parser.parse_args()))
