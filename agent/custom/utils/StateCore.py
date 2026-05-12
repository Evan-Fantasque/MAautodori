import threading
import agent.custom.utils.player as player
from minitouchpy import MNT
from maa.context import Context
from minitouchpy import (
    MNT,
    MNTEvATive7LogEventData,
    MNTEvent,
    MNTEventData,
    MNTServerCommunicateType,
)
from typing import Optional
from agent.deploy.deploy import get_main_py_path
from agent.custom.utils.chart import Chart
from agent.custom.utils.api import BestdoriAPI
from pathlib import Path


class MAautodoriState:
    """自动化打歌任务的全局生命周期状态管理"""

    def __init__(self):
        # --- 设备与基础组件 ---
        self.player: Optional[player.Player] = None
        self.mnt: Optional[MNT] = None
        self.orientation: int = 0

        self.all_songs: dict = BestdoriAPI.get_song_list()
        self.all_song_name_indexes: dict[str, str] = {
            list(filter(lambda title: title is not None, sinfo["musicTitle"]))[0]: sid
            for sid, sinfo in self.all_songs.items()
        }

        # --- 当前歌曲状态 ---
        self.current_song_id: Optional[str] = None
        self.current_song_name: Optional[str] = None
        self.current_chart: Optional[Chart] = None
        self.current_mode: Optional[str] = None

        # --- 任务配置 ---
        self.live_mode: str = "free_auto"
        self.difficulty: str = "expert"
        self.is_full_song: bool = False
        self.is_high_difficulty: bool = False
        self.max_attempt_count: int = 1
        self.max_continuous_not_fc_count: int = 1
        self.max_continuous_failed_times: int = 10
        self.human_delay_enabled: bool = False
        self.default_move_slice_size: int = 10
        self.cmd_slice_size: int = 100
        self.offset: dict = {"up": 0, "down": 0, "move": 0, "wait": 0.0, "interval": 0.0}
        self.roi: Optional[list] = None

        # --- 统计与记录 ---
        self.play_failed_times: int = 0
        self.not_fc_count_dict: dict[str, int] = {}
        self.song_attempt_count_dict: dict[str, int] = {}
        self.last_played_song_id: Optional[str] = None
        self.min_liveboost: int = 1

        # --- 线程控制 ---
        self.stop_event = threading.Event()
        self.playback_started_event = threading.Event()
        self.playback_interrupted: bool = False

        # --- 触控偏移回调数据 ---
        self.callback_data_lock = threading.Lock()
        self.callback_data = self._generate_default_callback_data()

        # --- 触控命令日志 ---
        self.cmd_log_list: list = []
        self.cmd_log_list_lock = threading.Lock()
    
    def __del__(self):
        # 确保在对象销毁时清理资源
        if self.mnt:
            self.mnt.stop()
        if self.player:
            del self.player

    def _generate_default_callback_data(self):
        return {
            "wait": {"total": 0, "total_offset": 0.0},
            "move": {"uncommited": 0, "total": 0, "total_offset": 0.0},
            "up": {"uncommited": 0, "total": 0, "total_offset": 0.0},
            "down": {"uncommited": 0, "total": 0, "total_offset": 0.0},
            "interval": {"total": 0, "total_offset": 0.0},
            "last_cmd_endtime": -1,
        }
    
    def clear_cmd_log(self):
        """清空触控命令日志"""
        with self.cmd_log_list_lock:
            self.cmd_log_list.clear()

    def reset_for_new_task(self):
        """在新一轮打歌任务开始前重置必要的临时状态"""
        self.stop_event.clear()
        self.playback_started_event.clear()
        self.playback_interrupted = False
        with self.callback_data_lock:
            self.callback_data = self._generate_default_callback_data()

    # 可以提供线程安全的更新方法
    def update_failed_times(self, is_success: bool):
        if is_success:
            self.play_failed_times = 0
        else:
            self.play_failed_times += 1

    def mnt_callback(self, event: MNTEvent, data: MNTEventData):
        if event == MNTEvent.EVATIVE7_LOG:
            data: MNTEvATive7LogEventData = data

            cmd = data.cmd
            cost = data.cost

            with self.cmd_log_list_lock:
                self.cmd_log_list.append(data)
            cmd_type = cmd.split(" ")[0]

            with self.callback_data_lock:
                if (
                    last_cmd_endtime := self.callback_data.get("last_cmd_endtime")
                ) != -1 and type(last_cmd_endtime) == float:
                    self.callback_data["interval"]["total"] += 1
                    self.callback_data["interval"]["total_offset"] += (
                        data.start_time - last_cmd_endtime
                    )
                self.callback_data["last_cmd_endtime"] = data.end_time
                if cmd_type in ["w"]:
                    self.callback_data["wait"]["total"] += 1
                    self.callback_data["wait"]["total_offset"] += cost - int(
                        cmd.split(" ")[-1]
                    )
                elif cmd_type in ["u", "d", "m"]:
                    type_ = {
                        "u": "up",
                        "d": "down",
                        "m": "move",
                    }[cmd_type]
                    self.callback_data[type_]["uncommited"] += 1
                    self.callback_data[type_]["total"] += 1
                    self.callback_data[type_]["total_offset"] += cost
                elif cmd_type in ["c"]:
                    total_uncommited = 0
                    for type_ in ["up", "down", "move"]:
                        total_uncommited += self.callback_data[type_]["uncommited"]

                    if total_uncommited != 0:
                        for type_ in ["up", "down", "move"]:
                            self.callback_data[type_]["total_offset"] += cost * (
                                self.callback_data[type_]["uncommited"]
                                / total_uncommited
                            )
                            self.callback_data[type_]["uncommited"] = 0


global_state = MAautodoriState()

def init_player_and_mnt(context: Context):
    global global_state
    ctrl_info = context.tasker.controller.info

    adb_path = str(ctrl_info.get("adb_path"))
    adb_serial = ctrl_info.get("adb_serial")
    extras = ctrl_info.get("config", {}).get("extras", {})

    type_ = None
    path = None
    index = 0

    # 动态判断模拟器类型
    if "mumu" in extras and extras["mumu"].get("enable"):
        mumu_info = extras["mumu"]
        path = mumu_info.get("path")
        index = mumu_info.get("index", 0)
        # 根据路径或版本进一步判断是 v4 还是 v5
        if "MuMuPlayer12" in path or "nx_main" in adb_path:
            type_ = "mumuv5"
        else:
            type_ = "mumuv4"

    elif "ld" in extras and extras["ld"].get("enable"):
        type_ = "ld"
        path = extras["ld"].get("path")
        index = extras["ld"].get("index", 0)

    if not type_:
        raise RuntimeError("无法从 Context 中识别出支持的模拟器配置(mumu/ld)")

    if type(path) == str:
        current_player = player.Player(type_, Path(path), index)
    else:
        raise RuntimeError("模拟器路径配置错误，必须为字符串类型")
    mnt = MNT(
        adb_serial,
        type_="EvATive7",
        communicate_type=MNTServerCommunicateType.STDIO,
        mnt_asset_path=str(
            get_main_py_path().parent.parent / "assets/minitouch_EvATive7"
        ),
        callback=global_state.mnt_callback,
        adb_executor=adb_path,
    )

    global_state.player = current_player
    global_state.mnt = mnt

    return current_player, mnt
