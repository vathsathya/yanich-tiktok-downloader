# TikTok Drama & Video Batch Downloader (with 1-Click Browser Bridge)

កម្មវិធី Desktop និង Browser Integration សម្រាប់ស្កេន និងទាញយកវីដេអូភាគ TikTok Drama (កម្រិត HD No-Watermark) ដោយស្វ័យប្រវត្តិតែមួយ Click។

---

### ១. លក្ខណៈសម្បត្តិពិសេស (Features)
- ⚡ **បើកលឿនបំផុត (Fast Startup < 0.1s)**៖ ប្រើប្រាស់ `tkinter` ស្រាល មិនស៊ី RAM (~២០ MB)។
- 🌐 **1-Click Browser Bridge (Port 54321)**៖ ស្កេនភាគលើ Browser រួចចុច **"🚀 Send to Desktop App"** វានឹងរត់ចូលកម្មវិធី Desktop ភ្លាមៗដោយមិនបាច់ Copy/Paste ដោយដៃ។
- 📥 **Batch Downloading**៖ ទាញយកវីដេអូជាច្រើនភាគបន្តបន្ទាប់គ្នាដោយស្វ័យប្រវត្តិ។
- 🎯 **HD No-Watermark**៖ វីដេអូច្បាស់កម្រិត HD និងគ្មានជាប់ Logo Watermark។
- 📂 **Directory & File Management**៖ មានប៊ូតុងជ្រើសរើស Folder និងប៊ូតុង **"📂 Open Folder"** ងាយស្រួលឆែក File វីដេអូ។
- ⏹️ **Stop & Safe Cancellation**៖ អាចចុចបញ្ឈប់ការទាញយកបានគ្រប់ពេលដោយសុវត្ថិភាព។

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
   - **URL**: Copy កូដទាំងអស់នៅក្នុង File [bookmarklet.txt](file:///home/yanich/projects/yanich-tiktok-downloader/bookmarklet.txt) យកមក Paste ចូល។
3. ពេលអ្នកបើកមើលរឿងលើ TikTok Drama (Tab "About") ➔ គ្រាន់តែ**ចុចលើ Bookmark នោះតែម្តង** វានឹងស្កេនភាគទាំងអស់ ហើយបញ្ជូនចូល Desktop App ដោយស្វ័យប្រវត្តិ!

#### ជម្រើស B (ដំណើរការតាម Browser Console F12)
1. បើកទំព័រ TikTok Drama (Tab "About")
2. ចុច **F12** (ឬ Right-click ➔ Inspect) រួចចូលទៅកាន់ Tab **Console**
3. Copy កូដទាំងអស់ក្នុង [extractor.js](file:///home/yanich/projects/yanich-tiktok-downloader/extractor.js) យកមក Paste រួចចុច **Enter**
4. ផ្ទាំង Modal នឹងបង្ហាញឡើង ➔ ចុចប៊ូតុង **"🚀 Send to Desktop App"**!

---

### ៤. របៀប Build ចេញជា File `.exe` តែមួយ (សម្រាប់ Windows)

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name "TikTok_Downloader" main.py
```
> File `.exe` នឹងស្ថិតនៅក្នុង Folder `dist/TikTok_Downloader.exe`
