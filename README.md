# Nightreign Save Slot Importer

[中文说明](#中文说明)

A compact desktop tool for importing character slots between **Elden Ring Nightreign** save files.

The tool focuses on one workflow only: load a source save, load a target save, choose a character slot from the source save, and import it into a selected slot in the target save.

## Source Code Origin

This project is based on source code from:

https://github.com/CSgaoshou/Elden-Ring-Nightreign-Save-Editor

This repository is a simplified standalone tool focused only on save-slot importing.

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

---

## 中文说明

这是一个用于 **Elden Ring Nightreign** 存档之间导入角色小存档的轻量级桌面工具。

本工具只保留一个核心流程：左侧加载来源存档，右侧加载目标存档，选择来源角色槽位，再点击目标槽位完成导入。

## 源码来源

本项目基于以下仓库的源码精简而来：

https://github.com/CSgaoshou/Elden-Ring-Nightreign-Save-Editor

当前仓库是一个独立的精简版工具，只专注于小存档导入功能。

## 功能

- 将一个存档中的角色槽位导入到另一个存档中。
- 支持 PC 存档：`.sl2`、`.co2`。
- 支持已解密的 PS4 存档：`.dat`。
- 小巧的白色双栏界面。
- 导入 PC 存档时自动修正 Steam ID。
- 保存时默认保留目标存档原文件名，例如 `NR0000.sl2`。
- 备份和临时文件会存放在源码目录之外。

## 运行要求

- Python 3.12 或更新版本
- `cryptography`
- Tkinter，Windows 的 Python 通常自带

安装依赖：

```bash
pip install cryptography
```

## 运行

```bash
python src/Final.py
```

## 使用方法

1. 在左侧选择来源存档。
2. 在右侧选择目标存档。
3. 点击左侧要导入的角色小存档。
4. 点击右侧要替换的目标角色小存档。
5. 点击保存按钮并保存目标存档。

## 备份和临时文件

运行时文件会存放在：

```text
%LOCALAPPDATA%\NightreignSaveImporter\
```

其中包括临时解包的存档数据，以及覆盖输出前创建的备份文件。

## 注意

请始终保留一份未修改的原始存档备份。不正确地修改存档可能导致进度损坏，在线使用修改存档也可能存在风险。
