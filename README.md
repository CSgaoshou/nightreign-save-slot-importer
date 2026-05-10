# Nightreign Save Slot Importer

A lightweight desktop tool for importing character slots between **Elden Ring Nightreign** save files.

This project keeps only the save-slot import workflow: choose a source save on the left, choose a target save on the right, select a source character slot, then click the target slot to replace it.

## Source Code Origin

The source code for this project is based on:

https://github.com/CSgaoshou/Elden-Ring-Nightreign-Save-Editor

This repository is a simplified and focused version that removes the original editor features and keeps only the character-slot import functionality.

## Features

- Import one character slot from one save file into another save file.
- Supports PC save files: `.sl2`, `.co2`.
- Supports decrypted PS4 save files: `.dat`.
- Compact white interface with two save panels.
- Automatically patches Steam ID for PC target saves.
- Creates backups before overwriting saved output.

## Requirements

- Python 3.12 or newer
- `cryptography`
- Tkinter, usually included with Python on Windows

Install the required dependency:

```bash
pip install cryptography
```

## Run

```bash
python src/Final.py
```

## Basic Usage

1. Click **Choose Source Save** on the left.
2. Click **Choose Target Save** on the right.
3. Select the character slot you want to import from the left list.
4. Click the target character slot on the right list.
5. Click **Save Imported Save**.

By default, the save dialog keeps the original target save filename, such as `NR0000.sl2`.

## Backup Location

Backups and temporary unpacked files are stored outside the source directory under the local app data folder:

```text
%LOCALAPPDATA%\NightreignSaveImporter\
```

## Safety Notice

Always keep a separate untouched backup of your original save files. Editing or replacing save data can corrupt progress if used incorrectly, and modified saves may carry online risk.
