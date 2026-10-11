# IndoSubMod — Panduan Penggunaan

**Versi 1.6.47 · Windows 64-bit**

## Instalasi

1. Buka `IndoSubModSetup.exe` dengan klik dua kali.
2. Pilih folder instalasi dan komponen opsional di jendela pemasang. Komponen aplikasi dan pengenalan suara wajib; model terjemahan offline dan pintasan desktop bersifat opsional.
3. Klik **Setujui & Instal** untuk menyatakan persetujuan terhadap ketentuan, lalu tunggu sampai proses selesai. Pemasang menampilkan tahap serta persentase kemajuan.
4. Setelah selesai, jalankan IndoSubMod dari pintasan desktop atau menu Start. Tombol **Dukung Kreator** tersedia di pemasang dan aplikasi.

Dengan mengeklik tombol **Setujui & Instal**, pengguna menyatakan telah membaca dan menyetujui ketentuan berikut. IndoSubMod adalah prototipe uji untuk pengenalan dan evaluasi, hanya untuk penggunaan nonkomersial. Aplikasi ini tidak memberikan hak untuk menjual, mengubah, atau mendistribusikan video yang dipilih; hak atas video tetap berada pada pemegang hak. File sumber tidak diubah: aplikasi membuat file MKV terpisah dengan trek subtitle, tanpa mengodekan ulang video atau audio. Akurasi hasil tidak dijamin; pengguna bertanggung jawab atas hak penggunaan video dan pemeriksaan subtitle. Setelah instalasi, klik **Dukung Kreator** untuk membuka halaman Buy Me a Coffee.

> Instalasi pertama memerlukan koneksi internet untuk mengunduh Python, pustaka, dan model suara. Jika memilih terjemahan offline, model Argos English → Indonesian juga akan diunduh. Setelah persiapan selesai, mode offline tidak memerlukan internet.

## Membuat video bersubtitel

1. Buka IndoSubMod dan pilih mode terjemahan: **Model lokal Anda (Ollama)**, **Offline (Argos)**, atau **GPT online**.
2. Pilih gaya bahasa Indonesia: otomatis, resmi, atau akrab.
3. Klik **Pilih video** dan pilih berkas video.
4. Klik **Buat video dengan subtitle**. IndoSubMod mengenali ucapan dengan Whisper, menerjemahkannya ke bahasa Inggris, lalu menerjemahkan teks Inggris ke bahasa Indonesia.
5. Pilih lokasi dan nama berkas hasil pada dialog penyimpanan.

File video sumber tetap utuh. Hasil berupa file MKV baru dengan trek subtitle terpisah yang dapat diaktifkan atau dinonaktifkan di pemutar video; video dan audio tidak dikodekan ulang. Berkas subtitle `.srt` juga disimpan. Latar abu-abu tipis di belakang teks subtitle dapat diatur atau dinonaktifkan melalui pengaturan subtitle.

## Mode terjemahan

- **Offline:** Argos Translate menerjemahkan dari English ke Indonesian secara lokal. Tidak memerlukan API key dan teks tidak dikirim ke layanan online.
- **Model lokal Anda (Ollama):** IndoSubMod hanya mengirim teks ke API Ollama lokal di komputer ini (`127.0.0.1:11434`). Penerjemahan tidak menggunakan API cloud atau internet. Pemasang dapat memasang Ollama dan model terjemahan lokal Qwen2.5 1.5B secara otomatis jika komponennya dipilih; pilih model tersebut di aplikasi. Ollama adalah runtime lokal, sedangkan model pilihan Anda yang menerjemahkan. Mengunduh Ollama dan bobot model memerlukan ruang disk dan biasanya koneksi internet; setelah diunduh, inferensi dapat berjalan luring.
- **GPT online:** memerlukan koneksi internet dan OpenAI API key. Teks bahasa Inggris yang dikenali dikirim ke OpenAI untuk diterjemahkan. Biaya API dapat berlaku terpisah dari langganan ChatGPT.

Pilih mode online hanya jika Anda menyetujui pemrosesan teks melalui layanan tersebut. Agar teks subtitle tidak dikirim ke cloud, gunakan model lokal atau Argos. Pengenalan ucapan dilakukan secara lokal oleh Whisper setelah model tersedia.

## Memperbaiki terjemahan

Buka **Nilai terjemahan terakhir**, pilih baris subtitle, lalu tandai sebagai baik/buruk atau masukkan koreksi. Koreksi dan umpan balik disimpan secara lokal di `%LOCALAPPDATA%\IndoSubMod\feedback.json` dan dapat membantu hasil berikutnya. Ini adalah memori umpan balik perangkat lunak, bukan rasa sakit atau dopamin biologis.

