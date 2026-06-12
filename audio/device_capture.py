import multiprocessing
import numpy as np
import time
import soundcard as sc
from audio.interfaces import IAudioCapture

def device_capture_worker(device_name: str, queue: multiprocessing.Queue, stop_event: multiprocessing.Event):
    """
    Background worker process to capture audio from an output device using soundcard loopback.
    """
    # AGC Settings (Same as process capture)
    target_peak = 0.9
    current_gain = 1.0
    attack = 0.8
    release = 0.1
    max_gain = 100.0

    try:
        # Find the loopback microphone by substring match
        if device_name and device_name.lower() != "default":
            mic_device = sc.get_microphone(device_name, include_loopback=True)
        else:
            # Use the default speaker's name to find its loopback microphone
            default_speaker_name = sc.default_speaker().name
            mic_device = sc.get_microphone(default_speaker_name, include_loopback=True)
        
        # We record loopback from the microphone device
        with mic_device.recorder(samplerate=48000, channels=2) as mic:
            while not stop_event.is_set():
                # Record 20ms of audio (960 frames at 48000Hz)
                audio_float = mic.record(numframes=960)
                
                # Directly convert to 16-bit PCM without Automatic Gain Control
                # (AGC can massively amplify the noise floor of hardware devices, causing static)
                audio_int16 = (audio_float * 32767).astype(np.int16)
                
                # Push to queue
                try:
                    queue.put(audio_int16.tobytes(), block=False)
                except multiprocessing.queues.Full:
                    pass
    except Exception as e:
        print(f"Device capture error: {e}")
        # Keep process alive until stop event, but don't spin CPU too fast
        while not stop_event.is_set():
            time.sleep(1)

class DeviceAudioCaptureService(IAudioCapture):
    def __init__(self, target_device: str = "default"):
        self.target_device = target_device
        self._queue = multiprocessing.Queue(maxsize=3000) 
        self._stop_event = multiprocessing.Event()
        self._process = None

    def start(self):
        if self._process and self._process.is_alive():
            return
            
        self._stop_event.clear()
        
        self._process = multiprocessing.Process(
            target=device_capture_worker,
            args=(self.target_device, self._queue, self._stop_event),
            daemon=True
        )
        self._process.start()
        print(f"Started capturing audio from device '{self.target_device}' in parallel process.")

    def stop(self):
        if self._process:
            self._stop_event.set()
            self._process.join(timeout=2)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None

    def get_audio_queue(self) -> multiprocessing.Queue:
        return self._queue
