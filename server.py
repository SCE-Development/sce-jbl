import subprocess
import threading
from contextlib import asynccontextmanager
from collections import deque

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mpv import MPV

from modules.args import get_args
from modules.logger import logger


song_queue = deque()
queue_lock = threading.Lock()
player = MPV(
        ytdl=True,
        input_default_bindings=False,
        input_vo_keyboard=False,
        # wid=None,
        vo='null',
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        connect_to_jbl()
    except Exception as e:
        logger.error(f'Failed to connect to JBL speaker: {e}')
        raise
    yield
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

class QueueRequest(BaseModel):
    url: str
    play_immediately: bool = False


@app.get('/')
def root():
    return {'message': 'sce jbl is running'}


@app.post('/queue')
def enqueue_song(request: QueueRequest):
    if not request or not request.url:
        raise HTTPException(status_code=400, detail='Invalid request payload')
    logger.info(f'Received play request for URL: {request.url}')
    if request.play_immediately:
        with queue_lock:
            song_queue.appendleft(request.url)
        play_next_song()
        return {'message': 'Playing song immediately'}
    with queue_lock:
        song_queue.append(request.url)
    if player.idle_active:
        play_next_song()
    return {'message': 'Song added to queue'}


@app.get('/skip')
def skip_song():
    play_next_song()
    return {'message': 'Skipped to next song'}


@app.get('/stop')
def stop():
    if song_queue:
        with queue_lock:
            song_queue.clear()
        player.stop()
        logger.info('Stopped playback and cleared the queue')
        return {'message': 'Playback stopped and queue cleared'}
    return {'message': 'No playback to stop'}


@player.event_callback('end-file')
def on_end(event):
    try:
        event_str = str(event)
    
        if "reason" in event_str:
            start = event_str.find("'reason': b'") + len("'reason': b'")
            end = event_str.find("'", start)
            reason = event_str[start:end]
            if reason == 'eof':
                play_next_song()
                
    except Exception as e:
        logger.error(f"Failed to handle event: {e}")


def connect_to_jbl():
    # first connect to the JBL speaker
    subprocess.run(['bluetoothctl', 'connect', args.jbl_mac_address], check=True)

    # now trust the device
    subprocess.run(['bluetoothctl', 'trust', args.jbl_mac_address], check=True)

    # set the audio output to be the JBL speaker
    set_audio_output_to_jbl()


def set_audio_output_to_jbl():
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
    subprocess.run(['bluetoothctl', 'disconnect', args.jbl_mac_address], check=True)
    subprocess.run(['wpctl', 'set-default', '@DEFAULT_AUDIO_SINK@'], check=True)
    logger.info('Disconnected from JBL speaker')


def play_next_song():
    with queue_lock:
        if song_queue:
            next_song = song_queue.popleft()
            logger.info(f'Playing next song from queue: {next_song}')
            player.play(next_song)


if __name__ == '__main__':
    uvicorn.run('server:app', host=args.host, port=args.port, reload=True)
