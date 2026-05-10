import logging
import mmap
import re
import shutil
from pathlib import Path

from ._packer import Packer
from ._registry import PackerRegistry

EXPECTED_SAVE_SIZE = 0x12A00A0
HEADER_SIZE = 0x80
HEADER_MAGIC = b"\x4b\x01\x34\x1b"
USERDATA_CHUNK_SIZE = 0x100000
MAX_USERDATA_CHUNKS = 10
USERDATA_PADDING = 0x00100010.to_bytes(4, "little")

FILE_HEADER = "HEADER"
FILE_REGULATION = "REGULATION"
FILE_USERDATA_PREFIX = "USERDATA_"

STEAM_ID_MAGIC = [
    {
        "aob": "00 00 00 00 0A 00 00 00 ?? ?? 00 00 00 00 00 00 06",
        "offset": 44,
        "allow_zero": True,
    },
    {
        "aob": "00 00 00 00 ?? 00 00 00 ?? ?? 00 00 00 00 00 00 ??",
        "offset": 44,
        "allow_zero": False,
    },
]


logger = logging.getLogger(__name__)


def aob_iter(file: Path, aob_string: str, allow_zero: bool):
    pattern_bytes = b""
    for part in aob_string.split():
        if part == "??" or part == "?":
            if allow_zero:
                pattern_bytes += b"."
            else:
                pattern_bytes += b"[^\x00]"
        else:
            pattern_bytes += re.escape(bytes.fromhex(part))
    regex = re.compile(pattern_bytes, re.DOTALL)
    with file.open("r+b") as f:
        with mmap.mmap(f.fileno(), 0) as mm:
            for match in regex.finditer(mm):
                yield mm, match.start()


@PackerRegistry.register("PS")
class PSPacker(Packer):
    @classmethod
    def probe_unpack(cls, file_path):
        with file_path.open("rb") as f:
            return f.read(4) == HEADER_MAGIC

    @classmethod
    def probe_repack(cls, input_dir):
        headers_path = (input_dir / "HEADER")
        if not headers_path.exists():
            return False
        with headers_path.open("rb") as f:
            return f.read(4) == HEADER_MAGIC

    def unpack(self, file_path, output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        with file_path.open("rb") as f:
            # 1. Extract Header
            header = f.read(HEADER_SIZE)
            if header:
                (output_dir / FILE_HEADER).write_bytes(header)

            # 2. Extract UserData Chunks
            for i in range(MAX_USERDATA_CHUNKS):
                data = f.read(USERDATA_CHUNK_SIZE)
                if not data:
                    break
                (output_dir / f"{FILE_USERDATA_PREFIX}{i}").write_bytes(
                    USERDATA_PADDING + data
                )

            # 3. Extract Regulation
            regulation = f.read()
            if regulation:
                (output_dir / FILE_REGULATION).write_bytes(regulation)

    def repack(self, input_dir, output_file):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("wb") as out:
            # 1. Header
            header_data = (input_dir / FILE_HEADER).read_bytes()
            if len(header_data) != HEADER_SIZE:
                raise ValueError(
                    f"Invalid header size: {hex(len(header_data))}. "
                    f"Expected {hex(HEADER_SIZE)} bytes."
                )
            out.write(header_data)

            # 2. Userdata 0–9
            for i in range(MAX_USERDATA_CHUNKS):
                userdata_path = input_dir / f"{FILE_USERDATA_PREFIX}{i}"
                if not userdata_path.is_file():
                    if i != 0:
                        break
                    # USERDATA_0 is required
                    raise FileNotFoundError(f"Required file not found: {userdata_path}")

                block = userdata_path.read_bytes()
                # Validate block has data
                # PS4 USERDATA should start with specified bytes padding
                # If padding exists, strip it. If not, write as-is (kept original logic)
                if len(block) < len(USERDATA_PADDING):
                    raise ValueError(
                        f"{FILE_USERDATA_PREFIX}{i} is too small ({len(block)} bytes)"
                    )
                if block[: len(USERDATA_PADDING)] == USERDATA_PADDING:
                    block = block[len(USERDATA_PADDING) :]
                out.write(block)

            # 3. Regulation
            regulation_path = input_dir / FILE_REGULATION
            if regulation_path.is_file():
                regulation_data = regulation_path.read_bytes()
                if regulation_data:
                    out.write(regulation_data)

        # 4. Size Validation
        final_size = output_file.stat().st_size
        if final_size != EXPECTED_SAVE_SIZE:
            raise ValueError(
                f"Invalid output file size!\n"
                f"Expected: {hex(EXPECTED_SAVE_SIZE)} ({EXPECTED_SAVE_SIZE:,} bytes)\n"
                f"Got: {hex(final_size)} ({final_size:,} bytes)\n"
                f"Difference: {final_size - EXPECTED_SAVE_SIZE:+,} bytes\n\n"
                f"File may be corrupt. Check the source files in {input_dir}"
            )

    def read_steam_id(self, unpack_dir):
        return b"\x00" * 8

    def patch_steam_id(self, userdata_file, steam_id):
        for i, magic in enumerate(STEAM_ID_MAGIC):
            logger.info(f"Search for AOB pattern #{i+1}")
            aob = magic["aob"]
            allow_zero = magic["allow_zero"]
            offset2 = magic["offset"]
            count = 0
            for mm, offset in aob_iter(userdata_file, aob, allow_zero):
                mm[offset + offset2 : offset + offset2 + 8] = steam_id
                count += 1
            if count > 0:
                break
            logger.info(f"AOB pattern #{i+1} not found.")
        else:
            raise ValueError(f"AOB pattern not found.")
