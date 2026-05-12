from maa.agent.agent_server import AgentServer

from agent.custom.action.Play import Play
from agent.custom.action.SaveSong import SaveSong
from agent.custom.action.HandleLiveBoost import HandleLiveBoost
from agent.custom.action.SavePlayResult import SavePlayResult

from agent.custom.recognition.SongRecognition import SongRecognition
from agent.custom.recognition.LiveBoostRecognition import LiveBoostRecognition
from agent.custom.recognition.PlayResultRecognition import PlayResultRecognition

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

@AgentServer.custom_action("HandleLiveBoost")
class HandleLiveBoostClass(HandleLiveBoost):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_action("SavePlayResult")
class SavePlayResultClass(SavePlayResult):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_recognition("SongRecognition")
class SongRecognitionClass(SongRecognition):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_recognition("LiveBoostEnoughRecognition")
class LiveBoostEnoughRecognitionClass(LiveBoostRecognition):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")

@AgentServer.custom_recognition("PlayResultRecognition")
class PlayResultRecognitionClass(PlayResultRecognition):
    def __init__(self):
        super().__init__()
        print(f"{self.__class__.__name__} 初始化")