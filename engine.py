import os
import shutil
import uuid
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Ukuran sepotong data yang ditarik ke RAM (64 KB)
# Semakin besar bisa sedikit lebih cepat, tapi memakan memori. 64KB - 1MB adalah ideal.
CHUNK_SIZE = 64 * 1024 

def buat_kunci_dari_password(password: str, salt: bytes):
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
        backend=default_backend()
    )
    return kdf.derive(password.encode())

def kunci_brankas_logic(nama_folder, password_kamu):
    file_zip = nama_folder + ".zip"
    path_simpan = None
    try:
        salt = os.urandom(16)
        kunci = buat_kunci_dari_password(password_kamu, salt)
        nonce = os.urandom(12) 

        while True:
            id_acak = uuid.uuid4().hex[:8]
            nama_file_kunci = f"brankas_{id_acak}.locked"
            path_simpan = os.path.join(os.path.dirname(nama_folder), nama_file_kunci)
            if not os.path.exists(path_simpan): break

        abs_path = os.path.abspath(nama_folder)
        parent_dir = os.path.dirname(abs_path)
        target_dir = os.path.basename(abs_path)
        
        # Buat file zip sementara
        shutil.make_archive(nama_folder, 'zip', parent_dir, target_dir)

        # Setup Encryptor mode Streaming
        encryptor = Cipher(
            algorithms.AES(kunci),
            modes.GCM(nonce),
            backend=default_backend()
        ).encryptor()

        # Mulai tulis ke file target (Brankas)
        with open(path_simpan, "wb") as fk:
            # 1. Tulis gerbong metadata publik (Salt + Nonce)
            fk.write(salt)
            fk.write(nonce)
            
            # 2. Siapkan dan Enkripsi metadata rahasia (Panjang Nama + Nama Folder)
            nama_bytes = target_dir.encode('utf-8')
            panjang_nama = len(nama_bytes).to_bytes(2, byteorder='big')
            fk.write(encryptor.update(panjang_nama + nama_bytes))
            
            # 3. Streaming Enkripsi File Zip (Solusi Anti-Memory Error!)
            with open(file_zip, "rb") as fz:
                while True:
                    chunk = fz.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fk.write(encryptor.update(chunk))
            
            # 4. Finalisasi enkripsi dan tulis TAG (16 byte pengaman GCM) di paling akhir
            encryptor.finalize()
            fk.write(encryptor.tag)

        # Bersihkan jejak
        os.remove(file_zip)
        shutil.rmtree(nama_folder)
        
        size_kb = os.path.getsize(path_simpan) / 1024
        return True, f"Berhasil!\n\nNama Brankas: {nama_file_kunci}\nUkuran: {size_kb:.1f} KB"
        
    except Exception as e:
        if os.path.exists(file_zip): os.remove(file_zip)
        if path_simpan and os.path.exists(path_simpan): os.remove(path_simpan)
        return False, str(e)

def buka_brankas_logic(path_file_kunci, password_kamu, force=False):
    file_zip_sementara = None
    try:
        ukuran_file_total = os.path.getsize(path_file_kunci)
        
        with open(path_file_kunci, "rb") as fk:
            # 1. Baca metadata publik
            salt = fk.read(16)
            nonce = fk.read(12)
            
            # 2. Lompat ke ujung file untuk mengambil Tag GCM (16 byte terakhir)
            fk.seek(-16, os.SEEK_END)
            tag = fk.read(16)
            
            # 3. Hitung panjang area Ciphertext murni
            # Total Size - Salt(16) - Nonce(12) - Tag(16)
            panjang_ciphertext = ukuran_file_total - 44
            
            # Kembali ke posisi awal ciphertext
            fk.seek(28) 

            # Setup Decryptor mode Streaming
            kunci = buat_kunci_dari_password(password_kamu, salt)
            decryptor = Cipher(
                algorithms.AES(kunci),
                modes.GCM(nonce, tag),
                backend=default_backend()
            ).decryptor()

            # 4. Baca chunk pertama untuk mengekstrak Nama Folder terenkripsi
            bytes_left = panjang_ciphertext
            first_chunk_size = min(1024, bytes_left) # Cukup 1KB pertama untuk header
            first_chunk = fk.read(first_chunk_size)
            bytes_left -= len(first_chunk)
            
            try:
                decrypted_first = decryptor.update(first_chunk)
            except Exception:
                return "WRONG_PW", None

            # Ekstrak metadata nama dari data yang terdekripsi
            panjang_nama = int.from_bytes(decrypted_first[:2], byteorder='big')
            nama_folder_tujuan = decrypted_first[2:2 + panjang_nama].decode('utf-8')
            
            # Cek potensi Overwrite SEBELUM proses dekripsi file berlanjut
            base_dir = os.path.dirname(path_file_kunci)
            path_tujuan_full = os.path.join(base_dir, nama_folder_tujuan)
            
            if os.path.exists(path_tujuan_full) and not force:
                return "OVERWRITE", nama_folder_tujuan

            # 5. Lanjut Streaming Dekripsi isi file Zip
            file_zip_sementara = os.path.join(base_dir, "temp_" + uuid.uuid4().hex[:8] + ".zip")
            with open(file_zip_sementara, "wb") as fz:
                # Tulis sisa blok pertama yang merupakan bagian dari file zip
                fz.write(decrypted_first[2 + panjang_nama:])
                
                # Streaming sisanya
                while bytes_left > 0:
                    chunk = fk.read(min(CHUNK_SIZE, bytes_left))
                    bytes_left -= len(chunk)
                    fz.write(decryptor.update(chunk))
            
            # Verifikasi integritas file! (Akan error jika password/file corrupt)
            try:
                decryptor.finalize() 
            except Exception:
                if os.path.exists(file_zip_sementara): os.remove(file_zip_sementara)
                return "WRONG_PW", None
                
        # 6. Ekstrak dan hapus zip sementara
        shutil.unpack_archive(file_zip_sementara, base_dir, 'zip')
        os.remove(file_zip_sementara)
        
        return "SUCCESS", nama_folder_tujuan
        
    except Exception as e:
        if file_zip_sementara and os.path.exists(file_zip_sementara): 
            os.remove(file_zip_sementara)
        return "ERROR", str(e)