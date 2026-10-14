from abc import ABC, abstractmethod


class BaseSender(ABC):
    conf: dict
    name: str

    @abstractmethod
    def send(self, message: str, image_url: str, **kwargs):
        pass
