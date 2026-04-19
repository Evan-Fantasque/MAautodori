import mumuipc
import ldipc
from pathlib import Path

class Player:
    def __init__(self, type_: str, path: Path, index: int) -> None:
        self.type = type_
        self.display_id = -1
        if type_ == "mumuv4":
            self.player = mumuipc.MuMuPlayer(path, index, "v4")
        elif type_ == "mumuv5":
            self.player = mumuipc.MuMuPlayer(path, index, "v5")
        elif type_ == "ld":
            self.player = ldipc.LDPlayer(path, index)

    @property
    def resolution(self):
        return self.player.resolution

    def ipc_capture_display(self):
        if type(self.player) == mumuipc.MuMuPlayer:
            if self.display_id == -1:
                self.display_id = self.player.ipc_get_display_id(
                    "com.bilibili.star.bili"
                )
            # RGBA -> RGB
            return self.player.ipc_capture_display(self.display_id)[:, :, :3]
        elif type(self.player) == ldipc.LDPlayer:
            # RGB
            return self.player.capture()
