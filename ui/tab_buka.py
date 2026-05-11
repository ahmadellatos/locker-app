"""
ui/tab_buka.py
Frame untuk tab "Buka Brankas".
"""
import threading
from tkinter import filedialog

import customtkinter as ctk

from core.vault import buka_brankas
from .dnd import DND_AVAILABLE, register_drop_file
from .theme import (
    FONT_LABEL, FONT_SMALL, FONT_BTN,
    CLR_ACCENT, CLR_ACCENT_HV, CLR_DANGER, CLR_DANGER_HV,
    CLR_INNER, CLR_BORDER, CLR_MUTED, CLR_CARD,
)
from .widgets import make_card, NotifBar, ProgressRow

CLR_CARD_HOVER  = "#252B42"
CLR_BORDER_DRAG = CLR_ACCENT


class TabBuka(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._path_file: str | None = None
        self._show_pw               = False
        self._konfirmasi_timpa      = False

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Masukkan file .locked dan password untuk membuka",
            font=FONT_SMALL, text_color=CLR_MUTED,
        ).pack(pady=(10, 12))

        self._build_card_file()
        self._build_card_password()
        self._build_action()

    def _build_card_file(self):
        self._card_file = ctk.CTkFrame(
            self, fg_color=CLR_CARD, corner_radius=10,
            border_width=2, border_color=CLR_CARD,
        )
        self._card_file.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self._card_file, text="📄  FILE BRANKAS (.locked)", font=FONT_LABEL,
            text_color=CLR_MUTED
        ).pack(anchor="w", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(self._card_file, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_browse = ctk.CTkButton(
            row, text="Browse  .locked", font=FONT_BTN,
            height=36, corner_radius=8,
            fg_color=CLR_ACCENT, hover_color=CLR_ACCENT_HV, text_color="#000000",
            command=self._pilih_file,
        )
        self.btn_browse.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_clear = ctk.CTkButton(
            row, text="✖", width=36, height=36,
            fg_color=CLR_BORDER, hover_color="#3D4562", font=("Segoe UI", 11),
            command=self._clear_file,
        )

        self.lbl_path = ctk.CTkLabel(
            self._card_file,
            text="File belum dipilih" + ("  ·  atau seret file .locked ke sini" if DND_AVAILABLE else ""),
            font=FONT_SMALL, text_color=CLR_MUTED, wraplength=390, anchor="w",
        )
        self.lbl_path.pack(anchor="w", padx=14, pady=(0, 10))

        self._register_dnd()

    def _register_dnd(self):
        targets = [self._card_file, self.btn_browse, self.lbl_path]
        for widget in targets:
            register_drop_file(
                widget,
                on_drop=self._on_drop_file,
                extension=".locked",
                on_enter=self._on_drag_enter,
                on_leave=self._on_drag_leave,
            )

    def _on_drag_enter(self):
        self._card_file.configure(
            fg_color=CLR_CARD_HOVER,
            border_color=CLR_BORDER_DRAG,
        )
        if not self._path_file:
            self.lbl_path.configure(
                text="📄  Lepaskan file .locked di sini…",
                text_color=CLR_ACCENT,
            )

    def _on_drag_leave(self):
        self._card_file.configure(
            fg_color=CLR_CARD,
            border_color=CLR_CARD,
        )
        if not self._path_file:
            self.lbl_path.configure(
                text="File belum dipilih  ·  atau seret file .locked ke sini",
                text_color=CLR_MUTED,
            )

    def _on_drop_file(self, path: str):
        self._set_file(path)

    def _build_card_password(self):
        card = make_card(self)
        ctk.CTkLabel(card, text="🔑  MASUKKAN PASSWORD", font=FONT_LABEL,
                     text_color=CLR_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        row_pw = ctk.CTkFrame(card, fg_color="transparent")
        row_pw.pack(fill="x", padx=14, pady=(0, 14))

        self.entry_pw = ctk.CTkEntry(
            row_pw, placeholder_text="Ketik password di sini…",
            show="*", height=36, corner_radius=8,
            fg_color=CLR_INNER, border_color=CLR_BORDER, border_width=1,
        )
        self.entry_pw.pack(side="left", expand=True, fill="x")
        self.entry_pw.bind("<Return>", lambda _: self._proses())
        self.entry_pw.bind("<KeyRelease>", lambda _: self.notif.clear())

        ctk.CTkButton(
            row_pw, text="👁", width=36, height=36,
            fg_color="transparent", hover_color=CLR_CARD,
            command=self._toggle_pw,
        ).pack(side="right", padx=(6, 0))

    def _build_action(self):
        self._progress = ProgressRow(self, accent_color=CLR_ACCENT)

        self.btn_aksi = ctk.CTkButton(
            self, text="BUKA BRANKAS",
            font=FONT_BTN, height=42, corner_radius=10,
            fg_color=CLR_ACCENT, hover_color=CLR_ACCENT_HV, text_color="#000000",
            command=self._proses,
        )
        self.btn_aksi.pack(fill="x", padx=20, pady=(6, 8))

        self.notif = NotifBar(self)
        self.notif.pack(fill="x", padx=20, ipady=6)

    # ── Controls ──────────────────────────────────────────────────────────────

    def _toggle_pw(self):
        self._show_pw = not self._show_pw
        self.entry_pw.configure(show="" if self._show_pw else "*")

    def _set_file(self, path: str):
        """Set file yang dipilih — dipanggil dari browse maupun drag & drop."""
        self._path_file = path
        tampil = path if len(path) < 50 else "…" + path[-47:]
        self.lbl_path.configure(text=tampil, text_color=CLR_ACCENT)
        self.btn_clear.pack(side="right", padx=(6, 0))
        self.notif.clear()
        self._reset_timpa()

    def _pilih_file(self):
        f = filedialog.askopenfilename(filetypes=[("Locked Files", "*.locked")])
        if not f:
            return
        self._set_file(f)

    def _clear_file(self):
        self._path_file = None
        hint = "File belum dipilih" + ("  ·  atau seret file .locked ke sini" if DND_AVAILABLE else "")
        self.lbl_path.configure(text=hint, text_color=CLR_MUTED)
        self.btn_clear.pack_forget()
        self._reset_timpa()

    def _reset_timpa(self):
        self._konfirmasi_timpa = False
        self.btn_aksi.configure(
            text="BUKA BRANKAS",
            fg_color=CLR_ACCENT, hover_color=CLR_ACCENT_HV, text_color="#000000",
        )

    # ── Process ───────────────────────────────────────────────────────────────

    def _proses(self):
        force = False
        if self._konfirmasi_timpa:
            force = True
            self._reset_timpa()

        if not self._path_file:
            self.notif.show("warn", "⚠  Pilih file .locked dulu!")
            return
        pw = self.entry_pw.get()
        if not pw:
            self.notif.show("warn", "⚠  Masukkan password!")
            return

        snap_path = self._path_file
        cb        = self._progress.make_callback(self)

        self._set_busy(True)

        def _tugas():
            result = buka_brankas(snap_path, pw, force, progress_cb=cb)
            self.after(0, lambda: self._on_selesai(*result))

        threading.Thread(target=_tugas, daemon=True).start()

    def _set_busy(self, busy: bool):
        if busy:
            self._progress.reset()
            self._progress.pack(fill="x", padx=20, pady=(0, 4),
                                before=self.btn_aksi)
            self.btn_aksi.configure(state="disabled", text="⏳  Membuka…")
            self.btn_browse.configure(state="disabled")
        else:
            self._progress.pack_forget()
            self.btn_aksi.configure(state="normal")
            self.btn_browse.configure(state="normal")

    def _on_selesai(self, status: str, msg: str | None):
        self._set_busy(False)

        if status == "SUCCESS":
            self.notif.show("ok", f"✔  Folder '{msg}' berhasil dikembalikan!")
            self.entry_pw.delete(0, "end")
            self._clear_file()
            # Auto-clear notif sukses setelah 5 detik
            self.after(5000, self.notif.clear)

        elif status == "WRONG_PW":
            self.notif.show("err", "✖  Password salah! Coba lagi.")
            self.btn_aksi.configure(text="BUKA BRANKAS")

        elif status == "OVERWRITE":
            self._konfirmasi_timpa = True
            self.btn_aksi.configure(
                text="⚠  KLIK LAGI UNTUK TIMPA",
                fg_color=CLR_DANGER, hover_color=CLR_DANGER_HV, text_color="#FFFFFF",
            )
            self.notif.show("warn",
                            f"⚠  Folder '{msg}' sudah ada! Klik tombol lagi untuk menimpa.")

        else:
            self.notif.show("err", f"✖  Error: {msg}")