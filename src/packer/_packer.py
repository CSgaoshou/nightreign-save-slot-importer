from abc import ABC, abstractmethod
from pathlib import Path


class Packer(ABC):
    def __init__(self):
        self.mode = "Base"

    @classmethod
    @abstractmethod
    def probe_unpack(cls, file_path: Path) -> bool: ...

    @classmethod
    @abstractmethod
    def probe_repack(cls, input_dir: Path) -> bool: ...

    @abstractmethod
    def unpack(self, file_path: Path, output_dir: Path): ...

    @abstractmethod
    def repack(self, input_dir: Path, output_file: Path): ...

    @abstractmethod
    def read_steam_id(self, unpack_dir: Path) -> bytes: ...

    @abstractmethod
    def patch_steam_id(self, userdata_file: Path, steam_id: bytes): ...
