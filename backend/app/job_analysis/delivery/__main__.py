"""Local CLI; stdout is a safe summary, full text only in explicit private exports."""
import argparse
import asyncio
import json
from pathlib import Path
import sqlite3

from ..foundation.inputs import parse_json
from ..foundation.runner import publish
from ..knowledge.catalog import load_snapshot
from ..understanding.storage import read_run
from .recorded import RecordedProcessor
from .runner import execute, resume
from .store import DeliveryStore


def _load(path):
    return parse_json(path.read_text(encoding='utf-8-sig'))


def _request(path):
    value = _load(path)
    for item in value['items']:
        if 'p1_run' in item:
            p1 = read_run(Path(item.pop('p1_run')))
            if any(k in item for k in ('analysis', 'p1')): raise ValueError('ambiguous input')
            item['p1'] = p1
            analysis = p1['analysis']
            for key, data in (('namespace', analysis['namespace']), ('row', analysis['input_row']),
                              ('input_version', analysis['input_version'])):
                item.setdefault(key, data)
    return value


def summary(value):
    return dict(status=value['status'], run_id=value['run_id'], request_sha256=value['request_sha256'],
                counts=value['counts'], candidate_revision=value['work']['revision'] if value['work'] else None,
                knowledge_sha256=value['knowledge']['sha256'], semantic_review=value['semantic_review'])


def main():
    parser = argparse.ArgumentParser(description='M2 independent P1/P2-1/P3/P4 delivery; private local data only')
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('init', 'head', 'run', 'resume', 'read'):
        command = commands.add_parser(name)
        command.add_argument('--state', required=True, type=Path)
        if name in {'run', 'resume', 'read'}:
            command.add_argument('--id', required=True)
            command.add_argument('--output', type=Path, help='Private directory; immutable <run-id>.json export')
        if name in {'run', 'resume'}:
            command.add_argument('--replay', type=Path, help='Manifest-bound recorded processor list; zero network')
            command.add_argument('--stop-file', type=Path, help='Stop between committed items; remove before resume')
        if name == 'run':
            command.add_argument('--request', required=True, type=Path)
            command.add_argument('--knowledge', required=True, type=Path)
        if name == 'read': command.add_argument('--expected-request')
    args = parser.parse_args()
    try:
        processor = None
        if getattr(args, 'replay', None):
            recorded = _load(args.replay)
            if set(recorded) != {'schema_version', 'runs'} or recorded['schema_version'] != 'm2-recorded-processor-1':
                raise ValueError('invalid recorded processor list')
            processor = RecordedProcessor([Path(p) for p in recorded['runs']])
        with DeliveryStore(args.state, create=args.command == 'init', readonly=args.command == 'read') as store:
            if args.command in {'init', 'head'}:
                value = dict(status='ok', binding=store.candidates.read()['binding'])
            elif args.command == 'read':
                result = store.read(args.id)
                if args.expected_request and result['request_sha256'] != args.expected_request:
                    raise ValueError('consumer request binding mismatch')
                if args.output: publish(result, args.output, args.id)
                value = summary(result)
            else:
                stop = args.stop_file.exists if args.stop_file else None
                if args.command == 'run':
                    result = asyncio.run(execute(store, args.id, _request(args.request), load_snapshot(args.knowledge),
                                                processor=processor, stop=stop, output=args.output))
                else:
                    result = asyncio.run(resume(store, args.id, processor=processor, stop=stop, output=args.output))
                value = summary(result)
        print(json.dumps(value, ensure_ascii=True, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps(dict(status='interrupted', reason='resume_same_run_with_original_dependencies')))
        return 130
    except (ValueError, OSError, KeyError, TypeError, RuntimeError, sqlite3.Error):
        print(json.dumps(dict(status='rejected', reason='invalid_or_unavailable_private_delivery')))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
