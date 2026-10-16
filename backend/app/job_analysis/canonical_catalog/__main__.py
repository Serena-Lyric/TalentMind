"""Explicit catalogue run/review/export/replay; never writes a formal release."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

from .runner import execute, review, export, replay, checked_destination, publish
from .store import CatalogStore


def main(argv=None):
    parser = argparse.ArgumentParser(description='B3-5 offline catalogue; human approval remains external.')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'review', 'export', 'replay'):
        command = commands.add_parser(name)
        command.add_argument('--state', required=True)
        if name != 'review': command.add_argument('--output', required=True)
        if name in ('run', 'review'): command.add_argument('--source-root', required=True)
        if name in ('review', 'export'): command.add_argument('--snapshot', required=True)
        if name == 'run':
            command.add_argument('--catalog', required=True)
            command.add_argument('--rules-version', default='v1')
        elif name == 'review': command.add_argument('--event', required=True)
        elif name == 'export':
            command.add_argument('--manifest')
            command.add_argument('--source-root')
        else: command.add_argument('--artifact', required=True)
    args = parser.parse_args(argv)
    try:
        with CatalogStore(args.state) as store:
            if args.command == 'run':
                saved = execute(store, args.catalog, args.source_root, revision=args.rules_version, output=args.output)
            elif args.command == 'review':
                identity = review(store, args.snapshot, args.event, args.source_root)
                saved = replay(store, identity)
            elif args.command == 'export':
                if args.manifest and not args.source_root:
                    raise ValueError('manifest requires explicit source root')
                saved = export(store, args.snapshot, args.manifest, args.source_root, output=args.output)
            else:
                saved = replay(store, args.artifact)
                destination = checked_destination(store, args.output, saved['input_paths'])
                publish(saved, destination, saved['run_id'])
        print(json.dumps(dict(artifact_id=saved['run_id'], formal_admitted=False)))
        return 0
    except (ValueError, OSError, TypeError, KeyError, sqlite3.Error):
        print('Catalogue input, review, manifest or publication failed; committed artifacts can be replayed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
