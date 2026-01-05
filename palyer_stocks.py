from typing import Optional, Tuple
from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
#查看玩家菜单
class PlayerStocksMenu(BasePlugin):
    command_name = "paleMenu"
    command_description = "玩家菜单"
    command_pattern = r"^.玩家菜单 (?P<num>\w+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        #获取菜单项
        num_str = self.matched_groups.get("num")

        if not num_str or not num_str.isdigit():
            async def execute(self) -> Tuple[bool, Optional[str], bool]:
                player_help = (
                    "玩家菜单帮助信息：\n"
                    "1. 自上架股票管理\n"
                    "2. 扑克对战"
                )
                await self.send_text(player_help)
                return True, "查看帮助信息成功！", False
            
        if num_str == "1":
            async def execute(self) -> Tuple[bool, Optional[str], bool]:
                player_help = (
                    "自上架股票管理：\n"
                    "1. 上架新股票(1000金币)\n"
                    "2. 调整交易税率\n"
                    "3. 补充管理税率\n"
                )
                await self.send_text(player_help)
                return True, "查看帮助信息成功！", False