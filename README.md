Borg Backup Ncdu Analyzer
=====

#### Goal

Get an overview on archive space usage. It doesn't take deduplication and compression into account. Its main goal was to help to identify large files put to the backup archive accidentally.

#### Usage

```bash
python borg_ncdu_analyzer.py BORG_ARCHIVE_OR_DUMP [--full-path]
```

##### Parameters

`--full-path` - If passed, all datasets are merged into one FS tree.

For example, if archive was created with the following command:
```shell
borg create BORG_ARCHIVE \
    /mnt/disk1/code \
    /mnt/disk1/backups \
    /mnt/disk2/documents`
```

With `--full-path` - ncdu will show all paths under one filesystem (starting with `/mnt`).

```text
/mnt
   ├── disk1
   │   ├── code
   │   └── backups
   └── disk2
       └── documents
```

Without `--full-path` - three datasets `code`, `backups` and `documents` will be shown in main ncdu screen.

```text
/code
/backups
/documents
```

#### Examples

```bash
# Directly from Borg archive
python borg_ncdu_analyzer.py host:/path/to/borg::archive --full-path

# From Borg dump
borg list --json-lines host:/path/to/borg::archive > dump
python borg_ncdu_analyzer.py dump --full-path
```
