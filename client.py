import os
import datetime
import requests
from fastapi import FastAPI, Form, UploadFile, Response, HTTPException, Header, Depends
from prisma import Prisma
from prisma.models import User, Voice

app = FastAPI()


# セッショントークンからユーザーを取得
async def get_current_user(authorization: str = Header(None)) -> User | None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")

    prisma = Prisma()
    await prisma.connect()

    session = await prisma.session.find_unique(
        where={"token": token}, include={"user": True}
    )

    await prisma.disconnect()

    if not session or session.expiresAt < datetime.datetime.now(datetime.timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return session.user


async def get_voice(id: str) -> Voice:
    prisma = Prisma()
    await prisma.connect()
    voice = await prisma.voice.find_unique(
        where={"id": id}, include={"character": True}
    )
    await prisma.disconnect()

    if not voice:
        raise HTTPException(status_code=400, detail="Voice not found")

    return voice


async def insert_voice(character_id: str, user_id) -> Voice:
    prisma = Prisma()
    await prisma.connect()
    voice = await prisma.voice.create(
        data={"characterId": character_id, "userId": user_id}
    )
    await prisma.disconnect()

    return voice


async def delete_voice(id: str) -> None:
    prisma = Prisma()
    await prisma.connect()
    await prisma.voice.delete(where={"id": id})
    await prisma.disconnect()


# パストラバーサル防止
def sanitize_path(base_dir: str, filename: str) -> str:
    safe_path = os.path.normpath(os.path.join(base_dir, filename))
    if not os.path.abspath(safe_path).startswith(os.path.abspath(base_dir)):
        raise HTTPException(status_code=400, detail="Invalid path")
    return safe_path


@app.get("/tts")
async def tts(id: str, text: str, current_user: User = Depends(get_current_user)):
    voice = await get_voice(id)

    if not voice.character:
        raise HTTPException(status_code=400, detail="Voice Not found")

    if not voice.character.is_public and voice.character.postedBy != current_user.id:
        raise HTTPException(status_code=400, detail="Voice Not found")

    base_path = f"Data/voice/Temp/{voice.character.postedBy}"
    text_path = sanitize_path(base_path, f"{id}.txt")
    audio_path = sanitize_path(base_path, f"{id}.wav")

    try:
        with open(text_path, encoding="utf-8") as f:
            transcript = f.read()

        params = {
            "text": text,
            "text_lang": "ja",
            "ref_audio_path": audio_path,
            "prompt_text": transcript,
            "prompt_lang": "ja",
            "media_type": "wav",
            "streaming_mode": "false",
        }

        response = requests.get("http://127.0.0.1:9880/tts", params=params)

        if response.status_code == 200:
            return Response(content=response.content, media_type="audio/wav")
        else:
            raise HTTPException(status_code=500, detail="TTS engine error")

    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="TTS failed")


@app.post("/register")
async def register(
    id: str = Form(),
    file: UploadFile = Form(),
    transcript: str = Form(),
    current_user: User = Depends(get_current_user),
):
    assert file.filename

    if file.content_type != "audio/wav" or not file.filename.endswith(".wav"):
        raise HTTPException(status_code=400, detail="Only wav files are allowed")

    voice: Voice = await insert_voice(id, current_user.id)

    base_path = f"Data/voice/Temp/{current_user.id}"
    os.makedirs(base_path, exist_ok=True)

    audio_path = sanitize_path(base_path, f"{voice.id}.wav")
    text_path = sanitize_path(base_path, f"{voice.id}.txt")

    with open(audio_path, mode="wb") as f:
        bytes = await file.read()
        f.write(bytes)

    with open(text_path, mode="wt", encoding="utf-8") as f:
        f.write(transcript)

    return {"id": voice.id}


@app.post("/unregister")
async def unregister(id: str = Form(), current_user: User = Depends(get_current_user)):
    voice = await get_voice(id)

    if not voice.character:
        raise HTTPException(status_code=400, detail="Invalid voice ID")

    if voice.character.postedBy != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    base_path = f"Data/voice/Temp/{current_user.id}"
    audio_path = sanitize_path(base_path, f"{id}.wav")
    text_path = sanitize_path(base_path, f"{id}.txt")

    try:
        await delete_voice(id)

        if os.path.exists(audio_path):
            os.remove(audio_path)
        if os.path.exists(text_path):
            os.remove(text_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

    return {"id": voice.id}