## Penghapusan dan pemecahan masalah

- Hapus aplikasi melalui **Pengaturan Windows → Aplikasi → Aplikasi terinstal → IndoSubMod**.
- Log instalasi: `%LOCALAPPDATA%\IndoSubMod\install.log`.
- Log Python Setup: `%LOCALAPPDATA%\IndoSubMod\python-install.log`.
- Jika instalasi gagal, buka log dari jendela pemasang dan periksa koneksi internet serta ruang disk.

Video yang didukung bergantung pada format yang dapat dibaca FFmpeg, termasuk MP4, MKV, MOV, AVI, dan WebM. Kecepatan pemrosesan bergantung pada durasi video dan kemampuan komputer.

---

# IndoSubMod — User Guide

**Version 1.6.47 · Windows 64-bit**

## Installation

1. Double-click `IndoSubModSetup.exe`.
2. Choose an installation folder and any optional components in the installer. The application and speech recognition components are required; the offline translation model and desktop shortcut are optional.
3. Click **Agree & Install** to confirm acceptance of the terms, then wait for completion. The installer displays the current stage and progress percentage.
4. When setup finishes, launch IndoSubMod from the desktop shortcut or Start menu. The **Support the Creator** button is available in both the installer and the app.

By clicking **Agree & Install**, the user confirms they have read and accept these terms. IndoSubMod is a test prototype for familiarization and evaluation, for non-commercial use only. It does not grant rights to sell, alter, or distribute selected videos; video rights remain with their respective owners. The source file is left unchanged: the app creates a separate MKV with a subtitle track, without re-encoding the video or audio. Results are not guaranteed; users are responsible for video-use rights and subtitle review. After installation, click **Support the Creator** to open the Buy Me a Coffee page.

> The first installation requires an internet connection to download Python, libraries, and the speech model. If you select offline translation, the Argos English → Indonesian model is downloaded too. Once setup is complete, offline mode works without an internet connection.

## Creating a subtitled video

1. Open IndoSubMod and choose a translation mode: **Your local model (Ollama)**, **Offline (Argos)**, or **GPT online**.
2. Choose an Indonesian style: automatic, formal, or friendly.
3. Click **Choose video** and select a video file.
4. Click **Create video with subtitles**. IndoSubMod recognizes speech with Whisper, translates it into English, and then translates the English text into Indonesian.
5. Choose the output file name and location in the save dialog.

The source video file remains unchanged. The output is a new MKV with a separate subtitle track that can be enabled or disabled in a video player; video and audio are not re-encoded. An `.srt` subtitle file is also saved. The subtle gray background behind subtitles can be adjusted or disabled in subtitle settings.

## Translation modes

- **Offline:** Argos Translate translates English to Indonesian locally. No API key is required, and text is not sent to an online service.
- **Your local model (Ollama):** IndoSubMod sends text only to Ollama's local API on this computer (`127.0.0.1:11434`). Translation does not use a cloud API or internet. When selected, the installer installs Ollama and downloads the Qwen2.5 1.5B translation model; select it in the app. Ollama is the local runtime, and your selected model performs the translation. Downloading Ollama and model weights takes disk space and usually requires internet; after download, inference can run offline.
- **GPT online:** requires an internet connection and an OpenAI API key. Recognized English text is sent to OpenAI for translation. API charges may apply separately from a ChatGPT subscription.

Choose online mode only if you agree to have the text processed by that service. To keep subtitle text off cloud services, choose the local model or Argos. Speech recognition runs locally with Whisper once its model is available.

## Correcting translations

Open **Rate the last translation**, select a subtitle line, and mark it as good or poor, or enter a correction. Corrections and feedback are stored locally in `%LOCALAPPDATA%\IndoSubMod\feedback.json` and may improve future results. This is software feedback memory, not biological pain or dopamine.

## Uninstalling and troubleshooting

- Remove the application through **Windows Settings → Apps → Installed apps → IndoSubMod**.
- Installation log: `%LOCALAPPDATA%\IndoSubMod\install.log`.
- Python Setup log: `%LOCALAPPDATA%\IndoSubMod\python-install.log`.
- If setup fails, open the log from the installer window and check your internet connection and available disk space.

Supported video formats depend on what FFmpeg can read, including MP4, MKV, MOV, AVI, and WebM. Processing speed depends on video length and computer performance.
