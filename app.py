import os, subprocess, requests, threading, json, gc, time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- [ 1. إعدادات الأدوات والمحرك ] ---
# ملاحظة: سيتم استخدام هذه البيانات كافتراضية، ويمكنك تغييرها من Secrets كويب
WD_URL = os.environ.get("WD_URL", "https://obedientsupporters.co/remote.php/dav/files/Kabil1")
WD_USER = os.environ.get("WD_USER", "kabil1")
WD_PASS = os.environ.get("WD_PASS", "XE2tG-6tmFJ-S3gn5-x6YKB-WRaHb")

def setup_tools():
    print("🛠️ جاري إعداد الأدوات (ffmpeg & rclone)...")
    # تحميل rclone
    if not os.path.exists("rclone"):
        os.system("wget -q https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qj rclone-current-linux-amd64.zip '*/rclone' && chmod +x rclone")
    
    # تحميل ffmpeg النسخة الثابتة (لضمان الضغط الذكي)
    if not os.path.exists("ffmpeg"):
        os.system("wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && tar -xJf ffmpeg-release-amd64-static.tar.xz && mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe ./ && chmod +x ffmpeg ffprobe")
    
    # إنشاء إعدادات rclone للـ WebDAV
    try:
        pw_enc = subprocess.check_output(["./rclone", "obscure", WD_PASS]).decode().strip()
        config_text = f"[dst]\ntype = webdav\nurl = {WD_URL}\nuser = {WD_USER}\npass = {pw_enc}"
        with open("up.conf", "w") as f: f.write(config_text)
        print("✅ تم إعداد rclone بنجاح")
    except Exception as e:
        print(f"❌ خطأ في إعداد rclone: {e}")

# تنفيذ الإعداد عند بدء التشغيل
setup_tools()

# --- [ 2. منطق المعالجة الرئيسي (عقل الرادار) ] ---
def run_radar_logic(params):
    p_url = params.get("url")
    folder_name = params.get("folder", "test")
    quality_v = params.get("video_quality", "360p")
    quality_a = params.get("audio_quality", "VBR_Smart_22k")
    mode = params.get("mode", "Audio Only")
    f_range = params.get("range", "")
    sort_by = params.get("sort", "Default")

    print(f"📥 بدء معالجة الرابط: {p_url}")
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    
    try:
        # تحليل القائمة/الفيديو
        y_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", p_url]
        raw = subprocess.check_output(y_cmd, text=True).splitlines()
        all_vids = [json.loads(line) for line in raw]

        # ترتيب الملفات
        if sort_by == "Most Viewed": all_vids.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
        elif sort_by == "Newest": all_vids.sort(key=lambda x: x.get('upload_date') or '', reverse=True)

        # تحديد النطاق
        start_num = 1
        if f_range.strip() and "-" in f_range:
            try:
                s, e = map(int, f_range.split('-'))
                start_num = s
                target_list = all_vids[s-1:e]
            except: target_list = all_vids
        else: target_list = all_vids

        # التحميل والرفع حلقة بحلقة (Loop)
        for i, vid in enumerate(target_list):
            current_idx = f"{(start_num + i):03d}"
            v_url = f"https://www.youtube.com/watch?v={vid['id']}"
            output_tmpl = f"{folder_name}/{current_idx} - %(title)s ByAK.%(ext)s"
            
            # أمر yt-dlp مع تحديد مسار ffmpeg المحلي
            dl_cmd = ["yt-dlp", "--quiet", "--no-warnings", "--ffmpeg-location", "./ffmpeg"]
            
            if mode == "Audio Only":
                if quality_a == "VBR_Smart_22k":
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--postprocessor-args", "ffmpeg:-ac 1 -ar 22050 -q:a 9", "-o", output_tmpl, v_url])
                else:
                    aq = quality_a[:-1] if "k" in quality_a else "0"
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", aq, "-o", output_tmpl, v_url])
            else:
                res = quality_v[:-1] if "p" in quality_v else "360"
                dl_cmd.extend(["-f", f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best", "-o", output_tmpl, v_url])

            print(f"⏳ جاري معالجة الملف رقم {current_idx}...")
            subprocess.run(dl_cmd)

            # الرفع الفوري للملف المكتمل
            for file in os.listdir(folder_name):
                if file.startswith(current_idx) and not file.endswith(".part"):
                    f_p = os.path.join(folder_name, file)
                    sub_f = "Audio" if mode == "Audio Only" else "Videos"
                    dest = f"dst:MyFiles/خاص يوتيوب/{folder_name}/{sub_f}".replace("//", "/")
                    subprocess.run(["./rclone", "move", f_p, dest, "--config", "up.conf", "-q"])
                    print(f"✅ تم رفع {file} بنجاح")
                    break
            gc.collect()

    except Exception as e:
        print(f"⚠️ خطأ أثناء التنفيذ: {e}")

# --- [ 3. نقاط اتصال Flask ] ---

@app.route('/start', methods=['POST'])
def start_task():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No data received"}), 400
    
    # تشغيل الرادار في Thread منفصل لكي لا ينهار الاتصال
    threading.Thread(target=run_radar_logic, args=(data,)).start()
    return jsonify({"status": "running", "message": "Radar v6.2 is now processing in background"}), 200

@app.route('/')
def health():
    return "<h1>Radar Backend is Online</h1>", 200

if __name__ == '__main__':
    # قراءة البورت من النظام (للتوافق مع كويب)
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
