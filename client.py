import requests
import tempfile
import os
from fastapi import FastAPI, Form, UploadFile, Response

app = FastAPI()


@app.post("/tts")
async def tts(file: UploadFile = Form(), transcript: str = Form(), text: str = Form()):
    with tempfile.TemporaryFile(mode="wb", dir="Data/voice/Temp/", delete=False) as t:
        f = await file.read()
        t.write(f)
        path = t.name

    try:
        params = {
            "text": text,
            "text_lang": "ja",
            "ref_audio_path": path,
            "prompt_text": transcript,
            "prompt_lang": "ja",
            "media_type": "wav",
            "streaming_mode": "false",
        }

        response = requests.get("http://127.0.0.1:9880/tts", params=params)

        if response.status_code == 200:
            return Response(content=response.content, media_type="audio/wav")

        else:
            return {"message": "An error has occurred."}
    finally:
        os.remove(path)
