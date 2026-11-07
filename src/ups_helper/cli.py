"""Command line entry point for the observe-only controller."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import ConfigError, load_config
from .runtime import monitor, simulate
from .store import StateError


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='ups-helper')
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('config-check')
    check.add_argument('--config', type=Path, required=True)
    sim = commands.add_parser('simulate')
    sim.add_argument('--config', type=Path, required=True)
    sim.add_argument('--scenario', type=Path, required=True)
    mon = commands.add_parser('monitor')
    mon.add_argument('--config', type=Path, required=True)
    mon.add_argument('--state', type=Path)
    mon.add_argument('--once', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == 'config-check':
            print(json.dumps({'type': 'config', 'version': config.version, 'mode': config.mode,
                              'hosts': len(config.hosts), 'enabled_hosts': sum(host.enabled for host in config.hosts)}))
        elif args.command == 'simulate':
            simulate(config, args.scenario)
        else:
            monitor(config, once=args.once, state_path=args.state)
        return 0
    except (ConfigError, StateError, ValueError) as exc:
        if isinstance(exc, ConfigError):
            message = 'Invalid configuration'
        elif isinstance(exc, StateError):
            message = 'Checkpoint access failed'
        else:
            message = 'Invalid input or state'
        print(json.dumps({'type': 'error', 'message': message}), file=sys.stderr)
        return 2
