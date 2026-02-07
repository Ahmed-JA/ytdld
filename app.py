import os, subprocess, requests, time, threading, json, gc
from queue import Queue
from datetime import timedelta

# --- الإعدادات المخفية (WebDAV فقط) ---
# تم حذف دروبوكس وابقاء ويب داف واخفاء معلوماته
WD_INFO = {
    "url": "https://obedientsupporters.co/remote.php/dav/files/Kabil1",
    "user": "kabil1",
    "pass": "XE2tG-6tmFJ-S3gn5-x6YKB-WRaHb"
}

# --- الإعدادات العامة (يمكنك تعديلها هنا) ---
Remote_Dest = "خاص يوتيوب" 
MAIN_FOLDER_NAME = "test"
Playlist_URL = "https://m.youtube.com/watch?v=NPLyrdpCuns"

# نطاق الملفات والجودة
FILE_RANGE = "" 
SORT_BY = "Most Viewed" 
VIDEO_QUALITY = "360p" 
AUDIO_QUALITY = "VBR_Smart_22k"
UPLOAD_MODE = "Audio Only" 

# --- تجهيز بيئة التشغيل ---
conf_path = "up.conf"

def setup_rclone():
    if not os.path.exists("rclone"):
        print("📡 جاري تحميل محرك الرفع...")
        os.system("wget -q https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qj rclone-current-linux-amd64.zip '*/rclone' && chmod +x rclone")
    
    # تشفير كلمة المرور وتوليد ملف الإعدادات صامتاً
    pw_enc = subprocess.check_output(["./rclone", "obscure", WD_INFO["pass"]]).decode().strip()
    config_text = f"[dst]\ntype = webdav\nurl = {WD_INFO['url']}\nuser = {WD_INFO['user']}\npass = {pw_enc}"
    with open(conf_path, "w") as f: f.write(config_text)

setup_rclone()
os.system("pip install -U -q yt-dlp")

# المسار النهائي على السحابة
BASE_PATH = "خاص يوتيوب"
FINAL_DEST = f"MyFiles/{BASE_PATH}/{Remote_Dest}/{MAIN_FOLDER_NAME}".replace("//", "/")

stats = {"v": 0, "a": 0, "size": 0, "start": time.time(), "skipped": 0, "active_up": 0, "total_found": 0}
upload_queue = Queue()
stop_flag = False

def uploader():
    while not stop_flag:
        try:
            item = upload_queue.get(timeout=3)
            if item is None: break
            f_p, sub = item
            stats["active_up"] += 1
            clean_dest = f"dst:{FINAL_DEST}/{sub}".replace("//", "/")
            subprocess.run(["./rclone", "move", f_p, clean_dest, "--config", conf_path, "-q"])
            stats["active_up"] -= 1
            upload_queue.task_done()
            gc.collect()
        except: continue

threading.Thread(target=uploader, daemon=True).start()

# --- التنفيذ الرئيسي ---
try:
    if not os.path.exists(MAIN_FOLDER_NAME): os.makedirs(MAIN_FOLDER_NAME)
    
    print(f"🔍 جاري تحليل الرابط وبناء الفهرس...")
    y_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", Playlist_URL]
    raw_data = subprocess.check_output(y_cmd, text=True).splitlines()
    all_videos = [json.loads(line) for line in raw_data]
    stats["total_found"] = len(all_videos)

    # الفرز
    if SORT_BY == "Most Viewed": all_videos.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
    elif SORT_BY == "Newest": all_videos.sort(key=lambda x: x.get('upload_date') or '', reverse=True)

    # تحديد النطاق
    start_num = 1
    if FILE_RANGE.strip() and "-" in FILE_RANGE:
        try:
            start_r, end_r = map(int, FILE_RANGE.split('-'))
            start_num = start_r
            target_list = all_videos[max(1, start_r)-1:end_r]
        except: target_list = all_videos
    else: target_list = all_videos

    total_to_process = len(target_list)

    for i, vid in enumerate(target_list):
        current_idx = start_num + i
        file_idx = f"{current_idx:03d}"
        
        elapsed_time = time.time() - stats["start"]
        print(f"🔄 [{file_idx}/{total_to_process}] معالجة: {vid.get('title')[:50]}...")

        v_url = f"https://www.youtube.com/watch?v={vid['id']}"
        output_tmpl = f"{MAIN_FOLDER_NAME}/{file_idx} - %(title)s ByAK.%(ext)s"

        dl_cmd = ["yt-dlp", "--quiet", "--no-warnings"]
        
        if UPLOAD_MODE == "Audio Only":
            if AUDIO_QUALITY == "VBR_Smart_22k":
                dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--postprocessor-args", "ffmpeg:-ac 1 -ar 22050 -q:a 9", "-o", output_tmpl, v_url])
            else:
                aq = AUDIO_QUALITY[:-1] if AUDIO_QUALITY != "Original/Best" else "0"
                dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", aq, "-o", output_tmpl, v_url])
        else:
            quality = VIDEO_QUALITY[:-1] if VIDEO_QUALITY != "Original/Best" else "1080"
            dl_cmd.extend(["-f", f"bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best", "-o", output_tmpl, v_url])

        subprocess.run(dl_cmd)

        # التحقق من الملف المجهز للرفع
        for file in os.listdir(MAIN_FOLDER_NAME):
            if file.startswith(file_idx) and not file.endswith(".part"):
                f_p = os.path.join(MAIN_FOLDER_NAME, file)
                ext = file.split('.')[-1]
                stats["size"] += os.path.getsize(f_p) / (1024**2)
                stats["v" if ext == "mp4" else "a"] += 1
                upload_queue.put((f_p, "Videos" if ext == "mp4" else "Audio"))
                break
        gc.collect()

    upload_queue.join()

    print(f"\n🏁 تم اكتمال المهمة بنجاح!")
    print(f"📦 الحجم الإجمالي: {stats['size']:.2f} MB")
    print(f"🎥 فيديوهات: {stats['v']} | 🎵 صوتيات: {stats['a']}")
    print(f"📂 المسار: {FINAL_DEST}")

except Exception as e:
    print(f"\n⚠️ توقف بسبب خطأ: {e}")
