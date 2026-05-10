import logging
import os
import shutil
import struct
import sys
import tempfile
import tkinter as tk
import traceback
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import packer
from utils.backup import create_backup


ITEM_TYPE_WEAPON = 0x80000000
ITEM_TYPE_ARMOR = 0x90000000
ITEM_TYPE_RELIC = 0xC0000000

STATE_START_OFFSET = 0x14
STATE_SLOT_COUNT = 5120
PLAYER_NAME_SKIP = 0x94
MAX_PLAYER_NAME_CHARS = 16


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
APP_DATA_DIR = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir()) / "NightreignSaveImporter"
SOURCE_UNPACK_DIR = APP_DATA_DIR / "decrypted_import_source"
TARGET_UNPACK_DIR = APP_DATA_DIR / "decrypted_import_target"
BACKUP_DIR = APP_DATA_DIR / "backup"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class CharacterSlot:
    index: int
    name: str
    path: Path
    available: bool


@dataclass
class SaveState:
    file_path: Path | None
    unpack_dir: Path
    mode: str | None
    slots: list[CharacterSlot]


def get_item_state_size(data: bytes, offset: int) -> int:
    if offset + 8 > len(data):
        raise ValueError("USERDATA is too small to read item state data.")

    ga_handle, _ = struct.unpack_from("<II", data, offset)
    type_bits = ga_handle & 0xF0000000

    if ga_handle == 0:
        return 8
    if type_bits == ITEM_TYPE_WEAPON:
        return 88
    if type_bits == ITEM_TYPE_ARMOR:
        return 16
    if type_bits == ITEM_TYPE_RELIC:
        return 80
    return 8


def read_player_name(data: bytes) -> str | None:
    try:
        cursor = STATE_START_OFFSET
        for _ in range(STATE_SLOT_COUNT):
            cursor += get_item_state_size(data, cursor)

        cursor += PLAYER_NAME_SKIP
        if cursor >= len(data):
            return None

        max_bytes = MAX_PLAYER_NAME_CHARS * 2
        raw_name = data[cursor : cursor + max_bytes]
        for pos in range(0, len(raw_name), 2):
            if raw_name[pos : pos + 2] == b"\x00\x00":
                raw_name = raw_name[:pos]
                break

        name = raw_name.decode("utf-16-le", errors="ignore").rstrip("\x00").strip()
        return name or None
    except Exception:
        logger.exception("Failed to read character name.")
        return None


def get_save_slots(unpack_dir: Path) -> list[CharacterSlot]:
    active_slots = packer.get_character_slots(unpack_dir)
    slots: list[CharacterSlot] = []

    for index in range(10):
        userdata_path = unpack_dir / f"USERDATA_{index}"
        available = (
            index < len(active_slots)
            and active_slots[index]
            and userdata_path.is_file()
            and userdata_path.stat().st_size >= 0x1000
        )

        if available:
            name = read_player_name(userdata_path.read_bytes())
            if not name:
                name = f"小存档 {index + 1}"
        else:
            name = "空槽位"

        slots.append(
            CharacterSlot(
                index=index,
                name=name,
                path=userdata_path,
                available=available,
            )
        )

    return slots


