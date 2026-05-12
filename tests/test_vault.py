"""
tests/test_vault.py
Unit + Integration test untuk core/vault.py.
Telah diperbaiki untuk menyesuaikan dengan signature API 3-argumen (paths, path_simpan, password).
"""

import os
import shutil
import pytest

from core.vault import kunci_brankas, buka_brankas, secure_delete
from tests.conftest import folder_checksum

# ── Helper ────────────────────────────────────────────────────────────────────

PASSWORD_BENAR = "P@ssw0rd!Kuat123"
PASSWORD_SALAH = "password_salah_banget"


def kunci_dan_dapat_path(folder, password=PASSWORD_BENAR, hapus=False, cb=None):
    """Helper: kunci folder, return path file .locked yang dihasilkan."""
    base_dir = os.path.dirname(folder)
    path_simpan = os.path.join(base_dir, f"{os.path.basename(folder)}.locked")

    locked_before = {f for f in os.listdir(base_dir) if f.endswith(".locked")}
    sukses, pesan = kunci_brankas(
        [folder], path_simpan, password, hapus_asli=hapus, progress_cb=cb
    )

    assert sukses is True, f"kunci_brankas gagal: {pesan}"
    assert os.path.exists(path_simpan), "File target tidak terbentuk"
    return path_simpan


# ── Happy Path ────────────────────────────────────────────────────────────────


class TestHappyPath:

    def test_kunci_menghasilkan_file_locked(self, sample_folder):
        base_dir = os.path.dirname(sample_folder)
        path_simpan = os.path.join(base_dir, "test_file.locked")

        sukses, pesan = kunci_brankas([sample_folder], path_simpan, PASSWORD_BENAR)

        assert sukses is True
        assert os.path.exists(path_simpan)

    def test_kunci_pesan_sukses(self, sample_folder):
        base_dir = os.path.dirname(sample_folder)
        path_simpan = os.path.join(base_dir, "test_file.locked")

        _, pesan = kunci_brankas([sample_folder], path_simpan, PASSWORD_BENAR)
        assert "Brankas berhasil dikunci" in pesan

    def test_kunci_lalu_buka_isi_sama(self, sample_folder):
        checksum_sebelum = folder_checksum(sample_folder)
        locked_path = kunci_dan_dapat_path(sample_folder)
        base_dir = os.path.dirname(locked_path)

        shutil.rmtree(sample_folder)

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "SUCCESS"

        folder_restored = os.path.join(base_dir, nama)
        checksum_sesudah = folder_checksum(folder_restored)

        assert checksum_sebelum == checksum_sesudah

    def test_buka_mengembalikan_nama_folder(self, sample_folder):
        locked_path = kunci_dan_dapat_path(sample_folder)
        shutil.rmtree(sample_folder)

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "SUCCESS"
        assert nama == os.path.basename(sample_folder)


# ── Wrong Password ────────────────────────────────────────────────────────────


class TestWrongPassword:

    def test_wrong_password_return_status(self, sample_folder):
        locked_path = kunci_dan_dapat_path(sample_folder)
        shutil.rmtree(sample_folder)

        status, msg = buka_brankas(locked_path, PASSWORD_SALAH)
        assert status == "WRONG_PW"
        assert msg is None

    def test_wrong_password_tidak_buat_folder(self, sample_folder, tmp_dir):
        locked_path = kunci_dan_dapat_path(sample_folder)
        shutil.rmtree(sample_folder)

        folder_before = set(os.listdir(tmp_dir))
        buka_brankas(locked_path, PASSWORD_SALAH)
        folder_after = set(os.listdir(tmp_dir))

        new_items = folder_after - folder_before
        assert all(item.endswith(".locked") for item in new_items)

    def test_password_mirip_tetap_gagal(self, sample_folder):
        locked_path = kunci_dan_dapat_path(sample_folder, password="Password123!")
        shutil.rmtree(sample_folder)

        status, _ = buka_brankas(locked_path, "Password123?")
        assert status == "WRONG_PW"


# ── File Corrupt ──────────────────────────────────────────────────────────────


