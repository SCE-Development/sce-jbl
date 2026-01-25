import os
import subprocess
import uuid
from threading import Thread, Lock, Event

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pytubefix import YouTube

from modules.args import get_args
from modules.logger import logger


song_queue = []
queue_lock = Lock()
jbl_event = Event()


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
    with queue_lock:
        song_queue.append(mp3_path)
    return mp3_path

def send_songs_to_jbl():
    while not jbl_event.is_set():
        if song_queue:
            with queue_lock:
                song_path = song_queue.pop(0)
        logger.info(f"Sending song to JBL: {song_path}")
        # send song to JBL speaker using Linux command line


@app.on_event('startup')
def start_jbl_thread():
    Thread(target=send_songs_to_jbl, daemon=True).start()

@app.on_event('shutdown')
def stop_jbl_thread():
    jbl_event.set()

if __name__ == '__main__':
    uvicorn.run('server:app', host=args.host, port=args.port, reload=True)
