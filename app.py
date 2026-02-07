import os, subprocess, requests, threading, json, gc, time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- [ إعدادات WebDAV ] ---
WD_URL = os.environ.get("WD_URL", "https://obedientsupporters.co/remote.php/dav/files/Kabil1")
WD_USER = os.environ.get("WD_USER", "kabil1")
WD_PASS = os.environ.get("WD_PASS", "XE2tG-6tmFJ-S3gn5-x6YKB-WRaHb")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- [ إعداد الأدوات ] ---
def setup_tools():
    try:
        if not os.path.exists("rclone"):
            os.system("wget -q https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qj rclone-current-linux-amd64.zip '*/rclone' && chmod +x rclone")
        if not os.path.exists("ffmpeg"):
            os.system("wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && tar -xJf ffmpeg-release-amd64-static.tar.xz && mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe ./ && chmod +x ffmpeg ffprobe")
        
        pw_enc = subprocess.check_output(["./rclone", "obscure", WD_PASS]).decode().strip()
        config_text = f"[dst]\ntype = webdav\nurl = {WD_URL}\nuser = {WD_USER}\npass = {pw_enc}"
        with open("up.conf", "w") as f: f.write(config_text)
        print("✅ Tools Ready.")
    except Exception as e: print(f"❌ Setup Error: {e}")

# --- [ عقل الرادار المطور ] ---
def run_radar_logic(params):
    p_url = params.get("url")
    folder_name = params.get("folder", "test")
    mode = params.get("mode", "Audio Only")
    f_range = params.get("range", "")
    cookies_content = params.get("cookies", "") # استقبال الكوكيز

    if not p_url: return
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    
    ffmpeg_local = os.path.join(BASE_DIR, "ffmpeg")
    cookies_path = os.path.join(BASE_DIR, "temp_cookies.txt")

    # التعامل مع ملف الكوكيز
    if cookies_content.strip():
        with open(cookies_path, "w", encoding="utf-8") as f:
            f.write(cookies_content.strip())

    try:
        # أمر الفحص
        y_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", p_url]
        if os.path.exists(cookies_path): y_cmd.extend(["--cookies", cookies_path])
        
        raw = subprocess.check_output(y_cmd, text=True).splitlines()
        all_vids = [json.loads(line) for line in raw]

        start_num = 1
        if f_range and "-" in str(f_range):
            s, e = map(int, str(f_range).split('-'))
            start_num = s
            target_list = all_vids[s-1:e]
        else: target_list = all_vids

        for i, vid in enumerate(target_list):
            current_idx = f"{(start_num + i):03d}"
            v_url = f"https://www.youtube.com/watch?v={vid['id']}"
            output_tmpl = f"{folder_name}/{current_idx} - %(title)s.%(ext)s"
            
            dl_cmd = ["yt-dlp", "--quiet", "--no-warnings", "--ffmpeg-location", ffmpeg_local, "-o", output_tmpl]
            if os.path.exists(cookies_path): dl_cmd.extend(["--cookies", cookies_path])

            if mode == "Audio Only":
                dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--postprocessor-args", "ffmpeg:-ac 1 -ar 22050 -q:a 9"])
            else:
                dl_cmd.extend(["-f", "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best"])

            dl_cmd.append(v_url)
            print(f"🎬 Processing: {current_idx}")
            subprocess.run(dl_cmd)

            # الرفع
            for file in os.listdir(folder_name):
                if file.startswith(current_idx) and not file.endswith(".part"):
                    f_p = os.path.join(folder_name, file)
                    dest = f"dst:MyFiles/خاص يوتيوب/{folder_name}/{'Audio' if mode == 'Audio Only' else 'Videos'}"
                    subprocess.run(["./rclone", "move", f_p, dest, "--config", "up.conf", "-q"])
                    break
            gc.collect()

        # تنظيف الكوكيز بعد الانتهاء للخصوصية
        if os.path.exists(cookies_path): os.remove(cookies_path)
        print(f"✅ Mission Completed: {folder_name}")

    except Exception as e: print(f"❌ Logic Error: {e}")

@app.route('/start', methods=['GET', 'POST'])
def start_task():
    data = request.args.to_dict() if request.method == 'GET' else (request.json or request.form.to_dict())
    if not data.get('url'): return jsonify({"status": "error"}), 400
    threading.Thread(target=run_radar_logic, args=(data,)).start()
    return jsonify({"status": "running", "message": "Radar v6.2 with Cookie Support started"}), 200

@app.route('/')
def health(): return "Radar Backend Online", 200

if __name__ == '__main__':
    threading.Thread(target=setup_tools, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
