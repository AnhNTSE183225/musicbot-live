import discord
import queue
import multiprocessing

class ProcessAudioSource(discord.AudioSource):
    """
    Custom audio source that reads from a multiprocessing Queue.
    """
    def __init__(self, audio_queue: multiprocessing.Queue):
        self.queue = audio_queue
        self.buffer = bytearray()
        self.chunk_size = 3840  # 20ms of 48000Hz 16-bit stereo PCM
        self.silence = b'\x00' * self.chunk_size

    def read(self) -> bytes:
        # Pull everything from the queue into the buffer
        try:
            while True:
                # Non-blocking read from queue (Concurrency)
                data = self.queue.get_nowait()
                self.buffer.extend(data)
        except queue.Empty:
            pass

        # If we have enough data, dispense one chunk
        if len(self.buffer) >= self.chunk_size:
            chunk = bytes(self.buffer[:self.chunk_size])
            del self.buffer[:self.chunk_size]
            return chunk
            
        # If we don't have enough data but we are continuously broadcasting,
        # return silence to keep the connection alive without jitter.
        return self.silence

    def cleanup(self):
        self.buffer.clear()
