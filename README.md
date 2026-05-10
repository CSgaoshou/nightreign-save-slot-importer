# Nightreign Save Slot Importer

A compact desktop tool for importing character slots between **Elden Ring Nightreign** save files.

The tool focuses on one workflow only: load a source save, load a target save, choose a character slot from the source save, and import it into a selected slot in the target save.

## Source Code Origin

This project is based on source code from:

https://github.com/CSgaoshou/Elden-Ring-Nightreign-Save-Editor

That repository was originally created as a modified version of the Nightreign save editor. The related change has since been adopted in **V4.6.4**, so this repository now exists as a simplified standalone tool focused only on save-slot importing.

## Features

- Import a character slot from one save file into another.
- Supports PC save files: `.sl2`, `.co2`.
- Supports decrypted PS4 save files: `.dat`.
- Compact white two-panel interface.
- Automatically patches Steam ID when importing into PC saves.
- Keeps the original target save filename by default, such as `NR0000.sl2`.
- Stores backups and temporary files outside the source directory.

## Requirements

- Python 3.12 or newer
- `cryptography`
- Tkinter, usually included with Python on Windows

Install dependencies:

```bash
pip install cryptography
```

## Run

```bash
python src/Final.py
```

## Usage

1. Choose the source save on the left.
2. Choose the target save on the right.
3. Click the source character slot you want to import.
4. Click the target character slot you want to replace.
5. Click the save button and save the target file.

## Backup and Temporary Files

Runtime files are stored under:

```text
%LOCALAPPDATA%\NightreignSaveImporter\
```

This includes temporary unpacked save data and backup files created before overwriting output.

## Notice

Always keep an untouched backup of your original save files. Editing save data can corrupt progress if used incorrectly, and modified saves may carry online risk.
