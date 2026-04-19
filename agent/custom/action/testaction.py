# autodori_agent.py (重构后的文件)
import json
import logging
from maa.custom_action import CustomAction
from maa.context import Context

class TestAction(CustomAction):

    def run(self, context: Context, argv: CustomAction.RunArg) -> bool:
        
        # 获取当前主程序连接的模拟器信息
        ctrl = context.tasker.controller.info
        print(f"当前连接的模拟器信息: {ctrl}")
        logging.info(f"当前连接的模拟器信息: {ctrl}")
        
        return True