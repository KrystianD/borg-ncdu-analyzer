import os
import signal
import subprocess
import json
import tempfile
from dataclasses import dataclass
from typing import List, Dict, Iterator, Tuple, Iterable


@dataclass
class FSEntry:
    name: str
    size: int
    sub: List['FSEntry']

    def add_entry(self, entry: 'FSEntry'):
        self.sub.append(entry)

    @staticmethod
    def from_filename(path: str, size: int = 0) -> 'FSEntry':
        return FSEntry(name=os.path.basename(path), size=size, sub=[])


def iterate_path_parts(path: str) -> Iterator[Tuple[str, str]]:
    p = path.split('/')
    for i in range(len(p)):
        yield '/'.join(p[:i]), '/'.join(p[:i + 1])


def read_lines_from_process(p: subprocess.Popen) -> Iterator[str]:
    while True:
        line = p.stdout.readline()
        if not line:
            break
        yield line


def open_ncdu_with_tree(tree: List[any]):
    with tempfile.NamedTemporaryFile(mode='w+t') as f:
        json.dump(tree, f)
        f.seek(0)

        subprocess.call(['ncdu', '-f', f.name])


class BorgAnalyzer:
    def __init__(self, full_path: bool):
        self._root_objects: List[FSEntry] = []
        self._fs_cache: Dict[str, FSEntry] = {}

        self._process_new_dir = self._process_new_dir_full_path if full_path else self._process_new_dir_dataset

    # all datasets put under one filesystem
    def _process_new_dir_full_path(self, path: str):
        for parent_path, part_path in iterate_path_parts(path):
            if part_path in self._fs_cache:
                continue

            entry = FSEntry.from_filename(part_path)
            self._fs_cache[part_path] = entry

            if parent_path == "":
                self._root_objects.append(entry)
            else:
                self._fs_cache[parent_path].add_entry(entry)

    # new tree for each dataset
    def _process_new_dir_dataset(self, path: str):
        entry = FSEntry.from_filename(path)
        self._fs_cache[path] = entry
        self._root_objects.append(entry)

    def process_lines(self, lines: Iterable[str]):
        for line in lines:
            record = json.loads(line)
            path = record['path']
            is_dir = record['type'] == 'd'

            if path == ".":
                continue

            entry = FSEntry.from_filename(path, record['size'])
            parent_dir = os.path.dirname(path)

            if is_dir:
                if parent_dir in self._fs_cache:
                    self._fs_cache[parent_dir].add_entry(entry)
                    self._fs_cache[path] = entry
                else:
                    self._process_new_dir(path)
            else:
                if parent_dir == "":
                    self._fs_cache[path] = entry
                    self._root_objects.append(entry)
                else:
                    self._fs_cache[parent_dir].add_entry(entry)

    def generate_ncdu_tree(self):

        def entry_to_ncdu(entry: FSEntry):
            if len(entry.sub) == 0:
                return {'name': entry.name, 'dsize': entry.size}
            else:
                return [
                    {'name': entry.name},
                    *[entry_to_ncdu(y) for y in entry.sub]
                ]

        new_tree = [
            1, 1, {},
            [
                {'name': '/'},
                *[entry_to_ncdu(x) for x in self._root_objects],
            ],
        ]
        return new_tree

    @staticmethod
    def analyze(lines: Iterable[str], full_path: bool):
        analyzer = BorgAnalyzer(full_path=full_path)
        analyzer.process_lines(lines)
        return analyzer.generate_ncdu_tree()


def main():
    import argparse

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--full-path', action='store_true')
    argparser.add_argument('path', nargs='?')

    args = argparser.parse_args()

    ncdu_tree = None

    is_borg_archive = "::" in args.path
    is_dump = os.path.exists(args.path)

    if is_borg_archive:
        p = None
        try:
            print("Dumping and processing archive...")
            p = subprocess.Popen(['borg', 'list', '--json-lines', args.path], stdout=subprocess.PIPE, preexec_fn=os.setpgrp)
            analyzer = BorgAnalyzer(full_path=args.full_path)
            analyzer.process_lines(read_lines_from_process(p))
            print("Generating ncdu tree...")
            ncdu_tree = analyzer.generate_ncdu_tree()
        except KeyboardInterrupt:
            exit(1)
        finally:
            if p is not None:
                os.kill(p.pid, signal.SIGTERM)

    elif is_dump:
        with open(args.path, "rt") as f:
            print("Loading lines...")
            lines = f.readlines()

            lines_cnt = len(lines)
            lines_processed = 0

            def cb(x):
                nonlocal lines_processed
                lines_processed += 1
                if lines_processed % 10000 == 0:
                    print(f"\r[{lines_processed / lines_cnt * 100:2.0f}%]", end='', flush=True)
                return x

            analyzer = BorgAnalyzer(full_path=args.full_path)
            print("Processing lines...")
            analyzer.process_lines((cb(x) for x in lines))
            print()

            print("Generating ncdu tree...")
            ncdu_tree = analyzer.generate_ncdu_tree()

    open_ncdu_with_tree(ncdu_tree)


if __name__ == '__main__':
    main()
