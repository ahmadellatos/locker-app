"""
core/vault.py
Logika utama: kunci folder (enkripsi) dan buka brankas (dekripsi).
Dioptimasi dengan Single-Pass I/O Streaming menggunakan Tarfile + Memory Buffering.
"""
import os
import shutil
import uuid
import tempfile
import tarfile
import zipfile

from .crypto import CHUNK_SIZE, derive_key, make_encryptor, make_decryptor, safe_cb

# ── File Operations ───────────────────────────────────────────────────────────

def secure_delete(path: str):
    """
    Menimpa file dengan nol sebelum dihapus.
    PERHATIAN: Tidak menjamin penghapusan aman di SSD/NVMe karena wear leveling.
    Hanya efektif untuk HDD konvensional.
    """
    if not os.path.exists(path):
        return
    if os.path.isfile(path):
        try:
            size = os.path.getsize(path)
            with open(path, "r+b") as f:
                written = 0
                while written < size:
                    chunk = min(CHUNK_SIZE, size - written)
                    f.write(b'\x00' * chunk)
                    written += chunk
            os.remove(path)
        except Exception:
            pass
    elif os.path.isdir(path):
        for root, dirs, files in os.walk(path, topdown=False):
            for name in files:
                secure_delete(os.path.join(root, name))
            for name in dirs:
                try:
                    os.rmdir(os.path.join(root, name))
                except OSError:
                    pass
        try:
            os.rmdir(path)
        except OSError:
            shutil.rmtree(path, ignore_errors=True)


def _unique_output_path(base_dir: str) -> tuple[str, str]:
    """Buat nama file .locked yang unik di base_dir."""
    while True:
        name = f"brankas_{uuid.uuid4().hex[:8]}.locked"
        path = os.path.join(base_dir, name)
        if not os.path.exists(path):
            return name, path


# ── Custom Stream Classes ─────────────────────────────────────────────────────

class EncryptingStream:
    """
    Pipa memori ajaib yang dilengkapi Buffer (Waduk).
    Mencegah overhead karena tarfile melempar data dalam byte yang sangat kecil.
    """
    def __init__(self, target_file, encryptor, progress_cb, total_bytes):
        self.target_file = target_file
        self.encryptor = encryptor
        self.progress_cb = progress_cb
        self.total_bytes = total_bytes
        
        self.bytes_written = 0
        self.buffer = bytearray()
        self.chunk_size = CHUNK_SIZE # Tampung sampai 4MB
        self._last_pct = 0.0
        self._flushed = False

    def write(self, data: bytes):
        self.buffer.extend(data)
        self.bytes_written += len(data)
        
        # THROTTLING: Hanya update UI jika progress bertambah minimal 0.5% (0.005)
        # Mencegah GUI freeze karena dikirimi ratusan ribu sinyal update
        # Di-cap 0.89 karena tar overhead bisa bikin bytes_written > total_bytes
        # (file binary tidak bisa dikompres + tar header metadata)
        if self.total_bytes > 0:
            pct = min(0.89, 0.05 + 0.85 * (self.bytes_written / self.total_bytes))
            if pct - self._last_pct >= 0.005:
                safe_cb(self.progress_cb, pct)
                self._last_pct = pct

        # Jika waduk buffer penuh (>= 4MB), baru proses ke AES dan tembak ke SSD
        if len(self.buffer) >= self.chunk_size:
            encrypted = self.encryptor.update(bytes(self.buffer))
            if encrypted:
                self.target_file.write(encrypted)
            self.buffer.clear() # Kosongkan waduk
            
        return len(data)
        
    def flush(self):
        if self._flushed:       
            return
        self._flushed = True
        if self.buffer:
            encrypted = self.encryptor.update(bytes(self.buffer))
        if encrypted:
            self.target_file.write(encrypted)
        self.buffer.clear()

    def close(self): 
        self.flush()


# ── Public API ────────────────────────────────────────────────────────────────

