import re
import struct
from dataclasses import dataclass
from pathlib import Path

from ._registry import PackerRegistry


@dataclass
class MagicPattern:
    pattern: re.Pattern[bytes]
    offset: int

    def finditer(self, buffer: bytes):
        for matched in self.pattern.finditer(buffer):
            offset = matched.start() + self.offset
            if 0 <= offset <= len(buffer):
                yield offset


character_slots_magic = MagicPattern(
    pattern=re.compile(b"'\x00\x00FACE"),
    offset=-61,
)


def get_character_slots(unpack_dir: Path) -> tuple[bool, ...]:
    mode = PackerRegistry.detect_repacker(unpack_dir).mode
    match mode:
        case "PC":
            regulation_file = "USERDATA_10"
        case "PS":
            regulation_file = "REGULATION"
        case _:
            raise ValueError(
                f"Unable to get available slots. "
                f"Mode {mode} is not supported."
            )
    regulation_path = unpack_dir / regulation_file
    buffer = regulation_path.read_bytes()
    for offset in character_slots_magic.finditer(buffer):
        slots = struct.unpack_from("<10B", buffer, offset)
        if any(x not in (0, 1) for x in slots):
            continue
        return tuple(x == 1 for x in slots)
    raise ValueError(
        f"Unable to get available slots. "
        f"Magic pattern not found in {regulation_path}."
    )
