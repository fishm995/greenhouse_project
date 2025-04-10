# ffmpeg_controller.py
"""
This module controls the launching and termination of the FFmpeg process for streaming.
We define functions to start the FFmpeg process and to stop it, which can be called
from the Flask-SocketIO event handlers when the first viewer connects or the last viewer disconnects.
"""

import subprocess
import os
import signal

# Global variable to hold the FFmpeg process reference.
ffmpeg_process = None

def start_ffmpeg():
    """
    Starts the FFmpeg process if it is not already running.
    The command below uses libx264 for hardware-accelerated encoding.
    """
    global ffmpeg_process
    if ffmpeg_process is None:
        ffmpeg_command = [
            '/usr/bin/ffmpeg',
            '-f', 'v4l2',
            '-framerate', '30',
            '-input_format', 'mjpeg',
            '-video_size', '640x480',
            '-i', '/dev/video0',
            '-vcodec', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-r', '30',
            '-g', '30',
            '-sc_threshold', '0',
            '-x264-params', 'keyint=60:scenecut=0',
            '-an', 
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '10',
            '-hls_flags', 'delete_segments',
            '/tmp/hls/stream.m3u8'
        ]
        print("Starting FFmpeg process...")
        ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = ffmpeg_process.communicate(timeout=10)
        print("FFmpeg stdout:", out.decode())
        print("FFmpeg stderr:", err.decode())
        print(f"FFmpeg started with PID: {ffmpeg_process.pid}")

def stop_ffmpeg():
    
    
    Stops the FFmpeg process if it is running.
    Sends a SIGTERM to the process and resets the process reference.
    """
    global ffmpeg_process
    if ffmpeg_process is not None:
        print("Stopping FFmpeg process...")
        os.kill(ffmpeg_process.pid, signal.SIGTERM)
        ffmpeg_process = None
        print("FFmpeg process stopped.")
