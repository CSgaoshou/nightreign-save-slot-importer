from pathlib import Path

from . import _pc, _ps
from ._registry import PackerRegistry
from ._utils import get_character_slots


def detect_unpacker(save_file: Path | str):
    return PackerRegistry.detect_unpacker(Path(save_file))


def detect_repacker(unpack_dir: Path | str):
    return PackerRegistry.detect_repacker(Path(unpack_dir))


def unpack(save_file: Path | str, output_dir: Path | str):
    """Unpacks a save file into the specified output directory."""
    save_file = Path(save_file)
    output_dir = Path(output_dir)
    handler = detect_unpacker(Path(save_file))
    handler.unpack(save_file, output_dir)


def repack(input_dir: Path | str, output_file: Path | str):
    """Repacks an unpacked directory back into a save file."""
    input_dir = Path(input_dir)
    output_file = Path(output_file)
    handler = detect_repacker(Path(input_dir))
    handler.repack(input_dir, output_file)


def read_steam_id(unpack_dir: Path | str):
    """Read Steam ID from a unpacked dir"""
    unpack_dir = Path(unpack_dir)
    handler = PackerRegistry.detect_repacker(unpack_dir)
    return handler.read_steam_id(unpack_dir)


def patch_steam_id(userdata_file: Path | str, steam_id: bytes):
    """Patch Steam ID for specific USERDATA"""
    userdata_file = Path(userdata_file)
    unpack_dir = userdata_file.parent
    handler = PackerRegistry.detect_repacker(unpack_dir)
    handler.patch_steam_id(userdata_file, steam_id)
