import requests
from fastapi import FastAPI, Form, UploadFile, Response

app = FastAPI()


@app.get("/tts")
async def tts(id: str, text: str):
    with open(f"Data/voice/Temp/{id}.txt", encoding="utf-8") as f:
        transcript = f.read()

        try:
            params = {
                "text": text,
                "text_lang": "ja",
                "ref_audio_path": f"Data/voice/Temp/{id}.wav",
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
        except:
            return {"message": "An error has occurred."}


@app.post("/register")
async def register(
    id: str = Form(), file: UploadFile = Form(), transcript: str = Form()
):
    with open(f"Data/voice/Temp/{id}.wav", mode="wb") as f:
        bytes = await file.read()
        f.write(bytes)

    with open(f"Data/voice/Temp/{id}.txt", mode="wt", encoding="utf-8") as f:
        f.write(transcript)