class TestFileCorrupt:

    def test_file_terlalu_kecil(self, tmp_dir):
        path = os.path.join(tmp_dir, "kecil.locked")
        with open(path, "wb") as f:
            f.write(b"x" * 10)

        status, msg = buka_brankas(path, PASSWORD_BENAR)
        assert status == "ERROR"

    def test_file_terpotong_di_tengah(self, sample_folder, tmp_dir):
        locked_path = kunci_dan_dapat_path(sample_folder)
        size = os.path.getsize(locked_path)

        with open(locked_path, "rb") as f:
            data = f.read(size // 2)

        terpotong = os.path.join(tmp_dir, "terpotong.locked")
        with open(terpotong, "wb") as f:
            f.write(data)

        status, _ = buka_brankas(terpotong, PASSWORD_BENAR, force=True)
        assert status in ("WRONG_PW", "ERROR")

    def test_file_kosong(self, tmp_dir):
        path = os.path.join(tmp_dir, "kosong.locked")
        open(path, "wb").close()

        status, msg = buka_brankas(path, PASSWORD_BENAR)
        assert status == "ERROR"


# ── Overwrite Flow ────────────────────────────────────────────────────────────


class TestOverwrite:

    def test_overwrite_prompt_jika_folder_ada(self, sample_folder):
        locked_path = kunci_dan_dapat_path(sample_folder)
        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "OVERWRITE"

    def test_force_true_timpa_folder(self, sample_folder):
        checksum_asli = folder_checksum(sample_folder)
        locked_path = kunci_dan_dapat_path(sample_folder)

        with open(os.path.join(sample_folder, "dokumen.txt"), "w") as f:
            f.write("ISI YANG SUDAH DIUBAH")

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR, force=True)
        assert status == "SUCCESS"


# ── Hapus Asli ────────────────────────────────────────────────────────────────


class TestHapusAsli:

    def test_hapus_asli_true_menghapus_folder(self, sample_folder):
        base_dir = os.path.dirname(sample_folder)
        path_simpan = os.path.join(base_dir, "hapus_asli.locked")
        sukses, _ = kunci_brankas(
            [sample_folder], path_simpan, PASSWORD_BENAR, hapus_asli=True
        )
        assert sukses is True
        assert not os.path.exists(sample_folder)

    def test_hapus_asli_false_tidak_menghapus(self, sample_folder):
        base_dir = os.path.dirname(sample_folder)
        path_simpan = os.path.join(base_dir, "tidak_dihapus.locked")
        sukses, _ = kunci_brankas(
            [sample_folder], path_simpan, PASSWORD_BENAR, hapus_asli=False
        )
        assert sukses is True
        assert os.path.exists(sample_folder)


# ── Progress Callback ─────────────────────────────────────────────────────────


class TestProgressCallback:

    def test_kunci_progress_dipanggil(self, sample_folder):
        progress_values = []
        path_simpan = os.path.join(os.path.dirname(sample_folder), "prog.locked")
        kunci_brankas(
            [sample_folder],
            path_simpan,
            PASSWORD_BENAR,
            progress_cb=lambda v: progress_values.append(v),
        )
        assert len(progress_values) > 0

    def test_kunci_progress_berakhir_di_1(self, sample_folder):
        progress_values = []
        path_simpan = os.path.join(os.path.dirname(sample_folder), "prog2.locked")
        kunci_brankas(
            [sample_folder],
            path_simpan,
            PASSWORD_BENAR,
            progress_cb=lambda v: progress_values.append(v),
        )
        assert progress_values[-1] == 1.0


# ── Edge Cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:

    def test_folder_kosong(self, empty_folder):
        locked_path = kunci_dan_dapat_path(empty_folder)
        shutil.rmtree(empty_folder)

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "SUCCESS"

    def test_nama_folder_dengan_spasi(self, sample_folder_spasi):
        locked_path = kunci_dan_dapat_path(sample_folder_spasi)
        shutil.rmtree(sample_folder_spasi)

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "SUCCESS"

    def test_file_unicode(self, sample_folder_unicode):
        checksum_asli = folder_checksum(sample_folder_unicode)
        locked_path = kunci_dan_dapat_path(sample_folder_unicode)
        shutil.rmtree(sample_folder_unicode)

        status, nama = buka_brankas(locked_path, PASSWORD_BENAR)
        assert status == "SUCCESS"

    def test_folder_path_tidak_ada(self, tmp_dir):
        path_fiktif = os.path.join(tmp_dir, "tidak_ada_sama_sekali")
        path_simpan = os.path.join(tmp_dir, "out.locked")
        sukses, pesan = kunci_brankas([path_fiktif], path_simpan, PASSWORD_BENAR)
        assert sukses is False
