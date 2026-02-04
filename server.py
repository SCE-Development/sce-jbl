import subprocess
import threading
from contextlib import asynccontextmanager
from collections import deque
import time

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from mpv import MPV
import prometheus_client

from modules.args import get_args
from modules.logger import logger
from modules.metrics import MetricsHandler


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
async def lifespan(_: FastAPI):
    try:
        connect_to_jbl()
        MetricsHandler.jbl_last_connected.set(time.time())
        MetricsHandler.bluetooth_error.set(0)
    except Exception as e:
        logger.error(f'Failed to connect to JBL speaker: {e}')
        MetricsHandler.bluetooth_error.set(1)
        raise
    yield
    try:
        disconnect_jbl()
        MetricsHandler.bluetooth_error.set(0)
    except Exception as e:
        logger.error(f'Failed to disconnect from JBL speaker: {e}')
        MetricsHandler.bluetooth_error.set(1)


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

metrics_handler = MetricsHandler.instance()

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


@app.get('/metrics')
def get_metrics():
    return Response(
        media_type='text/plain',
        content=prometheus_client.generate_latest()
    )


@app.middleware('http')
async def track_response_codes(request: Request, call_next):
    response = await call_next(request)
    MetricsHandler.endpoint_hits.labels(request.url.path, response.status_code).inc()
    return response


@player.event_callback('end-file')
def on_end(event):
    try:
        event_str = str(event)
    
        if 'reason' in event_str:
            start = event_str.find("'reason': b'") + len("'reason': b'")
            end = event_str.find("'", start)
            reason = event_str[start:end]
            if reason == 'eof':
                play_next_song()

    except Exception as e:
        logger.error(f'Failed to handle event: {e}')


def connect_to_jbl():
    # first connect to the JBL speaker
    subprocess.run(['bluetoothctl', 'connect', args.jbl_mac_address], check=True)

    # now trust the device
    subprocess.run(['bluetoothctl', 'trust', args.jbl_mac_address], check=True)


def disconnect_jbl():
    subprocess.run(['bluetoothctl', 'disconnect', args.jbl_mac_address], check=True)
    logger.info('Disconnected from JBL speaker')


def play_next_song():
    with queue_lock:
        if song_queue:
            next_song = song_queue.popleft()
            logger.info(f'Playing next song from queue: {next_song}')
            player.play(next_song)


if __name__ == '__main__':
    uvicorn.run('server:app', host=args.host, port=args.port, reload=True)
