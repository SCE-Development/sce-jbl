import os
import subprocess
import uuid
from threading import Thread, Lock, Event
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan():
    try:
        connect_to_jbl()
    except Exception as e:
        logger.error(f'Failed to connect to JBL speaker: {e}')
        raise
    thread = Thread(target=send_songs_to_jbl, daemon=True)
    thread.start()
    yield
    jbl_event.set()
    thread.join()
    try:
        disconnect_jbl()
    except Exception as e:
        logger.error(f'Failed to disconnect from JBL speaker: {e}')

app = FastAPI(lifespan=lifespan)

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
    logger.info(f'Received play request for URL: {request.url}')
    download_video(request.url)
    return {'message': 'Song added to queue'}

@app.get('/skip')
def skip_song():
    pass

@app.get('/stop')
def stop():
    if song_queue:
        with queue_lock:
            song_queue.clear()
        logger.info('Stopped playback and cleared the queue')
        return {'message': 'Playback stopped and queue cleared'}


def download_video(url: str) -> None:
    '''Downloads a YouTube video as mp3 and adds it to the song queue.''' # at some point try to figure out how to do this without PyTube -> Spotify integration?
    video = YouTube(url)
    if video.age_restricted:
        raise HTTPException(status_code=400, detail='Age restricted video')
    
    os.makedirs(args.output_dir, exist_ok=True)
    stream = video.streams.filter(only_audio=True).first()
    mp4_path = stream.download(output_path=args.output_dir, filename=f'{uuid.uuid4()}.mp4')

    # convert to mp3
    mp3_path = mp4_path.replace('.mp4', '.mp3')
    subprocess.run(['ffmpeg', '-i', mp4_path, mp3_path])
    os.remove(mp4_path)
    with queue_lock:
        song_queue.append(mp3_path)
    logger.info(f'Downloaded and queued song: {mp3_path}')

def connect_to_jbl():
    '''Connect to the JBL using bluetooth command line tools'''

    # first connect to the JBL speaker
    subprocess.run(['bluetoothctl', 'connect', args.jbl_mac_address], check=True)

    # now trust the device
    subprocess.run(['bluetoothctl', 'trust', args.jbl_mac_address], check=True)

    # set the audio output to be the JBL speaker
    set_audio_output_to_jbl()

def set_audio_output_to_jbl():
    '''Set the system audio output to the JBL speaker'''
    status = subprocess.run(['wpctl', 'status'], capture_output=True, text=True).stdout
    sink_ids = [
        line.split()[0].strip()
        for line in status.splitlines()
        if 'Audio/Sink' in line
    ]

    for sink_id in sink_ids:
        info = subprocess.run(['wpctl', 'info', sink_id], capture_output=True, text=True).stdout
        if args.jbl_mac_address.replace(':', '_') in info:
            subprocess.run(['wpctl', 'set-default', sink_id], check=True)
            logger.info(f'Set audio output to JBL speaker with sink ID: {sink_id}')
            return
    
    logger.info('JBL speaker not found among audio sinks')

def disconnect_jbl():
    '''Disconnect from the JBL speaker'''
    subprocess.run(['bluetoothctl', 'disconnect', args.jbl_mac_address], check=True)
    subprocess.run(['wpctl', 'set-default', '@DEFAULT_AUDIO_SINK@'], check=True)
    logger.info('Disconnected from JBL speaker')

def send_songs_to_jbl():
    '''Threaded function to send songs from the queue to the JBL speaker'''
    while not jbl_event.is_set():
        if song_queue:
            with queue_lock:
                song_path = song_queue.pop(0)
            logger.info(f'Sending song to JBL: {song_path}')
            # send song to JBL speaker using Linux command line

if __name__ == '__main__':
    uvicorn.run('server:app', host=args.host, port=args.port, reload=True)
