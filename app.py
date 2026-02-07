import os, subprocess, requests, threading, json, gc, time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- [ إعدادات WebDAV ] ---
WD_URL = os.environ.get("WD_URL", "https://obedientsupporters.co/remote.php/dav/files/Kabil1")
WD_USER = os.environ.get("WD_USER", "kabil1")
WD_PASS = os.environ.get("WD_PASS", "XE2tG-6tmFJ-S3gn5-x6YKB-WRaHb")

# --- [ وظيفة إعداد الأدوات في الخلفية ] ---
def setup_tools():
    print("🛠️ بدء تجهيز الأدوات في الخلفية...")
    try:
        # تحميل rclone إذا لم يكن موجوداً
        if not os.path.exists("rclone"):
            os.system("wget -q https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qj rclone-current-linux-amd64.zip '*/rclone' && chmod +x rclone")
        
        # تحميل ffmpeg النسخة الثابتة
        if not os.path.exists("ffmpeg"):
            os.system("wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && tar -xJf ffmpeg-release-amd64-static.tar.xz && mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe ./ && chmod +x ffmpeg ffprobe")
        
        # إعداد ملف rclone config
        pw_enc = subprocess.check_output(["./rclone", "obscure", WD_PASS]).decode().strip()
        config_text = f"[dst]\ntype = webdav\nurl = {WD_URL}\nuser = {WD_USER}\npass = {pw_enc}"
        with open("up.conf", "w") as f: f.write(config_text)
        print("✅ الأدوات جاهزة والرفع متصل بالسيرفر.")
    except Exception as e:
        print(f"❌ فشل إعداد الأدوات: {e}")

# --- [ عقل الرادار v6.2 ] ---
def run_radar_logic(params):
    p_url = params.get("url")
    folder_name = params.get("folder", "test")
    quality_v = params.get("video_quality", "360p")
    quality_a = params.get("audio_quality", "VBR_Smart_22k")
    mode = params.get("mode", "Audio Only")
    f_range = params.get("range", "")
    sort_by = params.get("sort", "Default")

    if not p_url: return
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    
    try:
        print(f"🔎 فحص الرابط: {p_url}")
        y_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", p_url]
        raw = subprocess.check_output(y_cmd, text=True).splitlines()
        all_vids = [json.loads(line) for line in raw]

        if sort_by == "Most Viewed": 
            all_vids.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
        
        start_num = 1
        if f_range and "-" in str(f_range):
            s, e = map(int, str(f_range).split('-'))
            start_num = s
            target_list = all_vids[s-1:e]
        else: target_list = all_vids

        for i, vid in enumerate(target_list):
            current_idx = f"{(start_num + i):03d}"
            v_url = f"https://www.youtube.com/watch?v={vid['id']}"
            output_tmpl = f"{folder_name}/{current_idx} - %(title)s ByAK.%(ext)s"
            
            # إعداد أمر التحميل
            dl_cmd = ["yt-dlp", "--quiet", "--no-warnings", "--ffmpeg-location", "./ffmpeg"]
            
            if mode == "Audio Only":
                if quality_a == "VBR_Smart_22k":
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--postprocessor-args", "ffmpeg:-ac 1 -ar 22050 -q:a 9", "-o", output_tmpl, v_url])
                else:
                    aq = str(quality_a).replace("k", "")
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", aq, "-o", output_tmpl, v_url])
            else:
                res = str(quality_v).replace("p", "")
                dl_cmd.extend(["-f", f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best", "-o", output_tmpl, v_url])

            print(f"🎬 جاري معالجة: {current_idx}")
            subprocess.run(dl_cmd)

            # الرفع الفوري
            for file in os.listdir(folder_name):
                if file.startswith(current_idx) and not file.endswith(".part"):
                    f_p = os.path.join(folder_name, file)
                    sub_f = "Audio" if mode == "Audio Only" else "Videos"
                    # المسار المطلوب في WebDAV
                    dest = f"dst:MyFiles/خاص يوتيوب/{folder_name}/{sub_f}"
                    subprocess.run(["./rclone", "move", f_p, dest, "--config", "up.conf", "-q"])
                    break
            gc.collect()
        print(f"✅ انتهت المهمة للمجلد: {folder_name}")
    except Exception as e:
        print(f"❌ خطأ في المعالجة: {e}")

# --- [ نقاط اتصال Flask المحدثة ] ---

@app.route('/start', methods=['GET', 'POST'])
def start_task():
    # دعم استقبال البيانات من POST (JSON) أو GET (URL Parameters)
    if request.method == 'POST':
        data = request.json if request.is_json else request.form.to_dict()
    else:
        data = request.args.to_dict()

    if not data or 'url' not in data:
        return jsonify({"status": "error", "message": "Missing URL parameter"}), 400
    
    # تشغيل الرادار في الخلفية
    threading.Thread(target=run_radar_logic, args=(data,)).start()
    
    return jsonify({
        "status": "running", 
        "message": "Radar v6.2 started in background",
        "received_params": data
    }), 200

@app.route('/')
def health():
    return "<h1>Radar Backend is Online</h1>", 200

if __name__ == '__main__':
    # تشغيل التجهيز في الخلفية
    threading.Thread(target=setup_tools, daemon=True).start()
    
    # التشغيل على بورت كويب
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
