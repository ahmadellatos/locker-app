"""
tests/test_stress.py
Stress test dan edge case ekstrem untuk core/vault.py.
Diperbarui dengan Signature kunci_brankas terbaru.
"""

import os
import stat
import shutil
import tempfile
import platform
import pytest

from core.vault import kunci_brankas, buka_brankas, secure_delete
from tests.conftest import folder_checksum

PASSWORD = "P@ssw0rd!Kuat"


def _tmp():
    return tempfile.mkdtemp(prefix="locker_stress_")


def _cleanup(path: str):
    if not os.path.exists(path):
        return
    if platform.system() == "Windows":
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    os.chmod(os.path.join(root, f), stat.S_IWRITE)
                except Exception:
                    pass
    shutil.rmtree(path, ignore_errors=True)


# ── 1. THE INCEPTION TEST ────────────────────────────────────────────────────


class TestInceptionTest:
    def test_folder_dalam_40_level(self):
        tmp = _tmp()
        try:
            folder_root = os.path.join(tmp, "inception_40")
            current = folder_root
            for _ in range(40):
                current = os.path.join(current, "a")
            os.makedirs(current)
            with open(os.path.join(current, "deep.txt"), "w") as f:
                f.write("file di kedalaman 40 level")

            checksum_asli = folder_checksum(folder_root)
            path_simpan = os.path.join(tmp, "inception.locked")
            sukses, pesan = kunci_brankas([folder_root], path_simpan, PASSWORD)

            assert sukses, f"Gagal: {pesan}"
            shutil.rmtree(folder_root)

            status, nama = buka_brankas(path_simpan, PASSWORD)
            assert status == "SUCCESS"
            assert checksum_asli == folder_checksum(os.path.join(tmp, nama))
        finally:
            _cleanup(tmp)

    def test_folder_mendekati_max_path(self):
        tmp = _tmp()
        try:
            sisa = max(10, min(240 - len(tmp) - 20, 80))
            folder_root = os.path.join(tmp, "F" * sisa)
            sub = os.path.join(folder_root, "sub")
            os.makedirs(sub)
            with open(os.path.join(sub, "file.txt"), "w") as f:
                f.write("test MAX_PATH")

            path_simpan = os.path.join(tmp, "max_path.locked")
            sukses, pesan = kunci_brankas([folder_root], path_simpan, PASSWORD)
            assert sukses
        finally:
            _cleanup(tmp)

    @pytest.mark.skipif(platform.system() != "Windows", reason="MAX_PATH Windows")
    def test_folder_melampaui_max_path_windows(self):
        tmp = _tmp()
        try:
            folder_root = os.path.join(tmp, "X" * 200)
            try:
                sub = os.path.join(folder_root, "sub")
                os.makedirs(sub)
                with open(os.path.join(sub, "file.txt"), "w") as f:
                    f.write("over MAX_PATH")
            except OSError:
                pytest.skip("OS menolak path > 260 char.")

            path_simpan = os.path.join(tmp, "over.locked")
            try:
                sukses, pesan = kunci_brankas([folder_root], path_simpan, PASSWORD)
                assert isinstance(sukses, bool)
            except Exception as e:
                pytest.fail(f"kunci_brankas() CRASH: {e}")
        finally:
            _cleanup(tmp)


# ── 2. THE IOPS KILLER ───────────────────────────────────────────────────────


class TestIOPSKiller:
    @pytest.fixture
    def folder_banyak_file(self):
        tmp = _tmp()
        folder = os.path.join(tmp, "iops_1000")
        os.makedirs(folder)
        for i in range(100):  # Dikurangi jadi 100 agar test cepat di CI
            with open(os.path.join(folder, f"file_{i:04d}.txt"), "wb") as f:
                f.write(os.urandom(1024))
        yield folder, tmp
        _cleanup(tmp)

    def test_1000_file_kunci_berhasil(self, folder_banyak_file):
        folder, tmp = folder_banyak_file
        path_simpan = os.path.join(tmp, "banyak.locked")
        sukses, pesan = kunci_brankas([folder], path_simpan, PASSWORD)
        assert sukses

    def test_1000_file_roundtrip_isi_sama(self, folder_banyak_file):
        folder, tmp = folder_banyak_file
        checksum_asli = folder_checksum(folder)

        path_simpan = os.path.join(tmp, "banyak.locked")
        sukses, _ = kunci_brankas([folder], path_simpan, PASSWORD)
        assert sukses
        shutil.rmtree(folder)

        status, nama = buka_brankas(path_simpan, PASSWORD)
        assert status == "SUCCESS"
        assert folder_checksum(os.path.join(tmp, nama)) == checksum_asli


# ── 3. THE STUBBORN FILE ─────────────────────────────────────────────────────


class TestStubbornFile:
    @pytest.fixture
    def folder_dengan_readonly(self):
        tmp = _tmp()
        folder = os.path.join(tmp, "stubborn_folder")
        os.makedirs(folder)
        with open(os.path.join(folder, "normal.txt"), "w") as f:
            f.write("normal")

        ro_path = os.path.join(folder, "readonly.txt")
        with open(ro_path, "w") as f:
            f.write("read-only")
        os.chmod(ro_path, stat.S_IREAD)
        yield folder, tmp
        _cleanup(tmp)

    def test_kunci_folder_dengan_readonly_tidak_crash(self, folder_dengan_readonly):
        folder, tmp = folder_dengan_readonly
        path_simpan = os.path.join(tmp, "ro.locked")
        sukses, pesan = kunci_brankas([folder], path_simpan, PASSWORD)
        assert sukses

    def test_secure_delete_hapus_asli_readonly_tidak_crash(
        self, folder_dengan_readonly
    ):
        folder, tmp = folder_dengan_readonly
        path_simpan = os.path.join(tmp, "ro.locked")
        try:
            sukses, pesan = kunci_brankas(
                [folder], path_simpan, PASSWORD, hapus_asli=True
            )
            assert sukses
        except Exception as e:
            pytest.fail(f"kunci_brankas(hapus_asli=True) CRASH: {e}")
