from maa.agent.agent_server import AgentServer

from agent.custom.action.Play import Play
from agent.custom.action.SaveSong import SaveSong

from agent.custom.recognition.SongRecognition import SongRecognition

@AgentServer.custom_action("Play")
class PlayClass(Play):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("SaveSong")
class SaveSongClass(SaveSong):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_recognition("SongRecognition")
class SongRecognitionClass(SongRecognition):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")