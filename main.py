import os
import subprocess
import uuid
from threading import Thread, Lock

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pytubefix import YouTube

from modules.args import get_args
from modules.logger import logger


SONG_QUEUE = []
QUEUE_LOCK = Lock()


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

args = get_args()

class PlayRequest(BaseModel):
    url: str


@app.get('/')
def root():
    return {'message': 'sce jbl is running'}


@app.post('/play')
def play_song(request: PlayRequest):
    logger.info(f"Received play request for URL: {request.url}")
    download_video(request.url)
    return {'message': 'Song added to queue'}


@app.post('/skip')
def skip_song():
    pass


@app.post('/stop')
def stop_song():
    pass


def download_video(url: str):
    video = YouTube(url)
    if video.age_restricted:
        raise HTTPException(status_code=400, detail='Age restricted video')
    
    os.makedirs('videos', exist_ok=True)
    stream = video.streams.filter(only_audio=True).first()
    mp4_path = stream.download(output_path='videos', filename=f'{uuid.uuid4()}.mp4')

    # convert to mp3
    mp3_path = mp4_path.replace('.mp4', '.mp3')
    subprocess.run(['ffmpeg', '-i', mp4_path, mp3_path])
    os.remove(mp4_path)
    SONG_QUEUE.append(mp3_path)
    return mp3_path


if __name__ == '__main__':
    uvicorn.run('main:app', host=args.host, port=args.port, reload=True)
