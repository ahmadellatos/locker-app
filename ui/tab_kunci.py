"""
ui/tab_kunci.py
Frame untuk tab "Kunci Folder".
"""
import threading
from tkinter import filedialog

import customtkinter as ctk

from core.vault import kunci_brankas
from .dnd import DND_AVAILABLE, register_drop_folder
from .theme import (
    FONT_LABEL, FONT_SMALL, FONT_BTN,
    CLR_ACCENT, CLR_ACCENT_HV, CLR_DANGER, CLR_DANGER_HV,
    CLR_INNER, CLR_BORDER, CLR_MUTED, CLR_CARD,
    STRENGTH_COLORS, STRENGTH_LABELS,
)
from .widgets import pw_strength, make_card, NotifBar, ProgressRow

# Warna card saat drag hover
CLR_CARD_HOVER  = "#252B42"
CLR_BORDER_DRAG = CLR_ACCENT


class TabKunci(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self._path_folder: str | None = None
        self._show_pw     = False
        self._var_hapus   = ctk.BooleanVar(value=False)

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        ctk.CTkLabel(
            self, text="Amankan folder dengan enkripsi AES-256-GCM",
            font=FONT_SMALL, text_color=CLR_MUTED,
        ).pack(pady=(10, 12))

        self._build_card_folder()
        self._build_card_password()
        self._build_action()

    def _build_card_folder(self):
        # Border width 2 agar bisa berubah warna saat drag hover
        self._card_folder = ctk.CTkFrame(
            self, fg_color=CLR_CARD, corner_radius=10,
            border_width=2, border_color=CLR_CARD,   # transparan awalnya
        )
        self._card_folder.pack(fill="x", padx=20, pady=(0, 12))

        ctk.CTkLabel(
            self._card_folder, text="📁  FOLDER TARGET", font=FONT_LABEL,
            text_color=CLR_MUTED
        ).pack(anchor="w", padx=14, pady=(10, 6))

        row = ctk.CTkFrame(self._card_folder, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_browse = ctk.CTkButton(
            row, text="Browse Folder", font=FONT_BTN,
            height=36, corner_radius=8,
            fg_color=CLR_ACCENT, hover_color=CLR_ACCENT_HV, text_color="#000000",
            command=self._pilih_folder,
        )
        self.btn_browse.pack(side="left", expand=True, fill="x", padx=(0, 6))

        self.btn_clear = ctk.CTkButton(
            row, text="✖", width=36, height=36,
            fg_color=CLR_BORDER, hover_color="#3D4562", font=("Segoe UI", 11),
            command=self._clear_folder,
        )

        # Label hint — teks berubah saat drag hover
        self.lbl_path = ctk.CTkLabel(
            self._card_folder,
            text="Belum ada folder dipilih" + ("  ·  atau seret folder ke sini" if DND_AVAILABLE else ""),
            font=FONT_SMALL, text_color=CLR_MUTED, wraplength=390, anchor="w",
        )
        self.lbl_path.pack(anchor="w", padx=14, pady=(0, 6))

        self.chk_hapus = ctk.CTkCheckBox(
            self._card_folder, text="Hapus folder asli setelah dikunci",
            font=FONT_SMALL, text_color=CLR_MUTED, variable=self._var_hapus,
            fg_color=CLR_DANGER, hover_color=CLR_DANGER_HV,
            corner_radius=4, checkbox_width=18, checkbox_height=18,
        )
        self.chk_hapus.pack(anchor="w", padx=14, pady=(0, 12))

        # Daftarkan seluruh card + semua children sebagai drop zone
        self._register_dnd()

    def _register_dnd(self):
        """Daftarkan card folder sebagai drop zone untuk folder."""
        # Widget yang didaftarkan: card utama + semua child
        # agar area browse button juga bisa di-drop
        targets = [self._card_folder, self.btn_browse, self.lbl_path, self.chk_hapus]
        for widget in targets:
            register_drop_folder(
                widget,
                on_drop=self._on_drop_folder,
                on_enter=self._on_drag_enter,
                on_leave=self._on_drag_leave,
            )

    def _on_drag_enter(self):
        """Visual feedback saat drag masuk area card."""
        self._card_folder.configure(
            fg_color=CLR_CARD_HOVER,
            border_color=CLR_BORDER_DRAG,
        )
        if not self._path_folder:
            self.lbl_path.configure(
                text="📂  Lepaskan folder di sini…",
                text_color=CLR_ACCENT,
            )

    def _on_drag_leave(self):
        """Restore tampilan saat drag keluar."""
        self._card_folder.configure(
            fg_color=CLR_CARD,
            border_color=CLR_CARD,
        )
        if not self._path_folder:
            self.lbl_path.configure(
                text="Belum ada folder dipilih  ·  atau seret folder ke sini",
                text_color=CLR_MUTED,
            )

    def _on_drop_folder(self, path: str):
        """Handler saat folder berhasil di-drop."""
        self._set_folder(path)

    def _build_card_password(self):
        card = make_card(self)
        ctk.CTkLabel(card, text="🔑  BUAT PASSWORD", font=FONT_LABEL,
                     text_color=CLR_MUTED).pack(anchor="w", padx=14, pady=(10, 6))

        # Password field row — disimpan sebagai referensi untuk pack(after=)
        self._row_pw = ctk.CTkFrame(card, fg_color="transparent")
        self._row_pw.pack(fill="x", padx=14)

        self.entry_pw = ctk.CTkEntry(
            self._row_pw, placeholder_text="Buat password kuat…",
            show="*", height=36, corner_radius=8,
            fg_color=CLR_INNER, border_color=CLR_BORDER, border_width=1,
        )
        self.entry_pw.pack(side="left", expand=True, fill="x")
        self.entry_pw.bind("<KeyRelease>", self._on_pw_change)

        ctk.CTkButton(
            self._row_pw, text="👁", width=36, height=36,
            fg_color="transparent", hover_color=CLR_CARD,
            command=self._toggle_pw,
        ).pack(side="right", padx=(6, 0))

        # Strength bar — hidden saat field kosong
        self._row_str = ctk.CTkFrame(card, fg_color="transparent")
        self._strength_bar = ctk.CTkProgressBar(self._row_str, height=5, corner_radius=3)
        self._strength_bar.set(0)
        self._strength_bar.pack(side="left", expand=True, fill="x", padx=(0, 8))
        self._lbl_strength = ctk.CTkLabel(
            self._row_str, text="", width=90,
            font=FONT_SMALL, text_color=CLR_MUTED, anchor="e",
        )
        self._lbl_strength.pack(side="right")

        # Confirm password
        ctk.CTkLabel(card, text="Konfirmasi Password",
                     font=FONT_SMALL, text_color=CLR_MUTED).pack(
            anchor="w", padx=14, pady=(4, 2)
        )
        self.entry_pw_confirm = ctk.CTkEntry(
            card, placeholder_text="Ulangi password…",
            show="*", height=36, corner_radius=8,
            fg_color=CLR_INNER, border_color=CLR_BORDER, border_width=1,
        )
        self.entry_pw_confirm.pack(fill="x", padx=14)
        self.entry_pw_confirm.bind("<KeyRelease>", self._on_confirm_change)
        self.entry_pw_confirm.bind("<Return>", lambda _: self._proses())

        self._lbl_match = ctk.CTkLabel(card, text="", font=FONT_SMALL, anchor="e")
        self._lbl_match.pack(anchor="e", padx=14, pady=(4, 10))

    def _build_action(self):
        self._progress = ProgressRow(self, accent_color=CLR_ACCENT)

        self.btn_aksi = ctk.CTkButton(
            self, text="KUNCI SEKARANG",
            font=FONT_BTN, height=42, corner_radius=10,
            fg_color=CLR_ACCENT, hover_color=CLR_ACCENT_HV, text_color="#000000",
            command=self._proses,
        )
        self.btn_aksi.pack(fill="x", padx=20, pady=(6, 8))

        self.notif = NotifBar(self)
        self.notif.pack(fill="x", padx=20, ipady=6)

    # ── Live feedback ─────────────────────────────────────────────────────────

    def _on_pw_change(self, _=None):
        pw = self.entry_pw.get()
        s  = pw_strength(pw)
        if s < 0:
            self._row_str.pack_forget()
        else:
            self._row_str.pack(after=self._row_pw, fill="x", padx=14, pady=(6, 4))
            self._strength_bar.set((s + 1) / 4)
            self._strength_bar.configure(progress_color=STRENGTH_COLORS[s])
            self._lbl_strength.configure(text=STRENGTH_LABELS[s],
                                         text_color=STRENGTH_COLORS[s])
        self._on_confirm_change()
        self.notif.clear()

    def _on_confirm_change(self, _=None):
        pw1, pw2 = self.entry_pw.get(), self.entry_pw_confirm.get()
        if not pw2:
            self._lbl_match.configure(text="")
        elif pw1 == pw2:
            self._lbl_match.configure(text="✔  Cocok", text_color="#2ECC71")
        else:
            self._lbl_match.configure(text="✖  Belum cocok", text_color="#E74C3C")

    def _toggle_pw(self):
        self._show_pw = not self._show_pw
        c = "" if self._show_pw else "*"
        self.entry_pw.configure(show=c)
        self.entry_pw_confirm.configure(show=c)

    # ── Folder Picker ─────────────────────────────────────────────────────────

    def _set_folder(self, path: str):
        """Set folder yang dipilih — dipanggil dari browse maupun drag & drop."""
        self._path_folder = path
        tampil = path if len(path) < 50 else "…" + path[-47:]
        self.lbl_path.configure(text=tampil, text_color=CLR_ACCENT)
        self.btn_clear.pack(side="right", padx=(6, 0))
        self.notif.clear()

    def _pilih_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self._set_folder(folder)

    def _clear_folder(self):
        self._path_folder = None
        hint = "Belum ada folder dipilih" + ("  ·  atau seret folder ke sini" if DND_AVAILABLE else "")
        self.lbl_path.configure(text=hint, text_color=CLR_MUTED)
        self.btn_clear.pack_forget()

    # ── Process ───────────────────────────────────────────────────────────────

    def _proses(self):
        if not self._path_folder:
            self.notif.show("warn", "⚠  Pilih folder dulu!")
            return
        pw, pw2 = self.entry_pw.get(), self.entry_pw_confirm.get()
        if not pw:
            self.notif.show("warn", "⚠  Password tidak boleh kosong!")
            return
        if pw != pw2:
            self.notif.show("warn", "⚠  Password tidak cocok!")
            return

        snap_path  = self._path_folder
        snap_hapus = self._var_hapus.get()
        cb         = self._progress.make_callback(self)

        self._set_busy(True)

        def _tugas():
            result = kunci_brankas(snap_path, pw, snap_hapus, progress_cb=cb)
            self.after(0, lambda: self._on_selesai(*result))

        threading.Thread(target=_tugas, daemon=True).start()

    def _set_busy(self, busy: bool):
        if busy:
            self._progress.reset()
            self._progress.pack(fill="x", padx=20, pady=(0, 4),
                                before=self.btn_aksi)
            self.btn_aksi.configure(state="disabled", text="⏳  Memproses…")
            self.btn_browse.configure(state="disabled")
            self.chk_hapus.configure(state="disabled")
        else:
            self._progress.pack_forget()
            self.btn_aksi.configure(state="normal", text="KUNCI SEKARANG")
            self.btn_browse.configure(state="normal")
            self.chk_hapus.configure(state="normal")

    def _on_selesai(self, sukses: bool, pesan: str):
        self._set_busy(False)
        if sukses:
            self.notif.show("ok", "✔  " + pesan)
            self.entry_pw.delete(0, "end")
            self.entry_pw_confirm.delete(0, "end")
            self._lbl_match.configure(text="")
            self._strength_bar.set(0)
            self._lbl_strength.configure(text="")
            self._row_str.pack_forget()
            self._var_hapus.set(False)
            self._clear_folder()
            # Auto-clear notif sukses setelah 5 detik
            self.after(5000, self.notif.clear)
        else:
            self.notif.show("err", "✖  " + pesan)