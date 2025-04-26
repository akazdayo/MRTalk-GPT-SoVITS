import datetime
import requests
from fastapi import FastAPI, Form, UploadFile, Response, HTTPException, Header, Depends
from prisma import Prisma
from prisma.models import Character, User


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


async def get_character(id: str) -> Character | None:
    prisma = Prisma()
    await prisma.connect()
    character = await prisma.character.find_unique(where={"id": id})

    if not character:
        raise HTTPException(status_code=400, detail="Character not found")

    await prisma.disconnect()
    return character


@app.get("/tts")
async def tts(id: str, text: str, current_user: User = Depends(get_current_user)):
    character: Character | None = await get_character(id)

    if not character:
        raise HTTPException(status_code=400, detail="Character not found")

    # キャラクターが非公開であればユーザーidを確認
    if not character.is_public and character.postedBy != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

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
