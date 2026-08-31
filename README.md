# TikTok Drama & Video Batch Downloader Pro v1.3.0 (with 1-Click Browser Bridge)

កម្មវិធី Desktop និង Browser Integration សម្រាប់ស្កេន និងទាញយកវីដេអូភាគ TikTok Drama (កម្រិត HD No-Watermark) ដោយស្វ័យប្រវត្តិតែមួយ Click។

---

### ១. លក្ខណៈសម្បត្តិពិសេស (Features in v1.3.0)
- ⚡ **បើកលឿនបំផុត (Fast Startup < 0.1s)**៖ ប្រើប្រាស់ `tkinter` ស្រាល មិនស៊ី RAM (~២០ MB)។
- 🌐 **1-Click Browser Bridge (Port 54321)**៖ ស្កេនភាគលើ Browser រួចចុច **"🚀 Send to Desktop App"** វានឹងរត់ចូលកម្មវិធី Desktop ភ្លាមៗដោយមិនបាច់ Copy/Paste ដោយដៃ។
- 🎬 **Lossless Episode Merger**៖ ផ្គុំគ្រប់ភាគទាំងអស់ចូលគ្នាជា Full Movie (`{Title}_Full_Movie.mp4`) ក្នុងរយៈពេលត្រឹមតែ ២ វិនាទី (ប្រើ FFmpeg Concat ដោយមិនធ្លាក់គុណភាព)។
- 🎵 **Audio Extraction Mode**៖ ជម្រើសទាញយកតែសំឡេង Audio (`.mp3`) សម្រាប់បទចម្រៀង ឬ Podcast។
- 📺 **Plex / Jellyfin / Kodi Metadata (`tvshow.nfo`)**៖ បង្កើត Poster និង `tvshow.nfo` ដោយស្វ័យប្រវត្តិសម្រាប់ Home Media Server។
- 🔄 **Resumable HTTP 206 Downloads**៖ បន្តទាញយកលើ File `.part` ដោយមិនបាច់ចាប់ផ្តើមពី 0% ឡើងវិញបើដាច់ Network។
- 🔍 **Queue Search & Status Filter**៖ ស្វែងរកលេខភាគ និង Filter មើលតែភាគដែល Pending, Failed, ឬ Done។
- 🎯 **HD No-Watermark**៖ វីដេអូច្បាស់កម្រិត HD 1080p និងគ្មានជាប់ Logo Watermark។
- 📂 **Directory & File Management**៖ មានប៊ូតុងជ្រើសរើស Folder និងប៊ូតុង **"📂 Open Folder"** ងាយស្រួលឆែក File វីដេអូ។

---

### ២. របៀបដំណើរការកម្មវិធី Desktop (How to Run Desktop App)

- **លើ Windows**៖ គ្រាន់តែ Double-click លើ File `run.bat`
- **លើ Linux / macOS**៖ 
  ```bash
  ./run.sh
  ```

---

### ៣. របៀបប្រើប្រាស់ 1-Click Send ពី Browser (Browser Integration)

មាន ២ ជម្រើសក្នុងការដំណើរការលើ Browser៖

#### ជម្រើស A (បង្កើតជា Bookmarklet លើ Browser Bookmarks Bar - ងាយស្រួលបំផុត)
1. បើក Browser របស់អ្នក (Chrome, Edge, Brave, etc.) ហើយចុច **Ctrl + Shift + O** (បើក Bookmark Manager)។
2. ចុច **Add Bookmark**៖
   - **Name**: `TikTok Extractor`
   - **URL**: Copy កូដទាំងអស់នៅក្នុង File [bookmarklet.txt](bookmarklet.txt) យកមក Paste ចូល។
3. ពេលអ្នកបើកមើលរឿងលើ TikTok Drama (Tab "About") ➔ គ្រាន់តែ**ចុចលើ Bookmark នោះតែម្តង** វានឹងស្កេនភាគទាំងអស់ ហើយបញ្ជូនចូល Desktop App ដោយស្វ័យប្រវត្តិ!

#### ជម្រើស B (ដំណើរការតាម Browser Console F12)
1. បើកទំព័រ TikTok Drama (Tab "About")
2. ចុច **F12** (ឬ Right-click ➔ Inspect) រួចចូលទៅកាន់ Tab **Console**
3. Copy កូដទាំងអស់ក្នុង [extractor.js](extractor.js) យកមក Paste រួចចុច **Enter**
4. ផ្ទាំង Modal នឹងបង្ហាញឡើង ➔ ចុចប៊ូតុង **"🚀 Send to Desktop App"**!

---

### ៤. របៀប Build ជា Standalone Executable (Windows & Linux)

កម្មវិធីមាន Script សម្រាប់ Build ជា Production ស្វ័យប្រវត្តិតែមួយ Command៖

#### លើ Linux (Ubuntu, Debian, Fedora, Arch, etc.)
```bash
./build_linux.sh
```
> Output នឹងទទួលបាន Folder `dist/TikTokDownloader`, `.desktop` Launcher និង Archive `dist/TikTokDownloader-Linux-x86_64.tar.gz` សម្រាប់ចែកចាយ។

#### លើ Windows (10/11)
```cmd
build_windows.bat
```
> Output នឹងទទួលបាន `dist\TikTokDownloader.exe` ឯករាជ្យ និង Archive `dist\TikTokDownloader-Windows-x64.zip` (ដំណើរការបានដោយមិនបាច់មាន Python លើម៉ាស៊ីន)។

---

### ៥. CI/CD Automated Releases (GitHub Actions)
គម្រោងនេះត្រូវបានបំពាក់ដោយ GitHub Actions Workflow (`.github/workflows/build_release.yml`)។ រាល់ពេលបង្កើត Tag ថ្មី (ឧ. `v1.3.0`) ប្រព័ន្ធនឹង Auto-build `.exe` និង Linux Binary រួចបង្ហោះចូលទៅកាន់ [GitHub Releases](https://github.com/vathsathya/yanich-tiktok-downloader/releases) ដោយស្វ័យប្រវត្តិ។

