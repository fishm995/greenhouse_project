#!/usr/bin/env python3
"""
scheduler.py

This script starts the background scheduler that runs your automation tasks.
It is intended to run as a separate process alongside your Gunicorn-served Flask app.

It uses APScheduler to schedule the combined_task() function (which reads sensors and applies automation)
at a specified interval (e.g., every 30 seconds).

Signal handlers are registered so that the scheduler can shut down gracefully
when receiving a termination signal (SIGINT or SIGTERM).

Usage:
    Run this script separately, for example:
      python3 scheduler.py
"""

import time            # For sleep in the infinite loop
import signal          # For handling system signals (e.g., SIGINT, SIGTERM)
import sys             # For exiting the process gracefully
import atexit          # For handling exit and releasing GPIO
from apscheduler.schedulers.background import BackgroundScheduler  # Scheduler for background jobs
from main import combined_task  # Import the combined_task function from your main module

# Create an instance of BackgroundScheduler.
scheduler = BackgroundScheduler()

# Add a job to run combined_task() every 30 seconds.
scheduler.add_job(func=combined_task, trigger="interval", seconds=30)

def shutdown_handler(signum, frame):
    """
    Signal handler that is called when the process receives SIGINT or SIGTERM.
    
    Parameters:
      signum (int): The signal number received.
      frame: The current stack frame (not used here).
    """
    print(f"Received signal {signum}. Shutting down scheduler...")
    scheduler.shutdown()  # Shutdown the scheduler gracefully.
    sys.exit(0)         # Exit the process.

# Register signal handlers for SIGINT (e.g., Ctrl+C) and SIGTERM (termination signal).
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Start the scheduler.
scheduler.start()
print("Scheduler started. Press Ctrl+C to exit.")

# Cleanup all GPIO on exit
atexit.register(GPIO.cleanup)

# Block the main thread so the process doesn't exit.
# This loop keeps the script running indefinitely, checking for shutdown signals.
while True:
    time.sleep(1)
