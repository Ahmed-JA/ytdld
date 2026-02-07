import os, subprocess, requests, threading, json, gc, time
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- [ إعدادات WebDAV الثابتة ] ---
WD_URL = os.environ.get("WD_URL", "https://obedientsupporters.co/remote.php/dav/files/Kabil1")
WD_USER = os.environ.get("WD_USER", "kabil1")
WD_PASS = os.environ.get("WD_PASS", "XE2tG-6tmFJ-S3gn5-x6YKB-WRaHb")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def setup_tools():
    if not os.path.exists("rclone"):
        os.system("wget -q https://downloads.rclone.org/rclone-current-linux-amd64.zip && unzip -qj rclone-current-linux-amd64.zip '*/rclone' && chmod +x rclone")
    if not os.path.exists("ffmpeg"):
        os.system("wget -q https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz && tar -xJf ffmpeg-release-amd64-static.tar.xz && mv ffmpeg-*-amd64-static/ffmpeg ffmpeg-*-amd64-static/ffprobe ./ && chmod +x ffmpeg ffprobe")
    
    # إعداد rclone للـ WebDAV فقط
    pw_enc = subprocess.check_output(["./rclone", "obscure", WD_PASS]).decode().strip()
    config_text = f"[dst]\ntype = webdav\nurl = {WD_URL}\nuser = {WD_USER}\npass = {pw_enc}"
    with open("up.conf", "w") as f: f.write(config_text)

def run_radar_logic(params):
    p_url = params.get("url")
    folder_name = params.get("folder", "test")
    mode = params.get("mode", "Audio Only")
    f_range = params.get("range", "")
    sort_by = params.get("sort", "Default")
    v_qual = params.get("video_quality", "360p")
    a_qual = params.get("audio_quality", "VBR_Smart_22k")
    remote_dest = params.get("remote_dest", "خاص يوتيوب")
    cookies_content = params.get("cookies", "")

    if not p_url: return
    if not os.path.exists(folder_name): os.makedirs(folder_name)
    
    cookies_path = os.path.join(BASE_DIR, "temp_cookies.txt")
    if cookies_content.strip():
        with open(cookies_path, "w", encoding="utf-8") as f: f.write(cookies_content.strip())

    try:
        # 1. تحليل الرابط وتطبيق الترتيب
        y_cmd = ["yt-dlp", "--dump-json", "--flat-playlist", p_url]
        if os.path.exists(cookies_path): y_cmd.extend(["--cookies", cookies_path])
        
        raw = subprocess.check_output(y_cmd, text=True).splitlines()
        all_vids = [json.loads(line) for line in raw]

        if sort_by == "Most Viewed": all_vids.sort(key=lambda x: x.get('view_count') or 0, reverse=True)
        elif sort_by == "Newest": all_vids.sort(key=lambda x: x.get('upload_date') or '', reverse=True)
        elif sort_by == "Oldest": all_vids.sort(key=lambda x: x.get('upload_date') or '')

        # 2. تحديد نطاق الملفات
        start_num = 1
        if f_range and "-" in str(f_range):
            s, e = map(int, str(f_range).split('-'))
            start_num = s
            target_list = all_vids[s-1:e]
        else: target_list = all_vids

        # 3. دورة التحميل والرفع
        for i, vid in enumerate(target_list):
            current_idx = f"{(start_num + i):03d}"
            v_url = f"https://www.youtube.com/watch?v={vid['id']}"
            output_tmpl = f"{folder_name}/{current_idx} - %(title)s.%(ext)s"
            
            dl_cmd = ["yt-dlp", "--quiet", "--no-warnings", "--ffmpeg-location", "./ffmpeg", "-o", output_tmpl]
            if os.path.exists(cookies_path): dl_cmd.extend(["--cookies", cookies_path])

            if mode == "Audio Only":
                if a_qual == "VBR_Smart_22k":
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--postprocessor-args", "ffmpeg:-ac 1 -ar 22050 -q:a 9"])
                else:
                    aq = a_qual.replace("k", "") if a_qual != "Original/Best" else "0"
                    dl_cmd.extend(["--extract-audio", "--audio-format", "mp3", "--audio-quality", aq])
            else:
                res = v_qual.replace("p", "") if v_qual != "Original/Best" else "1080"
                dl_cmd.extend(["-f", f"bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best"])

            dl_cmd.append(v_url)
            print(f"🎬 Processing: {current_idx}")
            subprocess.run(dl_cmd)

            # الرفع الفوري عبر WebDAV
            sub_folder = "Audio" if mode == "Audio Only" else "Videos"
            final_cloud_path = f"dst:MyFiles/{remote_dest}/{folder_name}/{sub_folder}".replace("//", "/")
            
            for file in os.listdir(folder_name):
                if file.startswith(current_idx) and not file.endswith(".part"):
                    subprocess.run(["./rclone", "move", os.path.join(folder_name, file), final_cloud_path, "--config", "up.conf", "-q"])
                    break
            gc.collect()

        if os.path.exists(cookies_path): os.remove(cookies_path)
        print(f"✅ Mission Finished for: {folder_name}")

    except Exception as e: print(f"❌ Error: {e}")

@app.route('/start')
def start():
    data = request.args.to_dict()
    threading.Thread(target=run_radar_logic, args=(data,)).start()
    return jsonify({"status": "running"}), 200

@app.route('/')
def health(): return "Radar WebDAV Engine Online", 200

if __name__ == '__main__':
    setup_tools()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
