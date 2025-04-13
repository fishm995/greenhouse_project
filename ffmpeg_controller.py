"""
ffmpeg_controller.py

This module manages the FFmpeg process that captures the camera feed and generates HLS segments.
It includes three main functions:
  1. kill_existing_ffmpeg(): Searches for and terminates any existing FFmpeg processes that match a specific command pattern.
  2. start_ffmpeg(): Kills any existing FFmpeg processes, then builds and starts a new FFmpeg process in the background.
  3. stop_ffmpeg(): Terminates the running FFmpeg process if it exists.

Note:
  - When running in the background (e.g., via nohup), any output from the print statements will be redirected to the log file specified,
    or to the default nohup.out if not redirected.
  - This module uses the 'pgrep' command to search for processes. Ensure that your environment includes this tool (most Linux systems do).

Usage:
  - Import and call start_ffmpeg() to launch the FFmpeg process.
  - Call stop_ffmpeg() when you need to stop the process.
"""

import subprocess
import os
import signal
import time
import threading

ffmpeg_state_lock = threading.Lock()
socketio = None
ffmpeg_ready_flag = False

# Global variable to store the FFmpeg process reference.
ffmpeg_process = None


def set_socketio(sio):
    """
    This function will be called by app.py to provide the SocketIO instance.
    """
    global socketio
    socketio = sio

def is_ffmpeg_ready():
    """
    Helper to read ffmpeg_ready_flag from app.py.
    """
    return ffmpeg_ready_flag

def kill_existing_ffmpeg():
    """
    Looks for any running FFmpeg processes that were started with a command pattern that identifies 
    our FFmpeg usage (e.g., capturing from /dev/video0) and kills them.

    This prevents duplicate FFmpeg processes from running simultaneously.
    """
    try:
        # 'pgrep -f' searches for processes where the command line contains a specific string.
        # Here, we look for a command that includes "ffmpeg -f v4l2", which should match the FFmpeg process.
        result = subprocess.run(["pgrep", "-f", "ffmpeg -f v4l2"], capture_output=True, text=True, check=False)
        if result.returncode == 0:
          
          pids = result.stdout.strip().splitlines()
          if pids:
              print(f"[ffmpeg_controller] Found existing FFmpeg processes: {pids}")
              for pid in pids:
                  try:
                      os.kill(int(pid), signal.SIGTERM)
                      print(f"[ffmpeg_controller] Killed FFmpeg process with PID {pid}")
                  except Exception as e:
                      print(f"[ffmpeg_controller] Error killing FFmpeg process {pid}: {e}")
        else:
            print("[ffmpeg_controller] No existing FFmpeg processes found.")
    except subprocess.CalledProcessError:
        # CalledProcessError occurs if pgrep finds no matching processes.
        print("[ffmpeg_controller] No existing FFmpeg processes found.")

def start_ffmpeg():
    """
    Starts the FFmpeg process for capturing video from /dev/video0, encoding it with libx264,
    and generating HLS segments in /tmp/hls/stream.m3u8.
    
    This function first calls kill_existing_ffmpeg() to ensure there are no duplicate
    FFmpeg processes running. It then constructs the FFmpeg command as a list of arguments,
    prints the command for debugging purposes, and finally starts the process in the background.
    
    The FFmpeg process output (via print statements) will go to standard output; if this script
    is run under nohup or with output redirection, the prints will appear in the specified log file.
    """
    global ffmpeg_process, ffmpeg_ready_flag

    with ffmpeg_state_lock:
      if ffmpeg_process is not None:
        print("[ffmpeg_controller] FFmpeg already running.")
        return
        
      # Build the FFmpeg command as a list. Adjust any parameters as needed.
      ffmpeg_command = [
          'nice', '-n', '5',
          'ffmpeg',
          '-f', 'v4l2',                      # Use the V4L2 input format for the camera.
          '-framerate', '30',                # Set frame rate to 30 fps.
          '-input_format', 'mjpeg',          # Expect the camera to provide MJPEG.
          '-video_size', '640x480',          # Set video resolution to 640x480.
          '-i', '/dev/video0',               # Input device.
          '-vcodec', 'libx264',              # Use libx264 for encoding.
          '-preset', 'veryfast',             # Use very fast settings for low latency.
          '-tune', 'zerolatency',            # Tune for zero latency.
          '-r', '30',                        # Output frame rate: 30 fps.
          '-g', '60',                        # GOP size (group of pictures): 60 frames.
          '-sc_threshold', '0',              # Disable scene cut detection.
          '-x264-params', 'keyint=60:scenecut=0',  # Force keyframes every 60 frames.
          '-an',                             # Disable audio.
          '-f', 'hls',                       # Output format is HLS.
          '-hls_time', '2',                  # Each HLS segment duration: 2 seconds.
          '-hls_list_size', '20',            # Keep a maximum of 20 segments in the playlist  
          '-hls_flags', 'delete_segments',   # Delete old segments automatically.
          '/tmp/hls/stream.m3u8'             # Output playlist location.
      ]
      
      print("[ffmpeg_controller] Starting FFmpeg process with command:")
      print(" ".join(ffmpeg_command))
  
      # Start FFmpeg as a background process.
      ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
      print(f"[ffmpeg_controller] FFmpeg process started with PID: {ffmpeg_process.pid}")
  
    timeout = 15
    start_time = time.time()
    while not os.path.exists("/tmp/hls/stream.m3u8"):
      if time.time() - start_time > timeout:
        print("[ffmpeg_controller] Timeout waiting for stream.m3u8")
        break
      time.sleep(0.5)

    with ffmpeg_state_lock:
      ffmpeg_ready_flag = True

    if socketio:
      socketio.emit('ffmpeg_ready', {'ready': True}, broadcast=True)
  
def stop_ffmpeg():
    """
    Stops the running FFmpeg process by sending SIGTERM, waits for it to exit
    (to prevent zombie processes), and resets the global reference to None.
    """
    global ffmpeg_process, ffmpeg_ready_flag

    with ffmpeg_state_lock:
      if ffmpeg_process is not None:
          print(f"[ffmpeg_controller] Stopping FFmpeg process with PID: {ffmpeg_process.pid}")
          try:
              # Send the termination signal (SIGTERM)
              os.kill(ffmpeg_process.pid, signal.SIGTERM)
              # Wait for the process to actually exit to ensure it’s reaped.
              # Specify a timeout to avoid blocking indefinitely.
              ffmpeg_process.wait(timeout=10)
              print("[ffmpeg_controller] FFmpeg process terminated successfully.")
          except subprocess.TimeoutExpired:
              print("[ffmpeg_controller] FFmpeg process did not terminate in time; consider force killing.")
              # Force kill if it does not exit:
              os.kill(ffmpeg_process.pid, signal.SIGKILL)
              ffmpeg_process.wait()
          except Exception as e:
              print(f"[ffmpeg_controller] Error stopping FFmpeg process: {e}")
          finally:
              ffmpeg_process = None
              ffmpeg_ready_flag = False
      else:
          print("[ffmpeg_controller] No FFmpeg process is currently running.")

if __name__ == '__main__':
    # This block is for testing purposes.
    # It will start FFmpeg, wait for the user to press Enter, and then stop FFmpeg.
    print("Testing FFmpeg controller functionality:")
    start_ffmpeg()
    print("FFmpeg should now be running. Press Enter to stop it.")
    input()  # Wait for user input before stopping FFmpeg.
    stop_ffmpeg()
