from pathlib import Path

from ._packer import Packer


class PackerRegistry:
    _handlers: dict[str, type[Packer]] = {}

    @classmethod
    def register(cls, mode: str):
        def wrapper(handler_class: type[Packer]):
            cls._handlers[mode] = handler_class
            return handler_class

        return wrapper

    @classmethod
    def detect_unpacker(cls, file_path: Path) -> Packer:
        for mode, handler_class in cls._handlers.items():
            if handler_class.probe_unpack(file_path):
                handler = handler_class()
                handler.mode = mode
                return handler
        raise ValueError(f"Unable to recognize mode: {file_path}")

    @classmethod
    def detect_repacker(cls, input_dir: Path) -> Packer:
        for mode, handler_class in cls._handlers.items():
            if handler_class.probe_repack(input_dir):
                handler = handler_class()
                handler.mode = mode
                return handler
        raise ValueError(f"Unable to recognize mode: {input_dir}")

    @classmethod
    def get_handler(cls, mode: str) -> Packer:
        if mode not in cls._handlers:
            raise ValueError(f"Mode not supports: {mode}")
        return cls._handlers[mode]()
