from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from moviepy.editor import VideoFileClip, concatenate_videoclips, TextClip, CompositeVideoClip
import openai
import tempfile
import os
import json

app = FastAPI()

openai.api_key = "DEIN_OPENAI_API_KEY"

@app.post("/edit-video/")
async def edit_video(file: UploadFile = File(...), instruction: str = Form(...)):
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, file.filename)
    output_path = os.path.join(temp_dir, "edited_" + file.filename)

    with open(input_path, "wb") as f:
        content = await file.read()
        f.write(content)

    lines = instruction.split("\n", 1)
    category = lines[0].replace("Kategorie: ", "").strip() if lines[0].startswith("Kategorie:") else "allgemein"
    user_prompt = lines[1] if len(lines) > 1 else ""

    gpt_response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Du bist ein professioneller Videoeditor. Nutze die Kategorie '{category}' und gib die Bearbeitungsanweisungen im JSON-Format zurück. Beispiel: {"trim": [0, 15], "text": [{"content": "Boom", "time": 5}]}"},
            {"role": "user", "content": user_prompt}
        ]
    )

    try:
        gpt_command = gpt_response.choices[0].message.content.strip()
        command_data = json.loads(gpt_command)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Ungültiges GPT-Format", "details": str(e)})

    try:
        clip = VideoFileClip(input_path)

        if "trim" in command_data:
            start, end = command_data["trim"]
            clip = clip.subclip(start, end)

        if "text" in command_data:
            texts = []
            for t in command_data["text"]:
                txt_clip = TextClip(t["content"], fontsize=40, color='white', bg_color='black', size=clip.size)
                txt_clip = txt_clip.set_start(t["time"]).set_duration(3)
                texts.append(txt_clip)
            clip = CompositeVideoClip([clip] + texts)

        clip.write_videofile(output_path, codec="libx264")
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    return FileResponse(output_path, filename="edited.mp4")