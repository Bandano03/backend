from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.editor import concatenate_videoclips, AudioFileClip, TextClip, CompositeVideoClip
import openai
import tempfile
import os
import json
from typing import List

app = FastAPI()

openai.api_key = os.getenv("OPENAI_API_KEY", "")

@app.post("/edit-video/")
async def edit_video(
    files: List[UploadFile] = File(...),
    instruction: str = Form(...)
):
    temp_dir = tempfile.mkdtemp()
    video_paths = []
    output_path = os.path.join(temp_dir, "final_edit.mp4")

    # Speichere alle hochgeladenen Videos
    for file in files:
        video_path = os.path.join(temp_dir, file.filename)
        with open(video_path, "wb") as f:
            f.write(await file.read())
        video_paths.append(video_path)

    # Kategorie & Prompt trennen
    lines = instruction.split("\n", 1)
    category = lines[0].replace("Kategorie: ", "").strip().lower() if lines[0].startswith("Kategorie:") else "edit"
    user_prompt = lines[1] if len(lines) > 1 else ""

    # Dynamischer Systemprompt für GPT basierend auf Kategorie
    if category in ["werbung", "produkt", "business"]:
        system_prompt = f"""
        Du bist ein professioneller Werbevideo-Editor. Die Videos zeigen Produkte oder Dienstleistungen.
        Deine Aufgabe ist es, daraus ein überzeugendes Social-Media-Werbevideo zu machen.
        Nutze dafür ansprechende Szenen, füge passende Übergänge und Musik hinzu.
        Ergänze kurze Werbetexte wie 'Jetzt erhältlich', 'Nur für kurze Zeit', 'Sichere dir dein Angebot'.
        Gib deine Bearbeitung im JSON-Format zurück: 
        {{
            "edit": true,
            "trim": [[start, end], ...],
            "text": [{{"content": "Jetzt erhältlich", "time": 2}}],
            "music": "standard.mp3"
        }}
        """
    else:
        system_prompt = f"Du bist ein kreativer TikTok-Videoeditor. Die Kategorie ist '{category}'. Nutze alle Videos kreativ, füge Musik und Text hinzu. Gib JSON zurück im Format: {{'edit': true, 'trim': [[start, end], ...], 'text': [...], 'music': 'standard.mp3'}}"

    try:
        # GPT fragen
        gpt_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        gpt_output = gpt_response.choices[0].message.content.strip()
        try:
            command_data = json.loads(gpt_output)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": "GPT JSON ungültig", "gpt_output": gpt_output, "details": str(e)})

        # Clips laden & ggf. trimmen
        clips = []
        for i, path in enumerate(video_paths):
            clip = VideoFileClip(path)
            if "trim" in command_data and i < len(command_data["trim"]):
                start, end = command_data["trim"][i]
                clip = clip.subclip(start, end)
            clips.append(clip)

        # Clips zusammenfügen
        final = concatenate_videoclips(clips, method="compose")

        # Text einfügen
        if "text" in command_data:
            text_layers = []
            for t in command_data["text"]:
                txt = TextClip(t["content"], fontsize=50, color="white", bg_color="black", size=final.size)
                txt = txt.set_start(t["time"]).set_duration(t.get("duration", 3))
                text_layers.append(txt)
            final = CompositeVideoClip([final] + text_layers)

        # Musik einfügen
        if "music" in command_data:
            music_path = os.path.join("assets", command_data["music"])
            if os.path.exists(music_path):
                audio = AudioFileClip(music_path).subclip(0, final.duration)
                final = final.set_audio(audio)

        # Exportieren
        final.write_videofile(output_path, codec="libx264", audio_codec="aac")
        return FileResponse(output_path, filename="edit_final.mp4")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": "Bearbeitung fehlgeschlagen", "details": str(e)})
