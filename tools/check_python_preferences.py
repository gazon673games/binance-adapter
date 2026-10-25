"""Check all public Python files in this independent repository."""

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def repository_sources() -> list[str]:
    result = subprocess.run(
        [
            'git',
            'ls-files',
            '--cached',
            '--others',
            '--exclude-standard',
            '-z',
            '--',
            '*.py',
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    sources = sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})
    for source in sources:
        path = (PROJECT_ROOT / source).resolve()
        if not path.is_relative_to(PROJECT_ROOT) or not path.is_file():
            raise ValueError(f'Invalid Python source: {source}')
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fix', action='store_true')
    args = parser.parse_args()
    tools = tomllib.loads(
        (PROJECT_ROOT / 'pyproject.toml').read_text(encoding='utf-8')
    )['tool']
    owner = tools.get('backtest_engine', tools.get('metarhia', {}))
    profile = owner['python_preferences']
    files = repository_sources()
    command = [sys.executable, '-m', 'ruff']

    def run(*arguments):
        subprocess.run(
            [*command, *arguments, '--config', profile['config']],
            cwd=PROJECT_ROOT,
            check=True,
        )

    for offset in range(0, len(files), 100):
        chunk = files[offset : offset + 100]
        if args.fix:
            run('check', '--fix', *chunk)
            run('format', *chunk)
        run('check', *chunk)
        run('format', '--check', *chunk)
    limit = profile['max_lines']
    oversized = [
        name
        for name in files
        if len((PROJECT_ROOT / name).read_text(encoding='utf-8').splitlines())
        > limit
    ]
    if oversized:
        raise ValueError(f'Source limit exceeded ({limit}): {oversized}')
    print(f'Checked all {len(files)} public Python files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
