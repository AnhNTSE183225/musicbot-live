import multiprocessing
import threading
import numpy as np
import time
import psutil
from typing import Optional
from proctap import ProcessAudioCapture
from audio.interfaces import IAudioCapture

def get_process_id_by_identifier(identifier: str) -> Optional[int]:
    """Finds the PID of the ROOT process given its name or exact exe path."""
    candidates = []
    
    # First, gather all processes matching the identifier
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'ppid']):
        try:
            match = False
            if proc.info['exe'] and proc.info['exe'].lower() == identifier.lower():
                match = True
            elif proc.info['name'] and proc.info['name'].lower() == identifier.lower():
                match = True
                
            if match:
                candidates.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not candidates:
        return None

    # Find the root process (whose parent is NOT in the candidate list)
    candidate_pids = {p.info['pid'] for p in candidates}
    for p in candidates:
        if p.info['ppid'] not in candidate_pids:
            return p.info['pid']
            
    # Fallback to the first one if we can't find a clear root
    return candidates[0].info['pid']

def capture_process_worker(pid: int, queue: multiprocessing.Queue, stop_event: multiprocessing.Event):
    """
    Background worker process to capture audio (Multiprocessing & Task Parallelism).
    Converts float32 audio to int16 using numpy (Vectorization & SIMD & Data Parallelism).
    """
    # AGC (Automatic Gain Control) Settings
    target_peak = 0.9  # Target amplitude (90% of max)
    current_gain = 1.0
    attack = 0.8       # How fast gain drops when too loud (fast to prevent clipping)
    release = 0.1      # How fast gain rises when too quiet (fast recovery)
    max_gain = 100.0   # Allow up to 100x amplification (so 1% volume sounds like 100%)

    with ProcessAudioCapture(pid=pid, resample_quality='best') as tap:
        tap.start()
        
        while not stop_event.is_set():
            # Synchronous blocking read (Non-blocking I/O achieved by isolating to this process)
            chunk = tap.read(timeout=0.1)
            if chunk:
                # Chunk is bytes of float32, 48000Hz, Stereo.
                # Convert to numpy array
                audio_float = np.frombuffer(chunk, dtype=np.float32)
                
                # Vectorized AGC / Normalization
                peak = np.max(np.abs(audio_float))
                
                if peak > 0.0001:  # Only adjust gain if there is actual audio
                    desired_gain = target_peak / peak
                    
                    # Smoothly adjust gain
                    if desired_gain < current_gain:
                        current_gain += attack * (desired_gain - current_gain)
                    else:
                        current_gain += release * (desired_gain - current_gain)
                        
                    # Clamp gain to prevent extreme amplification of background noise
                    current_gain = np.clip(current_gain, 1.0, max_gain)
                    
                    # Apply gain (Vectorization)
                    audio_float = audio_float * current_gain
                    
                    # Hard limit clipping to avoid audio corruption
                    audio_float = np.clip(audio_float, -1.0, 1.0)
                
                # Vectorized conversion: float32 [-1.0, 1.0] -> int16 [-32768, 32767]
                audio_int16 = np.int16(audio_float * 32767)
                
                # Push to queue for the Discord bot to consume
                try:
                    # Use non-blocking put into a massive queue to prevent skipping
                    queue.put(audio_int16.tobytes(), block=False)
                except multiprocessing.queues.Full:
                    # Only drop if we somehow accumulate more than a minute of lag
                    pass
            else:
                time.sleep(0.01)

class ProcessAudioCaptureService(IAudioCapture):
    def __init__(self, process_identifier: str = "firefox.exe"):
        self.process_identifier = process_identifier
        # Massive buffer (maxsize=3000 is ~60 seconds of audio) to prioritize smoothness over liveness
        self._queue = multiprocessing.Queue(maxsize=3000) 
        self._stop_event = multiprocessing.Event()
        self._process = None

    def start(self):
        if self._process and self._process.is_alive():
            return
            
        pid = get_process_id_by_identifier(self.process_identifier)
        if not pid:
            print(f"Error: Could not find process '{self.process_identifier}'. Ensure it is running.")
            return

        self._stop_event.clear()
        
        # Distributed/Multiprocessing
        self._process = multiprocessing.Process(
            target=capture_process_worker,
            args=(pid, self._queue, self._stop_event),
            daemon=True
        )
        self._process.start()
        print(f"Started capturing audio from {self.process_identifier} (PID: {pid}) in parallel process.")

    def stop(self):
        if self._process:
            self._stop_event.set()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None

    def get_audio_queue(self) -> multiprocessing.Queue:
        return self._queue
