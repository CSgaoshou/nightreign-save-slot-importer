import hashlib
import logging
import mmap
import os
import shutil
import struct
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ._packer import Packer
from ._registry import PackerRegistry

DS2_KEY = b"\x18\xf6\x32\x66\x05\xbd\x17\x8a\x55\x24\x52\x3a\xc0\xa0\xc6\x09"

BND4_MAGIC = b"BND4"
BND4_ENTRY_MAGIC = b"\x40\x00\x00\x00\xff\xff\xff\xff"

BND4_HEADER_LEN = 64
BND4_ENTRY_HEADER_LEN = 32

IV_SIZE = 16
PADDING_SIZE = 12
START_OF_CHECKSUM_DATA = 4
END_OF_CHECKSUM_DATA = PADDING_SIZE + 16  # 28 bytes

logger = logging.getLogger(__name__)


class BND4:
    def __init__(self, data: bytes):
        self.data = data
        self.entry_count = int(struct.unpack_from("<i", self.data, 12)[0])

    @classmethod
    def build(cls, headers: bytes, unpack_dir: Path):
        data = bytearray(headers)
        dummy = BND4(headers)
        for entry in dummy.entries(fill=False):
            decrypted_data = bytearray((unpack_dir / entry.filename).read_bytes())
            entry.decrypted_data = decrypted_data
            if len(decrypted_data) != entry.decrpyted_size:
                raise ValueError(
                    f"Size of modified file {entry.filename} does not match original size."
                )
            entry.patch_checksum()
            entry.encrypted_data = entry.encrypt()
            start = entry.data_offset
            end = start + len(entry.encrypted_data)
            data[start:end] = entry.encrypted_data
        return cls(bytes(data))

    def get_header(self):
        length = self.get_entry(0, False).data_offset
        return self.data[:length]

    def get_entry(self, i: int, fill=True):
        pos = BND4_HEADER_LEN + (BND4_ENTRY_HEADER_LEN * i)

        # Read Entry Magic
        magic = self.data[pos : pos + 8]
        if magic != BND4_ENTRY_MAGIC:
            raise ValueError(
                f"BND4 Entry Magic mismatch at index {i}: "
                f"Expected {BND4_ENTRY_MAGIC.hex()}, "
                f"Got {magic.hex()}"
            )

        # Unpack remaining header values
        size, _, data_offset, name_offset, footer_length = struct.unpack_from(
            "<i i i i i", self.data, pos + 8
        )

        if fill:
            # Sanity checks
            if size <= 0 or data_offset <= 0 or data_offset + size > len(self.data):
                raise ValueError(
                    f"BND4 Entry {i} has invalid size or bounds: "
                    f"offset={data_offset}, size={size}, "
                    f"end_pos={data_offset + size}, total_data_len={len(self.data)}"
                )
            encrypted_data = bytes(self.data[data_offset : data_offset + size])
        else:
            encrypted_data = b""

        return BND4Entry(
            index=i,
            size=size,
            data_offset=data_offset,
            name_offset=name_offset,
            footer_length=footer_length,
            encrypted_data=encrypted_data,
        )

    def entries(self, fill=True):
        for i in range(self.entry_count):
            yield self.get_entry(i, fill)


@dataclass
class BND4Entry:
    index: int
    size: int
    data_offset: int
    name_offset: int
    footer_length: int

    # Payload
    encrypted_data: bytes = b""
    decrypted_data: bytearray = field(default_factory=bytearray)

    @property
    def filename(self) -> str:
        return f"USERDATA_{self.index}"

    @property
    def iv(self) -> bytes:
        """The first 16 bytes of encrypted data is the Initialization Vector (IV)."""
        return self.encrypted_data[:IV_SIZE]

    @property
    def encrypted_payload(self) -> bytes:
        """The actual encrypted payload follows the IV."""
        return self.encrypted_data[IV_SIZE:]

    @property
    def decrpyted_size(self) -> int:
        return self.size - IV_SIZE

    def decrypt(self) -> bytearray:
        """Decrypts the AES-CBC payload and stores it in decrypted_data."""
        cipher = Cipher(algorithms.AES(DS2_KEY), modes.CBC(self.iv))
        decryptor = cipher.decryptor()

        raw_decrypted = decryptor.update(self.encrypted_payload) + decryptor.finalize()
        self.decrypted_data = bytearray(raw_decrypted)
        return self.decrypted_data

    def patch_checksum(self) -> None:
        """Calculates MD5 hash of the modified data and patches it into the payload."""
        if not self.decrypted_data:
            raise ValueError(
                f"Cannot patch checksum for empty data in entry {self.index}."
            )

        checksum_end = len(self.decrypted_data) - END_OF_CHECKSUM_DATA
        data_for_hash = self.decrypted_data[START_OF_CHECKSUM_DATA:checksum_end]

        # Calculate MD5
        checksum = hashlib.md5(data_for_hash, usedforsecurity=False).digest()

        # Inject checksum into the specific payload position (16 bytes)
        self.decrypted_data[checksum_end : checksum_end + 16] = checksum

    def encrypt(self) -> bytes:
        """Encrypts the currently loaded decrypted_data back to AES-CBC."""
        if not self.decrypted_data:
            raise ValueError(
                f"No decrypted data available to encrypt for entry {self.index}."
            )

        self.encrypted_data = os.urandom(IV_SIZE)  # IV
        cipher = Cipher(algorithms.AES(DS2_KEY), modes.CBC(self.iv))
        encryptor = cipher.encryptor()

        encrypted_payload = (
            encryptor.update(bytes(self.decrypted_data)) + encryptor.finalize()
        )
        return self.iv + encrypted_payload


@PackerRegistry.register("PC")
class PCPacker(Packer):
    @classmethod
    def probe_unpack(cls, file_path):
        with file_path.open("rb") as f:
            return f.read(4) == BND4_MAGIC

    @classmethod
    def probe_repack(cls, input_dir):
        headers_path = (input_dir / "HEADER")
        if not headers_path.exists():
            return False
        with headers_path.open("rb") as f:
            return f.read(4) == BND4_MAGIC

    def unpack(self, file_path, output_dir):
        raw_data = file_path.read_bytes()
        bnd4 = BND4(raw_data)

        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "HEADER").write_bytes(bnd4.get_header())

        for entry in bnd4.entries():
            try:
                decrypted = entry.decrypt()
                output_path = output_dir / entry.filename
                output_path.write_bytes(decrypted)
                logger.debug(f"Decrypted: {entry.filename}")
            except Exception as e:
                logger.error(f"Failed to decrypt entry {entry.index}: {e}")

    def repack(self, input_dir, output_file):
        header = (input_dir / "HEADER").read_bytes()
        bnd4 = BND4.build(header, input_dir)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(bnd4.data)

    def read_steam_id(self, unpack_dir):
        userdata_10 = unpack_dir / "USERDATA_10"
        with userdata_10.open("rb") as f:
            return f.read(16)[8:]

    def patch_steam_id(self, userdata_file, steam_id):
        unpack_dir = userdata_file.parent
        original_steam_id = self.read_steam_id(unpack_dir)
        with userdata_file.open("r+b") as f:
            with mmap.mmap(f.fileno(), 0) as mm:
                pos = 0
                while True:
                    pos = mm.find(original_steam_id, pos)
                    if pos == -1:
                        break
                    mm[pos : pos + len(steam_id)] = steam_id
                    pos += len(steam_id)