class SlotPanel(tk.Frame):
    def __init__(
        self,
        master,
        title: str,
        caption: str,
        button_text: str,
        on_load,
        on_slot_click,
        colors: dict[str, str],
        accent: str,
    ):
        super().__init__(
            master,
            bg=colors["panel"],
            highlightthickness=1,
            highlightbackground=colors["panel_border"],
            highlightcolor=colors["panel_border"],
        )
        self.colors = colors
        self.accent = accent
        self.title = title
        self.on_slot_click = on_slot_click
        self.slot_buttons: dict[int, tk.Button] = {}
        self.ready = False
        self.configure(padx=12, pady=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        tk.Label(
            self,
            text=title,
            bg=colors["panel"],
            fg=colors["text"],
            font=("Microsoft YaHei UI", 13, "bold"),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            self,
            text=caption,
            bg=colors["panel"],
            fg=colors["muted"],
            font=("Microsoft YaHei UI", 8),
        ).grid(row=1, column=0, sticky="w", pady=(1, 5))

        path_box = tk.Frame(
            self,
            bg=colors["soft"],
            highlightthickness=1,
            highlightbackground=colors["panel_border"],
        )
        path_box.grid(row=2, column=0, sticky="ew", pady=(0, 7))
        path_box.columnconfigure(0, weight=1)
        self.path_label = tk.Label(
            path_box,
            text="未选择存档",
            bg=colors["soft"],
            fg=colors["muted"],
            anchor="w",
            justify="left",
            font=("Microsoft YaHei UI", 8),
            padx=10,
            pady=4,
        )
        self.path_label.grid(row=0, column=0, sticky="ew")

        self.load_button = tk.Button(
            self,
            text=button_text,
            command=on_load,
            bg=accent,
            fg="#ffffff",
            activebackground=colors["accent_hover"],
            activeforeground="#ffffff",
            bd=0,
            relief="flat",
            cursor="hand2",
            highlightthickness=0,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=10,
            pady=5,
        )
        self.load_button.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        self.load_button.bind(
            "<Enter>",
            lambda _event: self.load_button.configure(bg=colors["accent_hover"]),
        )
        self.load_button.bind(
            "<Leave>",
            lambda _event: self.load_button.configure(bg=accent),
        )

        list_container = tk.Frame(self, bg=colors["panel"])
        list_container.grid(row=4, column=0, sticky="nsew")
        list_container.columnconfigure(0, weight=1)
        list_container.rowconfigure(0, weight=1)

        self.list_canvas = tk.Canvas(
            list_container,
            bg=colors["panel"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.list_scrollbar = ttk.Scrollbar(
            list_container,
            orient="vertical",
            command=self.list_canvas.yview,
        )
        self.list_canvas.configure(yscrollcommand=self.list_scrollbar.set)

        self.list_canvas.grid(row=0, column=0, sticky="nsew")
        self.list_scrollbar.grid(row=0, column=1, sticky="ns")

        self.list_frame = tk.Frame(self.list_canvas, bg=colors["panel"])
        self.list_window = self.list_canvas.create_window(
            (0, 0),
            window=self.list_frame,
            anchor="nw",
        )
        self.list_frame.bind(
            "<Configure>",
            lambda _event: self.list_canvas.configure(
                scrollregion=self.list_canvas.bbox("all")
            ),
        )
        self.list_canvas.bind(
            "<Configure>",
            lambda event: self.list_canvas.itemconfigure(
                self.list_window,
                width=event.width,
            ),
        )
        self.list_canvas.bind("<MouseWheel>", self.on_mousewheel)

    def on_mousewheel(self, event):
        self.list_canvas.yview_scroll(-int(event.delta / 120), "units")

    def set_path(self, path: Path | None):
        text = f"{path.name}\n{path.parent}" if path else "未选择存档"
        self.path_label.configure(text=text)

    def set_slots(self, slots: list[CharacterSlot]):
        for child in self.list_frame.winfo_children():
            child.destroy()
        self.slot_buttons.clear()

        if not slots:
            tk.Label(
                self.list_frame,
                text="加载存档后，这里会按 1-10 一列显示小存档。",
                bg=self.colors["panel"],
                fg=self.colors["muted"],
                anchor="w",
                justify="left",
                font=("Microsoft YaHei UI", 10),
                padx=4,
                pady=4,
            ).pack(anchor="w", fill="x", pady=4)
            return

        for slot in slots:
            text = f"{slot.index + 1:02d}   {slot.name}"
            bg = self.colors["slot"] if slot.available else self.colors["empty"]
            fg = self.colors["text"] if slot.available else self.colors["muted"]
            button = tk.Button(
                self.list_frame,
                text=text,
                command=lambda selected=slot: self.on_slot_click(selected),
                bg=bg,
                fg=fg,
                activebackground=self.colors["slot_hover"],
                activeforeground=self.colors["text"],
                disabledforeground=self.colors["muted"],
                bd=0,
                relief="flat",
                cursor="hand2" if slot.available else "arrow",
                anchor="w",
                justify="left",
                highlightthickness=0,
                font=("Microsoft YaHei UI", 9, "bold" if slot.available else "normal"),
                padx=10,
                pady=4,
            )
            button.pack(fill="x", pady=2)
            button.bind("<MouseWheel>", self.on_mousewheel)
            if not slot.available:
                button.configure(state="disabled")
            self.slot_buttons[slot.index] = button

    def mark_selected(self, slot_index: int | None):
        for index, button in self.slot_buttons.items():
            if str(button["state"]) == "disabled":
                continue
            if index == slot_index:
                button.configure(
                    bg=self.colors["selected"],
                    fg=self.accent,
                    activebackground=self.colors["selected"],
                )
            else:
                button.configure(
                    bg=self.colors["slot"],
                    fg=self.colors["text"],
                    activebackground=self.colors["slot_hover"],
                )

    def mark_ready(self, ready: bool):
        self.ready = ready
        for button in self.slot_buttons.values():
            if str(button["state"]) == "disabled":
                continue
            button.configure(
                bg=self.colors["ready"] if ready else self.colors["slot"],
                fg=self.accent if ready else self.colors["text"],
                activebackground=self.colors["selected"] if ready else self.colors["slot_hover"],
            )


class SaveImportApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Nightreign 小存档导入")
        self.root.geometry("760x480")
        self.root.minsize(700, 430)

        self.source = SaveState(None, SOURCE_UNPACK_DIR, None, [])
        self.target = SaveState(None, TARGET_UNPACK_DIR, None, [])
        self.selected_source_slot: CharacterSlot | None = None
        self.has_pending_changes = False

        self.setup_style()
        self.build_ui()

    def setup_style(self):
        self.colors = {
            "bg": "#f5f7fb",
            "panel": "#ffffff",
            "soft": "#f8fafc",
            "panel_border": "#dde5f0",
            "text": "#111827",
            "muted": "#667085",
            "accent": "#2563eb",
            "accent_hover": "#1d4ed8",
            "slot": "#ffffff",
            "slot_hover": "#f1f6ff",
            "selected": "#dbeafe",
            "ready": "#ecfdf5",
            "empty": "#f2f4f7",
            "danger": "#b42318",
        }

        self.root.configure(bg=self.colors["bg"])
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("Root.TFrame", background=self.colors["bg"])
        style.configure(
            "Panel.TFrame",
            background=self.colors["panel"],
            borderwidth=1,
            relief="solid",
        )
        style.configure(
            "Header.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Microsoft YaHei UI", 18, "bold"),
        )
        style.configure(
            "SubHeader.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["text"],
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.configure(
            "PanelTitle.TLabel",
            background=self.colors["panel"],
            foreground=self.colors["text"],
            font=("Microsoft YaHei UI", 14, "bold"),
        )
        style.configure(
            "Path.TLabel",
            background=self.colors["panel"],
            foreground=self.colors["muted"],
            font=("Microsoft YaHei UI", 9),
            wraplength=420,
        )
        style.configure(
            "Hint.TLabel",
            background=self.colors["panel"],
            foreground=self.colors["muted"],
            font=("Microsoft YaHei UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background=self.colors["bg"],
            foreground=self.colors["muted"],
            font=("Microsoft YaHei UI", 9),
        )
        style.configure(
            "Primary.TButton",
            background=self.colors["accent"],
            foreground="#ffffff",
            borderwidth=0,
            focusthickness=0,
            padding=(10, 8),
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        style.map(
            "Primary.TButton",
            background=[("active", self.colors["accent_hover"]), ("pressed", self.colors["accent_hover"])],
            foreground=[("disabled", "#ffffff")],
        )
        style.configure(
            "Secondary.TButton",
            background="#ffffff",
            foreground=self.colors["text"],
            borderwidth=1,
            focusthickness=0,
            padding=(12, 10),
            font=("Microsoft YaHei UI", 10),
        )
        style.map(
            "Secondary.TButton",
            background=[("active", self.colors["slot_hover"]), ("pressed", self.colors["selected"])],
        )
        style.configure(
            "Slot.TButton",
            background=self.colors["slot"],
            foreground=self.colors["text"],
            borderwidth=1,
            focusthickness=0,
            anchor="w",
            padding=(14, 12),
            font=("Microsoft YaHei UI", 10),
        )
        style.map(
            "Slot.TButton",
            background=[("active", self.colors["slot_hover"]), ("pressed", self.colors["selected"])],
        )
        style.configure(
            "SelectedSlot.TButton",
            background=self.colors["selected"],
            foreground=self.colors["accent"],
            borderwidth=1,
            focusthickness=0,
            anchor="w",
            padding=(14, 12),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "SelectedSlot.TButton",
            background=[("active", self.colors["selected"]), ("pressed", self.colors["selected"])],
        )
        style.configure(
            "ReadySlot.TButton",
            background="#eff6ff",
            foreground=self.colors["accent"],
            borderwidth=1,
            focusthickness=0,
            anchor="w",
            padding=(14, 12),
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        style.map(
            "ReadySlot.TButton",
            background=[("active", "#dbeafe"), ("pressed", "#bfdbfe")],
        )
        style.configure(
            "EmptySlot.TButton",
            background=self.colors["empty"],
            foreground=self.colors["muted"],
            borderwidth=1,
            focusthickness=0,
            anchor="w",
            padding=(14, 12),
            font=("Microsoft YaHei UI", 10),
        )

    def build_ui(self):
        container = ttk.Frame(self.root, style="Root.TFrame", padding=16)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(1, weight=1)

        ttk.Label(
            container,
            text="左侧选来源，右侧点目标，最后保存。",
            style="SubHeader.TLabel",
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        body = ttk.Frame(container, style="Root.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1, uniform="columns")
        body.columnconfigure(1, weight=1, uniform="columns")
        body.rowconfigure(0, weight=1)

        self.source_panel = SlotPanel(
            body,
            title="导入存档",
            caption="从这个存档选择要复制的小存档",
            button_text="选择导入存档",
            on_load=lambda: self.load_save("source"),
            on_slot_click=self.select_source_slot,
            colors=self.colors,
            accent=self.colors["accent"],
        )
        self.source_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 7))

        self.target_panel = SlotPanel(
            body,
            title="待导入的存档",
            caption="点击目标槽位完成导入",
            button_text="选择待导入的存档",
            on_load=lambda: self.load_save("target"),
            on_slot_click=self.import_to_target_slot,
            colors=self.colors,
            accent=self.colors["accent"],
        )
        self.target_panel.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        footer = ttk.Frame(container, style="Root.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(
            footer,
            text="请选择左侧导入存档和右侧待导入的目标存档。",
            style="Status.TLabel",
        )
        self.status_label.grid(row=0, column=0, sticky="ew", padx=(0, 16))

        self.save_button = ttk.Button(
            footer,
            text="保存导入后的存档",
            style="Primary.TButton",
            command=self.save_target_save,
        )
        self.save_button.grid(row=0, column=1, sticky="e")
        self.save_button.state(["disabled"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def load_save(self, side: str):
        if side == "target" and not self.confirm_discard_changes():
            return

        file_path = filedialog.askopenfilename(
            title="选择存档",
            filetypes=(("Save File", ("*.sl2", "*.co2", "*.dat")), ("All Files", "*")),
        )
        if not file_path:
            return

        state = self.source if side == "source" else self.target
        panel = self.source_panel if side == "source" else self.target_panel
        label = "导入存档" if side == "source" else "待导入的存档"

        try:
            self.set_busy(True)
            packer.unpack(Path(file_path), state.unpack_dir)
            handler = packer.detect_repacker(state.unpack_dir)
            state.file_path = Path(file_path)
            state.mode = handler.mode
            state.slots = get_save_slots(state.unpack_dir)
            panel.set_path(state.file_path)
            panel.set_slots(state.slots)

            if side == "source":
                self.selected_source_slot = None
                self.source_panel.mark_selected(None)
                self.target_panel.mark_ready(False)
            else:
                self.has_pending_changes = False
                self.save_button.state(["disabled"])
                self.target_panel.mark_ready(self.selected_source_slot is not None)

            available_count = sum(1 for slot in state.slots if slot.available)
            self.set_status(f"{label}已加载：{available_count} 个可用小存档。")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("加载失败", f"无法读取该存档：\n{exc}")
        finally:
            self.set_busy(False)

    def select_source_slot(self, slot: CharacterSlot):
        if not slot.available:
            return
        if not self.source.file_path:
            messagebox.showwarning("未选择存档", "请先选择左侧导入存档。")
            return

        self.selected_source_slot = slot
        self.source_panel.mark_selected(slot.index)
        self.target_panel.mark_ready(True)
        self.set_status(f"已选择左侧 {slot.index + 1}. {slot.name}，请点击右侧要导入到的小存档位置。")
        messagebox.showinfo(
            "请选择要导入到的小存档位置",
            f"已选择：{slot.index + 1}. {slot.name}\n\n请点击右侧的小存档位置完成导入。",
        )

    def import_to_target_slot(self, target_slot: CharacterSlot):
        if not target_slot.available:
            return
        if not self.target.file_path:
            messagebox.showwarning("未选择存档", "请先选择右侧待导入的目标存档。")
            return
        if not self.selected_source_slot:
            messagebox.showwarning("未选择来源", "请先点击左侧要导入的小存档。")
            return
        if self.source.mode != self.target.mode:
            messagebox.showerror("类型不一致", "导入存档和待导入的存档类型不同，PC/PS 存档不能互相导入。")
            return

        source_slot = self.selected_source_slot
        try:
            self.set_busy(True)
            self.replace_target_slot(source_slot, target_slot)
            self.target.slots = get_save_slots(self.target.unpack_dir)
            self.target_panel.set_slots(self.target.slots)
            self.source_panel.mark_selected(None)
            self.target_panel.mark_ready(False)
            self.selected_source_slot = None
            self.has_pending_changes = True
            self.save_button.state(["!disabled"])
            self.set_status(
                f"已导入：左侧 {source_slot.index + 1}. {source_slot.name} -> "
                f"右侧 {target_slot.index + 1}. {target_slot.name}。请保存目标存档。"
            )
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("导入失败", f"无法导入该小存档：\n{exc}")
        finally:
            self.set_busy(False)

    def replace_target_slot(self, source_slot: CharacterSlot, target_slot: CharacterSlot):
        if not source_slot.path.is_file():
            raise FileNotFoundError(f"来源小存档不存在：{source_slot.path}")
        if not target_slot.path.is_file():
            raise FileNotFoundError(f"目标小存档不存在：{target_slot.path}")

        patched_source = source_slot.path.parent / f".patched_USERDATA_{source_slot.index}"
        shutil.copy2(source_slot.path, patched_source)

        try:
            if self.target.mode == "PC":
                target_steam_id = packer.read_steam_id(self.target.unpack_dir)
                packer.patch_steam_id(patched_source, target_steam_id)

            imported_data = patched_source.read_bytes()
            original_target_data = target_slot.path.read_bytes()

            if len(imported_data) <= len(original_target_data):
                merged_data = imported_data + original_target_data[len(imported_data) :]
            else:
                merged_data = imported_data[: len(original_target_data)]

            target_slot.path.write_bytes(merged_data)
        finally:
            patched_source.unlink(missing_ok=True)

    def save_target_save(self):
        if not self.target.file_path:
            messagebox.showwarning("未选择存档", "请先选择右侧待导入的目标存档。")
            return
        if not self.has_pending_changes:
            messagebox.showinfo("无需保存", "当前没有待保存的导入内容。")
            return

        default_ext, filetypes = self.get_save_file_options()
        output_file = filedialog.asksaveasfilename(
            title="保存导入后的存档",
            initialdir=str(self.target.file_path.parent),
            initialfile=self.target.file_path.name,
            defaultextension=default_ext,
            filetypes=filetypes,
        )
        if not output_file:
            return

        try:
            self.set_busy(True)
            output_path = Path(output_file)
            with create_backup(output_path, BACKUP_DIR, max_backups=5):
                packer.repack(self.target.unpack_dir, output_path)
            self.target.file_path = output_path
            self.target_panel.set_path(output_path)
            self.has_pending_changes = False
            self.save_button.state(["disabled"])
            self.set_status(f"已保存：{output_path}")
            messagebox.showinfo("保存完成", "导入后的存档已保存。")
        except Exception as exc:
            traceback.print_exc()
            messagebox.showerror("保存失败", f"无法保存目标存档：\n{exc}")
        finally:
            self.set_busy(False)

    def get_save_file_options(self):
        if self.target.mode == "PC":
            return ".sl2", (("Save File", ("*.sl2", "*.co2")), ("All Files", "*"))
        if self.target.mode == "PS":
            return ".dat", (("Save File", "*.dat"), ("All Files", "*"))
        return "", (("All Files", "*"),)

    def confirm_discard_changes(self) -> bool:
        if not self.has_pending_changes:
            return True
        return messagebox.askyesno(
            "导入内容未保存",
            "当前目标存档里有尚未保存的导入内容。\n\n继续会丢弃这些改动，是否继续？",
        )

    def set_status(self, text: str):
        self.status_label.configure(text=text)

    def set_busy(self, busy: bool):
        self.root.configure(cursor="watch" if busy else "")
        self.root.update_idletasks()

    def close(self):
        if self.confirm_discard_changes():
            self.root.destroy()


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    traceback.print_exception(exc_type, exc_value, exc_traceback)
    logging.exception("Caught unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    messagebox.showerror("错误", f"发生未处理错误：{exc_value}")


def main():
    os.chdir(BASE_DIR)
    root = tk.Tk()
    root.report_callback_exception = handle_exception
    SaveImportApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
