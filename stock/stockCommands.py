'''
stockCommands.py主要负责股票命令的处理
在commdands后缀的文件中，只需要处理信息的输入，初步处理后交由core中的模块处理具体逻辑

'''

from typing import Optional, Tuple
from ..core import logCore
from src.plugin_system.apis import person_api
from src.plugin_system.base.base_command import BaseCommand
from . import stockCore
from . import stockPriceControl

# .市场 命令查看市场信息，显示所有股票的当前价格和涨跌情况
class MarketCommand(BaseCommand):
    command_name = "Market"
    command_description = "查看股票市场信息"
    command_pattern = r"^.市场$"
    
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """处理查看市场信息命令"""
        # 获取所有股票信息
        stock_list = stockCore.get_all_stocks()
        if not stock_list:
            await self.send_text("当前没有股票信息。")
            return False, "无股票信息", False
        
        # 构建市场信息文本
        market_info = "股票市场信息:\n"
        for stock in stock_list:
            market_info += f"[{stock.stock_type}]  {stock.stock_id}{stock.stock_name}   {int(stock.stock_price)}$\n"
        
        # 获取下次更新时间
        next_update = stockPriceControl.get_next_update_time()
        if next_update:
            market_info += f"\n下次股票更新时间: {next_update}"
        else:
            market_info += "\n下次股票更新时间: 未知"
        
        await self.send_text(market_info)
        return True, "市场信息发送成功", True
    

# .历史价格 <股票ID> [6m|小时|日] 命令查看指定股票的历史价格记录，默认展示6分钟线
class StockPriceHistoryCommand(BaseCommand):
    command_name = "Stock_Price_History"
    command_description = "查看股票历史价格"
    command_pattern = r"^.历史价格 (?P<stock_id>\w+)(?:\s+(?P<period>\S+))?$"
    
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """处理查看股票历史价格命令"""
        stock_id = self.matched_groups.get('stock_id')
        period_raw = self.matched_groups.get('period')
        if not stock_id:
            await self.send_text("命令格式错误，请使用 .历史价格 <股票ID> [6m|小时|日]")
            return False, "命令格式错误", False

        period_key, period_label = self._normalize_period(period_raw)
        if period_key is None:
            await self.send_text("周期参数仅支持: 6m/小时/日，例如 .历史价格 01 小时")
            return False, "周期参数错误", False

        # 获取股票历史价格
        price_history = stockCore.get_stock_price_history(stock_id, period_key)
        if not price_history:
            await self.send_text(f"未找到股票ID {stock_id} 的{period_label}记录。")
            return False, "无历史价格记录", False
        # 构建历史价格信息文本
        history_info = f"{stock_id}{stockCore.get_stock_name(stock_id)}的{period_label}记录:\n"
        for record in price_history:
            history_info += f"{record}\n"
        history_info += f"当前最新价格: {stockCore.get_stock_current_price(stock_id)}$\n"
        await self.send_text(history_info)
        return True, "历史价格信息发送成功", True

    def _normalize_period(self, period_raw: Optional[str]) -> Tuple[Optional[str], str]:
        """将用户输入归一化为内部周期键"""
        if not period_raw:
            return '6m', '6分钟线'
        normalized = str(period_raw).lower()
        if normalized in ['6m', '6分钟', '分钟', '分', 'min', 'minute', '默认']:
            return '6m', '6分钟线'
        if normalized in ['小时', '小时线', 'h', '1h', 'hour']:
            return '1h', '小时线'
        if normalized in ['日', '日线', 'd', '1d', 'day']:
            return '1d', '日线'
        return None, ''
    
# .购买股票 <股票id> <数量> 命令
class BuyStockCommand(BaseCommand):
    command_name = "Buy_Stock"
    command_description = "购买股票"
    command_pattern = r"^.购买股票 (?P<stock_id>\w+) (?P<quantity>\d+)$"
    
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """处理购买股票命令"""
        # 获取平台和用户ID
        platform = self.message.message_info.platform
        user_id = str(self.message.message_info.user_info.user_id)
        
        # 获取 person_id
        person_id = person_api.get_person_id(platform, user_id)
        
        stock_id = self.matched_groups.get('stock_id')
        quantity_str = self.matched_groups.get('quantity')
        if not stock_id or not quantity_str:
            return False, "命令格式错误", False
        quantity = int(quantity_str)
        if quantity <= 0:
            return False, "购买数量错误", False
        
        # 处理购买逻辑（调用stockCore中的函数）
        success, message = stockCore.buy_stock(person_id, stock_id, quantity)
        await self.send_text(message)
        return success, message, success

# .卖出股票 <股票id> <数量> 命令
class SellStockCommand(BaseCommand):
    command_name = "Sell_Stock"
    command_description = "卖出股票"
    command_pattern = r"^.卖出股票 (?P<stock_id>\w+) (?P<quantity>\d+)$"
    
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """处理卖出股票命令""" 
        # 获取平台和用户ID
        platform = self.message.message_info.platform
        user_id = str(self.message.message_info.user_info.user_id)
        
        # 获取 person_id
        person_id = person_api.get_person_id(platform, user_id)
        
        stock_id = self.matched_groups.get('stock_id')
        quantity_str = self.matched_groups.get('quantity')
        if not stock_id or not quantity_str:
            return False, "命令格式错误", False
        quantity = int(quantity_str)
        if quantity <= 0:
            return False, "卖出数量错误", False
        
        # 处理卖出逻辑（调用stockCore中的函数）
        success, message = stockCore.sell_stock(person_id, stock_id, quantity)
        await self.send_text(message)
        return success, message, success