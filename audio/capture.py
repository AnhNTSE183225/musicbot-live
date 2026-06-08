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
    with ProcessAudioCapture(pid=pid, resample_quality='best') as tap:
        tap.start()
        
        while not stop_event.is_set():
            # Synchronous blocking read (Non-blocking I/O achieved by isolating to this process)
            chunk = tap.read(timeout=0.1)
            if chunk:
                # Chunk is bytes of float32, 48000Hz, Stereo.
                # Convert to numpy array
                audio_float = np.frombuffer(chunk, dtype=np.float32)
                
                # Vectorized conversion: float32 [-1.0, 1.0] -> int16 [-32768, 32767]
                audio_int16 = np.int16(audio_float * 32767)
                
                # Push to queue for the Discord bot to consume
                try:
                    queue.put(audio_int16.tobytes(), block=False)
                except multiprocessing.queues.Full:
                    pass # Drop frame if bot is lagging behind
            else:
                time.sleep(0.01)

class ProcessAudioCaptureService(IAudioCapture):
    def __init__(self, process_identifier: str = "firefox.exe"):
        self.process_identifier = process_identifier
        self._queue = multiprocessing.Queue(maxsize=100) # Buffer
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
