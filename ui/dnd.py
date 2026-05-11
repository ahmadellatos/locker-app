"""
ui/dnd.py
Helper drag-and-drop berbasis tkinterdnd2.

Kalau tkinterdnd2 tidak terinstall, semua fungsi jadi no-op
sehingga app tetap jalan normal (hanya tanpa fitur DnD).

Install: pip install tkinterdnd2
"""
import os
import re

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    TkinterDnD = None
    DND_FILES   = None
    DND_AVAILABLE = False


def parse_drop_path(raw: str) -> str | None:
    """
    Parse path mentah dari event drop Windows Explorer.

    Windows bisa kirim dalam format:
      - Path normal          : C:/Users/Ahmad/folder
      - Path dengan spasi    : {C:/Users/Ahmad/my folder}
      - Multiple drop        : {C:/path1} C:/path2   → ambil yang pertama
    """
    raw = raw.strip()
    # Cari semua token: yang dibungkus {} atau kata tanpa spasi
    matches = re.findall(r'\{([^}]+)\}|(\S+)', raw)
    for braced, plain in matches:
        path = braced or plain
        if path:
            return os.path.normpath(path)
    return None


def _bind_hover(widget, on_enter, on_leave):
    """
    Bind enter/leave/position events ke satu widget.

    Nama event yang benar di tkinterdnd2/tkdnd:
        <<DropEnter>>    — cursor masuk area widget saat drag (BUKAN <<DragEnter>>)
        <<DropLeave>>    — cursor keluar area widget saat drag (BUKAN <<DragLeave>>)
        <<DropPosition>> — fire terus-menerus selama drag di atas widget
                           penting agar hover state tidak mati saat cursor
                           berpindah ke child widget (button, label) di dalam card

    <<DropPosition>> harus return event.action agar OS tahu drag masih valid.
    """
    hovering = [False]  # list agar bisa dimodifikasi dari dalam closure

    def _enter(event):
        if not hovering[0]:
            hovering[0] = True
            on_enter()

    def _position(event):
        if not hovering[0]:
            hovering[0] = True
            on_enter()
        return event.action   # wajib — memberitahu OS bahwa drop diizinkan

    def _leave(event):
        if hovering[0]:
            hovering[0] = False
            on_leave()

    widget.dnd_bind('<<DropEnter>>', _enter)
    widget.dnd_bind('<<DropPosition>>', _position)
    widget.dnd_bind('<<DropLeave>>', _leave)


def register_drop_folder(widget, on_drop, on_enter=None, on_leave=None):
    """
    Daftarkan widget sebagai drop target untuk folder.

    Args:
        widget   : widget Tkinter/CTk yang jadi drop zone
        on_drop  : callback(path: str) — dipanggil saat folder dilepas
        on_enter : callback() — dipanggil saat drag masuk area widget
        on_leave : callback() — dipanggil saat drag keluar area widget
    """
    if not DND_AVAILABLE:
        return

    widget.drop_target_register(DND_FILES)

    def _on_drop(event):
        if on_leave:
            on_leave()
        path = parse_drop_path(event.data)
        if path and os.path.isdir(path):
            on_drop(path)

    widget.dnd_bind('<<Drop>>', _on_drop)

    if on_enter and on_leave:
        _bind_hover(widget, on_enter, on_leave)


def register_drop_file(widget, on_drop, extension: str = ".locked",
                       on_enter=None, on_leave=None):
    """
    Daftarkan widget sebagai drop target untuk file dengan ekstensi tertentu.

    Args:
        widget    : widget Tkinter/CTk yang jadi drop zone
        on_drop   : callback(path: str) — dipanggil saat file dilepas
        extension : ekstensi yang diterima, default ".locked"
        on_enter  : callback() — dipanggil saat drag masuk
        on_leave  : callback() — dipanggil saat drag keluar
    """
    if not DND_AVAILABLE:
        return

    widget.drop_target_register(DND_FILES)

    def _on_drop(event):
        if on_leave:
            on_leave()
        path = parse_drop_path(event.data)
        if path and os.path.isfile(path) and path.lower().endswith(extension):
            on_drop(path)

    widget.dnd_bind('<<Drop>>', _on_drop)

    if on_enter and on_leave:
        _bind_hover(widget, on_enter, on_leave)