def kunci_brankas(folder_path: str, password: str,
                  hapus_asli: bool = False,
                  progress_cb=None) -> tuple[bool, str]:
    path_simpan = None
 
    try:
        salt  = os.urandom(16)
        nonce = os.urandom(12)
 
        key = derive_key(password, salt)
        safe_cb(progress_cb, 0.05)
 
        abs_path   = os.path.abspath(folder_path)
        target_dir = os.path.basename(abs_path)
        base_dir   = os.path.dirname(abs_path)
        nama_file, path_simpan = _unique_output_path(base_dir)
 
        total_size = sum(
            os.path.getsize(os.path.join(r, f))
            for r, _, files in os.walk(folder_path)
            for f in files if not os.path.islink(os.path.join(r, f))
        ) or 1

        encryptor = make_encryptor(key, nonce)
        nama_bytes   = target_dir.encode()
        panjang_nama = len(nama_bytes).to_bytes(2, byteorder='big')
 
        with open(path_simpan, "wb") as fk:
            fk.write(salt)
            fk.write(nonce)
            fk.write(encryptor.update(panjang_nama + nama_bytes))
            
            out_stream = EncryptingStream(fk, encryptor, progress_cb, total_size)
            
            # mode 'w|' berarti stream (satu arah) tanpa seek
            with tarfile.open(fileobj=out_stream, mode='w|') as tar:
                tar.add(folder_path, arcname=target_dir)

            # Wajib panggil flush untuk membersihkan sisa data di buffer EncryptingStream
            out_stream.flush()

            fk.write(encryptor.finalize())
            fk.write(encryptor.tag)
 
        safe_cb(progress_cb, 0.90)
        if hapus_asli:
            safe_cb(progress_cb, 0.95)
            secure_delete(folder_path)
 
        size_mb = os.path.getsize(path_simpan) / (1024 * 1024)
        safe_cb(progress_cb, 1.0)
        return True, f"Berhasil!\n\nNama Brankas: {nama_file}\nUkuran: {size_mb:.1f} MB"
 
    except Exception as exc:
        if path_simpan and os.path.exists(path_simpan):
            os.remove(path_simpan)
        return False, str(exc)

def buka_brankas(locked_path: str, password: str,
                 force: bool = False,
                 progress_cb=None) -> tuple[str, str | None]:
    temp_archive = None
    try:
        total_size = os.path.getsize(locked_path)
        if total_size < 44:
            return "ERROR", "File terlalu kecil/rusak."
            
        cipher_len = total_size - 44 

        with open(locked_path, "rb") as fk:
            salt  = fk.read(16)
            nonce = fk.read(12)
            fk.seek(-16, os.SEEK_END)
            tag   = fk.read(16)
            fk.seek(28)

            key       = derive_key(password, salt)
            decryptor = make_decryptor(key, nonce, tag)

            first_sz        = min(1024, cipher_len)
            first_chunk     = fk.read(first_sz)
            bytes_remaining = cipher_len - first_sz

            decrypted_first = decryptor.update(first_chunk)

            try:
                panjang_nama = int.from_bytes(decrypted_first[:2], byteorder='big')
                if panjang_nama > 512:
                    return "WRONG_PW", None
                if len(decrypted_first) < 2 + panjang_nama:
                    return "ERROR", "File brankas rusak atau terpotong."
                nama_folder = decrypted_first[2:2 + panjang_nama].decode('utf-8')
            except Exception:
                return "WRONG_PW", None

            base_dir    = os.path.dirname(locked_path)
            path_tujuan = os.path.join(base_dir, nama_folder)

            if os.path.exists(path_tujuan) and not force:
                return "OVERWRITE", nama_folder

            id_temp      = uuid.uuid4().hex[:8]
            temp_archive = os.path.join(tempfile.gettempdir(), f"dec_temp_{id_temp}.tmp")
            bytes_dec    = first_sz
            last_pct     = 0.0

            with open(temp_archive, "wb") as ft:
                ft.write(decrypted_first[2 + panjang_nama:])
                safe_cb(progress_cb, 0.80 * bytes_dec / (cipher_len or 1))

                while bytes_remaining > 0:
                    chunk            = fk.read(min(CHUNK_SIZE, bytes_remaining))
                    bytes_remaining -= len(chunk)
                    ft.write(decryptor.update(chunk))
                    bytes_dec += len(chunk)
                    
                    # Throttle progress buka brankas juga agar GUI tenang
                    pct = 0.80 * bytes_dec / (cipher_len or 1)
                    if pct - last_pct >= 0.005:
                        safe_cb(progress_cb, pct)
                        last_pct = pct

            try:
                decryptor.finalize()   
            except Exception:
                secure_delete(temp_archive)
                return "WRONG_PW", None

        safe_cb(progress_cb, 0.85)
        
        # SMART AUTO-DETECT & EXTRACT
        if zipfile.is_zipfile(temp_archive):
            with zipfile.ZipFile(temp_archive, 'r') as zf:
                zf.extractall(path=base_dir)
        elif tarfile.is_tarfile(temp_archive):
            with tarfile.open(temp_archive, 'r') as tar:
                tar.extractall(path=base_dir)
        else:
            secure_delete(temp_archive)
            return "ERROR", "Format arsip di dalam brankas tidak dikenali/rusak."

        secure_delete(temp_archive)
        safe_cb(progress_cb, 1.0)
        return "SUCCESS", nama_folder

    except Exception as exc:
        if temp_archive and os.path.exists(temp_archive):
            secure_delete(temp_archive)
        return "ERROR", str(exc)