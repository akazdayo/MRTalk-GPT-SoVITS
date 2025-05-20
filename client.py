import os
import datetime
import requests
from fastapi import FastAPI, Form, UploadFile, Response, HTTPException, Header, Depends
from prisma import Prisma
from prisma.models import User, Voice

app = FastAPI()


# セッショントークンからユーザーを取得
async def get_current_user(authorization: str = Header(None)) -> User | None:
    print(f"[DEBUG] Enter get_current_user with authorization={authorization}")
    if not authorization:
        print("[DEBUG] No authorization header")
        raise HTTPException(status_code=401, detail="Unauthorized")

    token = authorization.replace("Bearer ", "")
    print(f"[DEBUG] Extracted token={token}")

    prisma = Prisma()
    print("[DEBUG] Initializing Prisma")
    await prisma.connect()
    print("[DEBUG] Connected to database")

    session = await prisma.session.find_unique(
        where={"token": token}, include={"user": True}
    )
    print(f"[DEBUG] Session fetched: {session}")

    await prisma.disconnect()
    print("[DEBUG] Disconnected from database")

    if not session or session.expiresAt < datetime.datetime.now(datetime.timezone.utc):
        print(f"[DEBUG] Invalid or expired token: {session}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    print(f"[DEBUG] Returning user: {session.user}")
    return session.user


async def get_voice(id: str) -> Voice:
    print(f"[DEBUG] Enter get_voice with id={id}")
    prisma = Prisma()
    print("[DEBUG] Initializing Prisma for get_voice")
    await prisma.connect()
    print("[DEBUG] Connected to database for get_voice")
    voice = await prisma.voice.find_unique(
        where={"id": id}, include={"character": True}
    )
    print(f"[DEBUG] Voice fetched: {voice}")
    await prisma.disconnect()
    print("[DEBUG] Disconnected from database for get_voice")

    if not voice:
        print("[DEBUG] Voice not found, raising HTTPException")
        raise HTTPException(status_code=400, detail="Voice not found")

    print(f"[DEBUG] Returning voice: {voice}")
    return voice


async def insert_voice(character_id: str, user_id) -> Voice:
    print(
        f"[DEBUG] Enter insert_voice with character_id={character_id}, user_id={user_id}"
    )
    prisma = Prisma()
    print("[DEBUG] Initializing Prisma for insert_voice")
    await prisma.connect()
    print("[DEBUG] Connected to database for insert_voice")
    voice = await prisma.voice.create(
        data={"characterId": character_id, "userId": user_id}
    )
    print(f"[DEBUG] Voice created: {voice}")
    await prisma.disconnect()
    print("[DEBUG] Disconnected from database for insert_voice")
    print(f"[DEBUG] Returning voice: {voice}")
    return voice


async def delete_voice(id: str) -> None:
    print(f"[DEBUG] Enter delete_voice with id={id}")
    prisma = Prisma()
    print("[DEBUG] Initializing Prisma for delete_voice")
    await prisma.connect()
    print("[DEBUG] Connected to database for delete_voice")
    await prisma.voice.delete(where={"id": id})
    print("[DEBUG] Voice deleted in database")
    await prisma.disconnect()
    print("[DEBUG] Disconnected from database for delete_voice")


# パストラバーサル防止
def sanitize_path(base_dir: str, filename: str) -> str:
    print(f"[DEBUG] Enter sanitize_path with base_dir={base_dir}, filename={filename}")
    safe_path = os.path.normpath(os.path.join(base_dir, filename))
    print(f"[DEBUG] Computed safe_path={safe_path}")
    if not os.path.abspath(safe_path).startswith(os.path.abspath(base_dir)):
        print("[DEBUG] Invalid path detected")
        raise HTTPException(status_code=400, detail="Invalid path")
    print(f"[DEBUG] Returning safe_path={safe_path}")
    return safe_path


@app.get("/tts")
async def tts(id: str, text: str, current_user: User = Depends(get_current_user)):
    print(f"[DEBUG] Enter tts with id={id}, text={text}, current_user={current_user}")
    voice = await get_voice(id)
    print(f"[DEBUG] Fetched voice: {voice}")

    if not voice.character:
        print("[DEBUG] No character in voice, raising HTTPException")
        raise HTTPException(status_code=400, detail="Voice Not found")

    if not voice.character.isPublic and voice.character.postedBy != current_user.id:
        print(
            f"[DEBUG] Unauthorized access: voice.character.postedBy={voice.character.postedBy}, current_user.id={current_user.id}"
        )
        raise HTTPException(status_code=400, detail="Voice Not found")

    base_path = f"Data/voice/Temp/{voice.character.postedBy}"
    text_path = (
        sanitize_path(base_dir := base_path, filename := f"{id}.txt")
        if False
        else sanitize_path(base_path, f"{id}.txt")
    )
    audio_path = sanitize_path(base_path, f"{id}.wav")
    print(
        f"[DEBUG] Paths set: base_path={base_path}, text_path={text_path}, audio_path={audio_path}"
    )

    try:
        print(f"[DEBUG] Opening text file at {text_path}")
        with open(text_path, encoding="utf-8") as f:
            transcript = f.read()
        print(f"[DEBUG] Transcript loaded: {transcript}")

        params = {
            "text": text,
            "text_lang": "ja",
            "ref_audio_path": audio_path,
            "prompt_text": transcript,
            "prompt_lang": "ja",
            "media_type": "wav",
            "streaming_mode": "false",
        }
        print(f"[DEBUG] Sending request to TTS engine with params={params}")

        response = requests.get("http://127.0.0.1:9880/tts", params=params)
        print(f"[DEBUG] Response status: {response.status_code}")
        print(f"[DEBUG] Response content: {response.content}")

        if response.status_code == 200:
            print("[DEBUG] TTS request successful")
            return Response(content=response.content, media_type="audio/wav")
        else:
            print(f"[DEBUG] TTS engine error: status_code={response.status_code}")
            raise HTTPException(status_code=500, detail="TTS engine error")

    except Exception as e:
        print(f"[DEBUG] Exception in tts: {e}")
        raise HTTPException(status_code=500, detail="TTS failed")


@app.post("/register")
async def register(
    id: str = Form(),
    file: UploadFile = Form(),
    transcript: str = Form(),
    current_user: User = Depends(get_current_user),
):
    print(
        f"[DEBUG] Enter register with id={id}, file.filename={file.filename}, transcript={transcript}, current_user={current_user}"
    )
    assert file.filename
    print("[DEBUG] Validating file type")
    if file.content_type != "audio/wav" or not file.filename.endswith(".wav"):
        print(f"[DEBUG] Invalid file type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Only wav files are allowed")

    print("[DEBUG] Inserting voice record")
    voice: Voice = await insert_voice(id, current_user.id)
    print(f"[DEBUG] Voice record created: {voice}")

    base_path = f"Data/voice/Temp/{current_user.id}"
    print(f"[DEBUG] Saving files to base_path {base_path}")
    os.makedirs(base_path, exist_ok=True)

    audio_path = (
        sanitize_path(base_dir := base_path, filename := f"{voice.id}.wav")
        if False
        else sanitize_path(base_path, f"{voice.id}.wav")
    )
    text_path = sanitize_path(base_path, f"{voice.id}.txt")

    with open(audio_path, mode="wb") as f:
        bytes = await file.read()
        f.write(bytes)
        print(f"[DEBUG] Audio file written: {audio_path}")

    with open(text_path, mode="wt", encoding="utf-8") as f:
        f.write(transcript)
        print(f"[DEBUG] Transcript file written: {text_path}")

    print(f"[DEBUG] Returning id: {voice.id}")
    return {"id": voice.id}


@app.post("/unregister")
async def unregister(id: str = Form(), current_user: User = Depends(get_current_user)):
    print(f"[DEBUG] Enter unregister with id={id}, current_user={current_user}")
    voice = await get_voice(id)
    print(f"[DEBUG] Fetched voice: {voice}")

    if not voice.character:
        print("[DEBUG] Invalid voice ID, raising HTTPException")
        raise HTTPException(status_code=400, detail="Invalid voice ID")

    if voice.character.postedBy != current_user.id:
        print(
            f"[DEBUG] Forbidden access: postedBy={voice.character.postedBy}, current_user.id={current_user.id}"
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    base_path = f"Data/voice/Temp/{current_user.id}"
    audio_path = sanitize_path(base_path, f"{id}.wav")
    text_path = sanitize_path(base_path, f"{id}.txt")
    print(
        f"[DEBUG] Paths set: base_path={base_path}, audio_path={audio_path}, text_path={text_path}"
    )

    try:
        print("[DEBUG] Deleting voice record")
        await delete_voice(id)
        print("[DEBUG] Voice record deleted")

        if os.path.exists(audio_path):
            os.remove(audio_path)
            print(f"[DEBUG] Removed audio file: {audio_path}")
        if os.path.exists(text_path):
            os.remove(text_path)
            print(f"[DEBUG] Removed transcript file: {text_path}")
    except Exception as e:
        print(f"[DEBUG] Exception in unregister: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete: {e}")

    print(f"[DEBUG] Returning id: {voice.id}")
    return {"id": voice.id}
