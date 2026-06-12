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
        # Try to fill the buffer until we have at least chunk_size bytes
        while len(self.buffer) < self.chunk_size:
            try:
                # Block briefly to wait for data (prevents glitchy underflows)
                data = self.queue.get(timeout=0.01)
                self.buffer.extend(data)
            except queue.Empty:
                # If we really don't have enough data after waiting, break out
                break

        # If we have enough data, dispense one chunk
        if len(self.buffer) >= self.chunk_size:
            chunk = bytes(self.buffer[:self.chunk_size])
            del self.buffer[:self.chunk_size]
            return chunk
            
        # Only inject silence if the buffer is genuinely starved
        return self.silence

    def cleanup(self):
        self.buffer.clear()
