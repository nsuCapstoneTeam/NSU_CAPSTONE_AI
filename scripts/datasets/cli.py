"""Argument and result handling shared only by dataset CLIs."""

import argparse
import json
import sys
from pathlib import Path

from scripts.datasets.highlight_dataset import DatasetError, load_manifest, run


def main(prepare=False, argv=None):
    parser = argparse.ArgumentParser(description='ADR-0007 Phase A local dataset tool')
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--report', type=Path, help='Optional new report file; never overwritten')
    if not prepare:
        parser.add_argument('--check', choices=('source', 'highlights'), default='highlights')
        parser.add_argument('--repeat', action='store_true', help='Repeat full decode and encode in memory')
    args = parser.parse_args(argv)
    if not prepare and args.repeat and args.check == 'source':
        parser.error('--repeat requires --check highlights')
    try:
        manifest = load_manifest(args.manifest, args.root)
    except DatasetError as error:
        print(error, file=sys.stderr)
        return 2
    if args.report is not None and args.report.exists():
        print(f'{args.report}: report_exists: refusing to overwrite existing report', file=sys.stderr)
        return 2
    mode = 'prepare' if prepare else ('source' if args.check == 'source' else 'highlights')
    report = run(manifest, args.root, mode, repeat=False if prepare else args.repeat)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    print(payload, end='')
    for row in report['tracks']:
        if row['technical_status'] == 'failed':
            print(f"{row['failed_path']}: {row['reason']}: {row['detail']}", file=sys.stderr)
    if args.report is not None:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(payload)
        except OSError as error:
            print(f'{args.report}: report_write_failed: {error}', file=sys.stderr)
            return 1
    return 0 if report['technical_passed'] else 1
