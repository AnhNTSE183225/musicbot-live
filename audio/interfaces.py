from abc import ABC, abstractmethod

class IAudioCapture(ABC):
    """
    Interface for audio capture services (SOLID: Dependency Inversion).
    """
    @abstractmethod
    def start(self):
        """Starts the capture process."""
        pass

    @abstractmethod
    def stop(self):
        """Stops the capture process."""
        pass

    @abstractmethod
    def get_audio_queue(self):
        """Returns the multiprocessing.Queue containing audio chunks."""
        pass
