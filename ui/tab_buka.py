"""
Modul: tab_buka.py
Deskripsi: Antarmuka untuk Tab "Buka Brankas".
           Diperbarui: Fix layout overlap dengan mengatur ulang spacing dinamis.
"""

import os
from loguru import logger
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QFrame,
    QStackedWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFontMetrics

from core.vault import buka_brankas, VaultStatus
from .widgets import (
    CryptoWorker,
    AnimatedNotifBar,
    apply_shadow,
    BigActionBtn,
    ElidedLabel,
    HeroIconWidget,
)

notification = None
try:
    from plyer import notification

    HAS_PLYER = True
except ImportError:
    HAS_PLYER = False


class DropTargetFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropArea")
        self.setAcceptDrops(True)
        self.on_file_dropped = None

    def _set_drag_state(self, state: bool):
        self.setProperty("dragActive", state)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".locked"):
                    self._set_drag_state(True)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drag_state(False)

    def dropEvent(self, event):
        self._set_drag_state(False)
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(".locked"):
                if self.on_file_dropped:
                    self.on_file_dropped(path)
                break


class TabBuka(QWidget):
    def __init__(self):
        super().__init__()
        self._path_file = None
        self._konfirmasi_timpa = False
        self.worker: CryptoWorker | None = None
        self._build_ui()

    def _update_card_style(self, is_empty: bool):
        if is_empty:
            self.card_file.setStyleSheet("""
                QFrame#DropArea {
                    border: 2px dashed #232B3E;
                    background-color: #0B101E;
                    border-radius: 12px;
                }
                QFrame#DropArea[dragActive="true"] {
                    border: 2px dashed #00D2C8;
                    background-color: #181F32;
                }
            """)
        else:
            self.card_file.setStyleSheet("""
                QFrame#DropArea {
                    border: 1px solid #232B3E;
                    background-color: #111625;
                    border-radius: 12px;
                }
                QFrame#DropArea[dragActive="true"] {
                    border: 2px dashed #00D2C8;
                    background-color: #181F32;
                }
            """)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)

        h_container = QHBoxLayout()
        h_container.setSpacing(20)

        # KIRI (File Brankas - Stacked Dropzone)
        self.card_file = DropTargetFrame()
        apply_shadow(self.card_file, blur_radius=30, opacity=40)
        self.card_file.on_file_dropped = self._set_file

        layout_card = QVBoxLayout(self.card_file)
        layout_card.setContentsMargins(2, 2, 2, 2)

        self.stack_file = QStackedWidget()
        layout_card.addWidget(self.stack_file)

        # --- PAGE 0: DASHED EMPTY STATE DENGAN HERO ICON ---
        page_empty = QWidget()
        lay_empty = QVBoxLayout(page_empty)
        lay_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # FIX OVERLAP: Spacing nol, kita atur manual via addSpacing
        lay_empty.setSpacing(0)

        icon_empty = HeroIconWidget(mode="buka")

        lbl_main_empty = QLabel("Drag & drop file .locked ke sini")
        lbl_main_empty.setStyleSheet(
            "font-size: 13pt; font-weight: bold; color: white;"
        )
        lbl_main_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_sub_empty = QLabel("atau klik tombol di bawah untuk memilih file")
        lbl_sub_empty.setStyleSheet("font-size: 10pt; color: #8B95A5;")
        lbl_sub_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_browse_center = QPushButton(" Pilih File Brankas")
        self.btn_browse_center.setIcon(qta.icon("mdi6.folder-search", color="white"))
        self.btn_browse_center.setFixedSize(220, 42)
        self.btn_browse_center.setStyleSheet("""
            QPushButton {
                background-color: rgba(24, 31, 50, 0.5);
                border: 1px solid #232B3E;
                border-radius: 8px;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #181F32;
                border: 1px solid #00D2C8;
            }
        """)
        self.btn_browse_center.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_center.clicked.connect(self._pilih_file)

        lbl_footer_empty = QLabel(
            "Hanya file dengan ekstensi .locked yang dapat dibuka"
        )
        lbl_footer_empty.setStyleSheet("font-size: 9pt; color: #5B6575;")
        lbl_footer_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Spacing dinamis yang bisa mengecil saat window di resize ke minimum
        lay_empty.addStretch(1)
        lay_empty.addWidget(icon_empty, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay_empty.addSpacing(15)
        lay_empty.addWidget(lbl_main_empty)
        lay_empty.addSpacing(5)
        lay_empty.addWidget(lbl_sub_empty)
        lay_empty.addSpacing(20)
        lay_empty.addWidget(
            self.btn_browse_center, alignment=Qt.AlignmentFlag.AlignHCenter
        )
        lay_empty.addSpacing(25)
        lay_empty.addWidget(lbl_footer_empty)
        lay_empty.addStretch(1)

        self.stack_file.addWidget(page_empty)

        # --- PAGE 1: FILLED STATE ---
        page_filled = QWidget()
        lay_filled = QVBoxLayout(page_filled)
        lay_filled.setContentsMargins(23, 23, 23, 23)
        lay_filled.setSpacing(15)

        lbl_title_file = QLabel("FILE BRANKAS (.locked)")
        lbl_title_file.setObjectName("CardTitle")
        lay_filled.addWidget(lbl_title_file)

        # Inner Box target terpilih
        file_box = QFrame()
        file_box.setStyleSheet(
            "background-color: #181F32; border: 1px solid #232B3E; border-radius: 8px;"
        )
        lay_fbox = QHBoxLayout(file_box)
        lay_fbox.setContentsMargins(15, 15, 15, 15)

        icon_locked = QLabel()
        icon_locked.setPixmap(
            qta.icon("mdi6.file-lock", color="#00D2C8").pixmap(32, 32)
        )

        v_fname = QVBoxLayout()
        v_fname.setSpacing(2)
        self.lbl_path_filled = ElidedLabel("...", mode=Qt.TextElideMode.ElideMiddle)
        self.lbl_path_filled.setStyleSheet(
            "color: white; font-weight: bold; font-size: 11pt; border: none; background: transparent;"
        )
        lbl_path_desc = QLabel("Siap untuk didekripsi")
        lbl_path_desc.setStyleSheet(
            "color: #8B95A5; font-size: 9pt; border: none; background: transparent;"
        )
        v_fname.addWidget(self.lbl_path_filled)
        v_fname.addWidget(lbl_path_desc)

        self.btn_clear = QPushButton()
        self.btn_clear.setIcon(
            qta.icon("mdi6.close", color="#8B95A5", color_active="white")
        )
        self.btn_clear.setFixedSize(32, 32)
        self.btn_clear.setStyleSheet(
            "QPushButton { background: transparent; border: none; } QPushButton:hover { background: #E74C3C; border-radius: 4px; }"
        )
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self._clear_file)

        lay_fbox.addWidget(icon_locked)
        lay_fbox.addSpacing(10)
        lay_fbox.addLayout(v_fname, 1)
        lay_fbox.addWidget(self.btn_clear)
        lay_filled.addWidget(file_box)

        self.btn_ganti = QPushButton(" Ganti File Brankas")
        self.btn_ganti.setIcon(qta.icon("mdi6.file-find", color="white"))
        self.btn_ganti.setFixedHeight(40)
        self.btn_ganti.clicked.connect(self._pilih_file)
        lay_filled.addWidget(self.btn_ganti)

        lay_filled.addStretch()
        self.stack_file.addWidget(page_filled)

        # Set default state ke Empty
        self._update_card_style(True)
        h_container.addWidget(self.card_file, 1)

        # KANAN (Password Form)
        col_right = QVBoxLayout()
        card_pw = QFrame()
        card_pw.setObjectName("Card")
        apply_shadow(card_pw, blur_radius=30, opacity=40)

        v_pw = QVBoxLayout(card_pw)
        v_pw.setContentsMargins(25, 25, 25, 25)
        v_pw.setSpacing(15)

        lbl_title_pw = QLabel("MASUKKAN PASSWORD")
        lbl_title_pw.setObjectName("CardTitle")
        v_pw.addWidget(lbl_title_pw)
        v_pw.addSpacing(10)

        box_pw = QFrame()
        box_pw.setObjectName("InputBox")
        lay_box = QHBoxLayout(box_pw)
        lay_box.setContentsMargins(10, 0, 5, 0)
        lay_box.setSpacing(0)

        self.entry_pw = QLineEdit()
        self.entry_pw.setObjectName("InputInside")
        self.entry_pw.setFixedHeight(45)
        self.entry_pw.setPlaceholderText("Ketik password di sini…")
        self.entry_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.entry_pw.textChanged.connect(self._on_pw_change)
        self.entry_pw.returnPressed.connect(self._proses)
        lay_box.addWidget(self.entry_pw)

        self.btn_toggle_pw = QPushButton()
        self.btn_toggle_pw.setIcon(qta.icon("mdi6.eye-outline", color="#8B95A5"))
        self.btn_toggle_pw.setIconSize(QSize(22, 22))
        self.btn_toggle_pw.setObjectName("BtnEye")
        self.btn_toggle_pw.setFixedSize(40, 45)
        self.btn_toggle_pw.clicked.connect(self._toggle_pw)
        lay_box.addWidget(self.btn_toggle_pw)

        v_pw.addWidget(box_pw)
        v_pw.addStretch()
        col_right.addWidget(card_pw, 1)
        h_container.addLayout(col_right, 1)

        main_layout.addLayout(h_container)

        # BOTTOM ACTION BAR
        self.btn_aksi = BigActionBtn(
            "BUKA BRANKAS",
            "Masukkan password untuk membuka",
            icon_name="mdi6.lock-open-variant",
        )
        self.btn_aksi.setEnabled(False)
        self.btn_aksi.clicked.connect(self._proses)
        apply_shadow(self.btn_aksi, blur_radius=20, y_offset=4, opacity=80)
        main_layout.addWidget(self.btn_aksi)

        self.notif = AnimatedNotifBar(self)

    def _toggle_pw(self):
        mode = (
            QLineEdit.EchoMode.Normal
            if self.entry_pw.echoMode() == QLineEdit.EchoMode.Password
            else QLineEdit.EchoMode.Password
        )
        self.entry_pw.setEchoMode(mode)
        color = "#00D2C8" if mode == QLineEdit.EchoMode.Normal else "#8B95A5"
        icon_name = (
            "mdi6.eye-outline"
            if mode == QLineEdit.EchoMode.Password
            else "mdi6.eye-off-outline"
        )
        self.btn_toggle_pw.setIcon(qta.icon(icon_name, color=color))

    def _on_pw_change(self):
        self.notif.hide_msg()
        self._validate_state()

    def _validate_state(self):
        if not self._konfirmasi_timpa:
            self.btn_aksi.setEnabled(
                self._path_file is not None and bool(self.entry_pw.text())
            )

    def _set_file(self, path: str):
        self._path_file = path
        self.lbl_path_filled.setText(os.path.basename(path))
        self.lbl_path_filled.setToolTip(path)

        self.stack_file.setCurrentIndex(1)
        self._update_card_style(False)
        self._reset_timpa()
        self._validate_state()

    def _clear_file(self):
        self._path_file = None
        self.stack_file.setCurrentIndex(0)
        self._update_card_style(True)
        self._reset_timpa()
        self._validate_state()

    def _pilih_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Pilih File Brankas", "", "Locked Files (*.locked)"
        )
        if f:
            self._set_file(f)

    def _reset_timpa(self):
        self._konfirmasi_timpa = False
        self.btn_aksi.setTextLabels(
            "BUKA BRANKAS", "Masukkan password untuk membuka kunci"
        )

    def _proses(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            self.btn_aksi.setTextLabels("MEMBATALKAN...", "Harap tunggu...")
            self.btn_aksi.setEnabled(False)
            return

        force = self._konfirmasi_timpa
        if force:
            self._reset_timpa()

        pw = self.entry_pw.text()
        if not self._path_file or not pw:
            return

        self._set_busy(True)
        self.worker = CryptoWorker(buka_brankas, self._path_file, pw, force)
        self.worker.progress.connect(
            lambda v: self.btn_aksi.setTextLabels(
                "MEMBUKA...", f"Progress: {int(v*100)}% (Klik untuk Batal)"
            )
        )
        self.worker.finished.connect(self._on_selesai)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _set_busy(self, busy: bool):
        self.btn_browse_center.setEnabled(not busy)
        self.btn_ganti.setEnabled(not busy)
        self.btn_clear.setEnabled(not busy)
        if busy:
            self.btn_aksi.setTextLabels("MEMBUKA BRANKAS...", "Harap tunggu...")
            self.btn_aksi.setEnabled(True)
        else:
            self.btn_aksi.setTextLabels(
                "BUKA BRANKAS", "Masukkan password untuk membuka"
            )
            self._validate_state()

    def _on_selesai(self, result):
        self.worker = None
        status, msg = result

        if status == VaultStatus.SUCCESS:
            self.entry_pw.blockSignals(True)
            self.entry_pw.clear()
            self.entry_pw.blockSignals(False)
            self._clear_file()

        self._set_busy(False)

        if status == VaultStatus.SUCCESS:
            self.notif.show_msg(
                "ok", f"Folder/File '{msg}' berhasil dikembalikan!", 6000
            )
            if HAS_PLYER and notification:
                try:
                    notification.notify(
                        title="Digital Locker",
                        message=f"Brankas '{msg}' berhasil dibuka.",
                        timeout=5,
                    )
                except:
                    pass
        elif status == VaultStatus.CANCELLED:
            self.notif.show_msg("warn", "Dekripsi dibatalkan pengguna.", 4000)
        elif status == VaultStatus.WRONG_PASSWORD:
            self.notif.show_msg("err", "Password salah atau file corrupted! Coba lagi.")
        elif status == VaultStatus.OVERWRITE_NEEDED:
            self._konfirmasi_timpa = True
            self.btn_aksi.setTextLabels(
                "TIMPA FILE YANG ADA", "Klik lagi untuk memaksa ekstrak"
            )
            self.btn_aksi.setEnabled(True)
            self.notif.show_msg("warn", f"'{msg}' sudah ada! Klik lagi untuk menimpa.")
        else:
            self.notif.show_msg("err", f"Error: {msg}", 8000)
