'''
gold_boom.py主要负责黄金爆炸小游戏的逻辑处理
谁记得我当时只准备写个这个...、
'''

from typing import Optional, Tuple
from src.plugin_system.apis import person_api, send_api
from src.plugin_system.base.base_command import BaseCommand
from ..core import userCore


# .金币炸弹 <数量> 命令
class GoldBoomCommand(BaseCommand):
    command_name = "Gold_Boom"
    command_description = "金币炸弹"
    command_pattern = r"^.金币炸弹 (\d+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """处理金币炸弹小游戏命令"""
        """处理用户查询个人信息命令"""        
        # 获取平台和用户ID
        platform = self.message.message_info.platform
        user_id = str(self.message.message_info.user_info.user_id)
        username = await person_api.get_person_value(person_id, "nickname", user_id)
        
        # 获取 person_id
        person_id = person_api.get_person_id(platform, user_id)

        amount_str = self.matched_groups.get(1)
        if not amount_str:
            return False, "命令格式错误", False
        # 检查用户是否注册
        if not userCore.is_user_registered(person_id):
            await self.send_text("你还没有注册，请先签到注册！")
            return False, "用户未注册", False
        
        try:
            amount = int(amount_str)
            if amount <= 0:
                await self.send_text("请输入正整数数量的金币进行游戏。")
                return False, "无效数量", False
        except ValueError:
            await self.send_text("请输入有效的金币数量。")
            return False, "无效数量格式", False

        # 检查用户金币是否足够
        user_coins = userCore.get_user_info(person_id).coins
        if user_coins < amount:
            await self.send_text(f"你的金币不足，当前持有金币：{user_coins}。")
            return False, "金币不足", False

        # 扣除金币并进行游戏逻辑
        userCore.update_coins_to_user(person_id, -amount)

        # 游戏逻辑,随机获得[-1, +1]倍的金币
        import random
        multiplier = random.choice([-1, 0, 1])
        reward = amount * multiplier + amount  # 赢得的金币
        #为用户添加奖励金币
        userCore.update_coins_to_user(person_id, reward)
        await self.send_text(f"{username}\n你点燃了{amount}金币,从废墟中找到了{reward}金币！\n当前金币数量：{userCore.get_user_info(person_id).coins}")
        return True, "金币炸弹完成", True