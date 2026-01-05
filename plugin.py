import datetime
import asyncio
import json
import os
import random
import math
from typing import List, Optional, Tuple, Type
from plugins.boom_plugin import stock
from src.plugin_system import BasePlugin, register_plugin, ComponentInfo
from src.plugin_system.apis import person_api
from src.common.logger import get_logger
from src.plugin_system.base.base_command import BaseCommand


logger = get_logger("boom_plugin")


# 一个轻量级的异步调度器，提供 add_job/get_job/get_jobs 接口，满足 stock.schedule_stock_price_updates 的调用需求
class _SimpleJob:
    def __init__(self, id: str | None, name: str | None):
        self.id = id
        self.name = name
        self.next_run_time = None
        self._cancel = False

    def cancel(self):
        self._cancel = True


class SimpleScheduler:
    def __init__(self):
        self._jobs: dict[str, _SimpleJob] = {}

    def add_job(self, func, trigger: str, hours: float = 1.0, id: str | None = None, name: str | None = None, next_run_time=None, **kwargs):
        # 仅支持最基本的 interval 调度
        job = _SimpleJob(id=id, name=name)
        self._jobs[id or name or str(id)] = job
        # 预先计算初次运行时间，便于立即查询
        try:
            interval = max(0.0, float(hours)) * 3600.0
            job.next_run_time = datetime.datetime.now() + datetime.timedelta(seconds=interval)
        except Exception:
            job.next_run_time = None

        async def _runner():
            # 初次计算下一次运行时间
            interval = max(0.0, float(hours)) * 3600.0
            while not job._cancel:
                now = datetime.datetime.now()
                job.next_run_time = now + datetime.timedelta(seconds=interval)
                try:
                    # 调用可能是协程函数
                    result = func()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    # 避免任务崩溃影响主循环；记录日志即可
                    logger.exception("调度任务执行出错")
                await asyncio.sleep(interval)

        # 在事件循环中创建后台任务
        try:
            asyncio.create_task(_runner())
        except RuntimeError:
            # 如果在非事件循环上下文被调用，创建一个新的 loop 在后台运行
            loop = asyncio.new_event_loop()
            asyncio.get_event_loop().run_in_executor(None, loop.run_forever)
            loop.call_soon_threadsafe(lambda: asyncio.run(_runner()))

        return job

    def get_job(self, id: str):
        return self._jobs.get(id)

    def get_jobs(self):
        return list(self._jobs.values())


class BoomDataManager:
    """管理爆炸插件的数据"""
    DATA_FILE = os.path.join(os.path.dirname(__file__), "boom_data.json")

    @staticmethod
    def _ensure_data_file():
        """确保数据文件存在"""
        if not os.path.exists(BoomDataManager.DATA_FILE):
            os.makedirs(os.path.dirname(BoomDataManager.DATA_FILE), exist_ok=True)
            with open(BoomDataManager.DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False)

    @staticmethod
    def read_id(uid: int) -> bool:
        """判断ID是否已注册"""
        BoomDataManager._ensure_data_file()
        try:
            with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return False

        return str(uid) in data

    @staticmethod
    def register_id(uid: int):
        """注册用户"""
        BoomDataManager._ensure_data_file()
        try:
            with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        data[str(uid)] = {
            "registered_at": str(datetime.datetime.now()),
            "gold": 10  # 初始金币
        }

        with open(BoomDataManager.DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def add_gold(uid: int, amount: int):
        """为用户添加金币"""
        BoomDataManager._ensure_data_file()
        try:
            with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return

        uid_str = str(uid)
        if uid_str not in data:
            # 如果用户不存在，先注册
            BoomDataManager.register_id(uid)
            # 重新读取数据
            with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)

        if "gold" not in data[uid_str] or not isinstance(data[uid_str]["gold"], int):
            data[uid_str]["gold"] = 0
        # 防止负数余额
        data[uid_str]["gold"] = max(0, data[uid_str]["gold"] + int(amount))

        with open(BoomDataManager.DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    @staticmethod
    def get_gold(uid: int) -> int:
        """根据uid获取用户金币"""
        BoomDataManager._ensure_data_file()
        try:
            with open(BoomDataManager.DATA_FILE, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return 0

        uid_str = str(uid)
        if uid_str in data and "gold" in data[uid_str]:
            return data[uid_str]["gold"]
        return 0


class BoomCommand(BaseCommand):
    command_name = "boom"
    command_description = "产生一次爆炸"

    command_pattern = r"^.金币炸弹 (?P<gold>\w+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        gold_str = self.matched_groups.get("gold")      # 获取爆炸的金币
        # 判断金币是否合法
        if not gold_str.isdigit() or int(gold_str) <= 0:
            return False, "金币数量错误！", False
        #判断数量是否小于5
        if int(gold_str) < 5:
            await self.send_text("金币数量太少了炸不起来，不能小于5个！")
            return False, "金币数量不能少于5！", False  
        try:
            platform = getattr(self.message.message_info, "platform", "")
            user_info = getattr(self.message.message_info, "user_info", None)
            if not user_info:
                return False, "无法获取用户信息！", False
            uid = person_api.get_person_id(platform, user_info.user_id)
        except Exception as e:
            logger.error(f"获取 person_id 失败: {e}")
            return False, "无法获取用户信息！", False

        if not BoomDataManager.read_id(uid):
            BoomDataManager.register_id(uid)    # 注册用户
            await self.send_text(f"你是第一次使用金币炸弹，请使用签到进行注册。")
            return False, f"你是第一次使用金币炸弹，请使用签到进行注册。", False
        

        gold = int(gold_str)
        # 检查用户是否有足够的金币
        current_gold = BoomDataManager.get_gold(uid)
        if current_gold < gold:
            await self.send_text(f"你的金币不足！你只有{current_gold}金币，无法爆炸{gold}金币。")
            return False, f"你的金币不足！你只有{current_gold}金币，无法爆炸{gold}金币。", False

        # 扣除爆炸的金币
        BoomDataManager.add_gold(uid, -gold)
        new_gold = int(random.randint(0, gold * 2))  # 随机0到2倍之间整数
        BoomDataManager.add_gold(uid, new_gold)  # 为用户添加新获得的金币

        await self.send_text(f"你爆炸了{gold}金币！从废墟中获得了{new_gold}金币！目前你有{BoomDataManager.get_gold(uid)}金币。")
        return True, f"你爆炸了{gold}金币！你获得了{new_gold}金币！", False

#签到
class CheckInCommand(BaseCommand):
    command_name = "checkin"
    command_description = "每日签到领取金币"

    command_pattern = r"^.签到$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        try:
            platform = getattr(self.message.message_info, "platform", "")
            user_info = getattr(self.message.message_info, "user_info", None)
            if not user_info:
                return False, "无法获取用户信息！", False
            uid = person_api.get_person_id(platform, user_info.user_id)
        except Exception as e:
            logger.error(f"获取 person_id 失败: {e}")
            return False, "无法获取用户信息！", False
        
        if not BoomDataManager.read_id(uid):
            await self.send_text(f"你是第一次使用签到功能，已为你注册！当前你有10金币。")
            BoomDataManager.register_id(uid)    # 注册用户
            return False, f"你是第一次使用签到功能，已为你注册！", False
        
        # 检查今天是否已经签到
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        try:
            with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        uid_str = str(uid)
        if uid_str in data and "last_checkin" in data[uid_str]:
            if data[uid_str]["last_checkin"] == today_str:
                await self.send_text("你今天已经签到过了，明天再来吧！")
                return False, "你今天已经签到过了，明天再来吧！", False
            
        # 日期是否是连续签到，连续签到了几天
        last_checkin = data.get(uid_str, {}).get("last_checkin", "")
        if last_checkin == (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d"):
            streak = data.get(uid_str, {}).get("streak", 0) + 1
        else:
            streak = 1
        
        # 签到奖励：连续签到的天数个金币 + 0-20个随机金币
        reward_gold = random.randint(0, 20)
        uid_str = str(uid)
        if uid_str not in data:
            data[uid_str] = {}
        # 确保 gold 字段存在且为整数
        if "gold" not in data[uid_str] or not isinstance(data[uid_str]["gold"], int):
            data[uid_str]["gold"] = 0

        total_reward = streak + reward_gold
        # 在同一 data 对象中更新金币和签到信息，避免覆盖问题
        data[uid_str]["gold"] = max(0, int(data[uid_str]["gold"]) + int(total_reward))
        data[uid_str]["last_checkin"] = today_str
        data[uid_str]["streak"] = streak

        with open(BoomDataManager.DATA_FILE, "w", encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        await self.send_text(f"签到成功！你连续签到了{streak}天，你获得了{streak}（连续）+{reward_gold}（随机）共{total_reward}金币！目前你有{data[uid_str]['gold']}金币。")
        return True, "签到成功！你获得了金币！", False

    #查看市场
class MarketCommand(BaseCommand):
        command_name = "market"
        command_description = "查看股票市场信息"

        command_pattern = r"^.市场$"

        #调用stock.py中的函数获取股票信息显示
        #添加下次更新时间
        async def execute(self) -> Tuple[bool, Optional[str], bool]:
            stock_symbols = ["01", "02", "03", "04", "05"]
            market_info = "当前股票市场信息：\n"
            for symbol in stock_symbols:
                stock_info = stock.get_stock_info(symbol)
                if stock_info:
                    market_info += f"{stock_info.name} ({stock_info.symbol}): ${stock_info.price}\n"
                else:
                    market_info += f"{symbol}: 无法获取信息\n"
            next_update_time = stock.get_next_update_time(getattr(self, 'scheduler', None))
            market_info += f"距离下次更新时间: {next_update_time}\n"
            await self.send_text(market_info)
            return True, "查看市场信息成功！", False
        
    #购买股票
class BuyStockCommand(BaseCommand):
    command_name = "buystock"
    command_description = "购买股票"

    command_pattern = r"^.购买(?P<symbol>\w+) (?P<quantity>\d+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
            symbol = self.matched_groups.get("symbol")
            quantity_str = self.matched_groups.get("quantity")
            if not quantity_str.isdigit() or int(quantity_str) <= 0:
                return False, "购买数量错误！", False
            quantity = int(quantity_str)

            stock_info = stock.get_stock_info(symbol)
            if not stock_info:
                await self.send_text(f"股票代码{symbol}不存在！")
                return False, f"股票代码{symbol}不存在！", False

            
            try:
                platform = getattr(self.message.message_info, "platform", "")
                user_info = getattr(self.message.message_info, "user_info", None)
                if not user_info:
                    return False, "无法获取用户信息！", False
                uid = person_api.get_person_id(platform, user_info.user_id)
            except Exception as e:
                logger.error(f"获取 person_id 失败: {e}")
                return False, "无法获取用户信息！", False

            total_price = stock_info.price * quantity
            # 使用整数金币表示，避免浮点截断
            total_price = int(round(total_price))
            # 计算手续费：交易总金额的5%，向上取整，最小1金币
            fee = math.ceil(total_price * 0.05)
            if fee < 1:
                fee = 1
            current_gold = BoomDataManager.get_gold(uid)
            # 购买需要保证能支付价格+手续费
            if current_gold < total_price + fee:
                await self.send_text(f"你的金币不足以购买{quantity}股{stock_info.name}（含手续费{fee}金币），需要{total_price + fee}金币，你只有{current_gold}金币。")
                return False, f"金币不足以购买股票！", False

            # 扣除总费用（买入金额 + 手续费）
            BoomDataManager.add_gold(uid, -(total_price + fee))
            #添加股票信息到boom_data.json中用户持有的股票
            BoomDataManager._ensure_data_file()
            try:
                with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            uid_str = str(uid)
            if uid_str not in data:
                data[uid_str] = {}
            if "stocks" not in data[uid_str]:
                data[uid_str]["stocks"] = {}
            if symbol not in data[uid_str]["stocks"]:
                data[uid_str]["stocks"][symbol] = 0
            data[uid_str]["stocks"][symbol] += quantity
            with open(BoomDataManager.DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            # 更新对应股票的权重：每买10股增加0.01，最大不超过0.2；不足10股不计
            try:
                # 平滑策略：已有权重绝对值越高，新增每 0.01 权重所需股数越多
                # 基础每 0.01 所需股数为 10，按比例放大： required = 10 * (1 + abs(cur_weight))
                # 只对达到 required 的整单位计入权重变化
                # 读取并更新 stock_data.json
                try:
                    with open(stock.DATA_FILE, "r", encoding='utf-8') as sf:
                        stock_data = json.load(sf)
                except (FileNotFoundError, json.JSONDecodeError):
                    stock_data = {}
                if symbol not in stock_data:
                    stock_data[symbol] = {"name": stock_info.name, "price": stock_info.price}
                cur_weight = float(stock_data[symbol].get('weight', 0) or 0)
                required_per_unit = max(1, int(round(10 * (1 + abs(cur_weight)))))
                units = quantity // required_per_unit
                if units > 0:
                    # 买入应当降低权重（购买推低权重），因此为负值
                    weight_add = -0.01 * units
                    new_weight = cur_weight + weight_add
                    stock_data[symbol]['weight'] = new_weight
                    with open(stock.DATA_FILE, "w", encoding='utf-8') as sf:
                        json.dump(stock_data, sf, indent=4, ensure_ascii=False)
            except Exception:
                logger.exception("更新股票权重时出错")

            remaining = BoomDataManager.get_gold(uid)
            await self.send_text(f"你成功购买了{quantity}股{stock_info.name}，总价{total_price}金币，手续费{fee}金币，已扣除，共计{total_price + fee}金币，剩余{remaining}金币。")
            return True, f"成功购买股票！", False
        
#卖出股票
class SellStockCommand(BaseCommand):
    command_name = "sellstock"
    command_description = "卖出股票"
    command_pattern = r"^.卖出(?P<symbol>\w+) (?P<quantity>\d+)$"
    async def execute(self) -> Tuple[bool, Optional[str], bool]:
            symbol = self.matched_groups.get("symbol")
            quantity_str = self.matched_groups.get("quantity")
            if not quantity_str.isdigit() or int(quantity_str) <= 0:
                return False, "卖出数量错误！", False
            quantity = int(quantity_str)

            stock_info = stock.get_stock_info(symbol)
            if not stock_info:
                await self.send_text(f"股票代码{symbol}不存在！")
                return False, f"股票代码{symbol}不存在！", False

            try:
                platform = getattr(self.message.message_info, "platform", "")
                user_info = getattr(self.message.message_info, "user_info", None)
                if not user_info:
                    return False, "无法获取用户信息！", False
                uid = person_api.get_person_id(platform, user_info.user_id)
            except Exception as e:
                logger.error(f"获取 person_id 失败: {e}")
                return False, "无法获取用户信息！", False

            BoomDataManager._ensure_data_file()
            try:
                with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            uid_str = str(uid)
            if uid_str not in data or "stocks" not in data[uid_str] or symbol not in data[uid_str]["stocks"]:
                await self.send_text(f"你没有持有股票{stock_info.name}，无法卖出。")
                return False, f"没有持有该股票，无法卖出！", False

            owned_quantity = data[uid_str]["stocks"][symbol]
            if owned_quantity < quantity:
                await self.send_text(f"你持有的股票{stock_info.name}数量不足，无法卖出{quantity}股。")
                return False, f"持有股票数量不足，无法卖出！", False

            total_price = stock_info.price * quantity
            # 使用整数金币表示，避免浮点截断
            total_price = int(round(total_price))
            # 计算手续费：交易总金额的5%，向上取整，最小1金币
            fee = math.ceil(total_price * 0.05)
            if fee < 1:
                fee = 1
            # 手续费若大于等于总价，则不允许卖出（无意义）
            if fee >= total_price:
                await self.send_text(f"此次卖出手续费{fee}金币不低于卖出总额{total_price}，无法完成卖出。")
                return False, f"手续费过高，无法卖出。", False

            net_gain = total_price - fee
            # 在同一个 data 对象中同时更新金币和持仓，避免先调用 add_gold 写入后被下面的写入覆盖
            if uid_str not in data:
                data[uid_str] = {}
            if "gold" not in data[uid_str] or not isinstance(data[uid_str]["gold"], int):
                data[uid_str]["gold"] = 0
            data[uid_str]["gold"] = max(0, data[uid_str]["gold"] + net_gain)
            # 更新持有的股票数量
            data[uid_str]["stocks"][symbol] -= quantity
            if data[uid_str]["stocks"][symbol] == 0:
                del data[uid_str]["stocks"][symbol]
            with open(BoomDataManager.DATA_FILE, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            # 更新对应股票的权重：每卖10股增加-0.01，最低不小于-0.2；不足10股不计
            try:
                try:
                    with open(stock.DATA_FILE, "r", encoding='utf-8') as sf:
                        stock_data = json.load(sf)
                except (FileNotFoundError, json.JSONDecodeError):
                    stock_data = {}
                if symbol not in stock_data:
                    stock_data[symbol] = {"name": stock_info.name, "price": stock_info.price}
                cur_weight = float(stock_data[symbol].get('weight', 0) or 0)
                required_per_unit = max(1, int(round(10 * (1 + abs(cur_weight)))))
                units = quantity // required_per_unit
                if units > 0:
                    # 卖出应当增加权重（卖出推高权重），因此为正值
                    weight_add = 0.01 * units
                    new_weight = cur_weight + weight_add
                    stock_data[symbol]['weight'] = new_weight
                    with open(stock.DATA_FILE, "w", encoding='utf-8') as sf:
                        json.dump(stock_data, sf, indent=4, ensure_ascii=False)
            except Exception:
                logger.exception("更新股票权重时出错")

            remaining = BoomDataManager.get_gold(uid)
            await self.send_text(f"你成功卖出了{quantity}股{stock_info.name}，卖出总额{total_price}金币，手续费{fee}金币，实得{net_gain}金币，当前余额{remaining}金币。")
            return True, f"成功卖出股票！", False

        #根据用户ID查看持有的股票
class PortfolioCommand(BaseCommand):
        command_name = "portfolio"
        command_description = "查看持有的股票"

        command_pattern = r"^.持仓$"

        async def execute(self) -> Tuple[bool, Optional[str], bool]:
            try:
                platform = getattr(self.message.message_info, "platform", "")
                user_info = getattr(self.message.message_info, "user_info", None)
                if not user_info:
                    return False, "无法获取用户信息！", False
                uid = person_api.get_person_id(platform, user_info.user_id)
            except Exception as e:
                logger.error(f"获取 person_id 失败: {e}")
                return False, "无法获取用户信息！", False

            BoomDataManager._ensure_data_file()
            try:
                with open(BoomDataManager.DATA_FILE, "r", encoding='utf-8') as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                data = {}
            uid_str = str(uid)
            if uid_str not in data or "stocks" not in data[uid_str]:
                await self.send_text("你当前没有持有任何股票。")
                return True, "查看持仓成功！", False

            portfolio_info = "你当前持有的股票：\n"
            for symbol, quantity in data[uid_str]["stocks"].items():
                stock_info = stock.get_stock_info(symbol)
                if stock_info:
                    portfolio_info += f"{stock_info.name} ({stock_info.symbol}): {quantity}股\n"
                else:
                    portfolio_info += f"{symbol}: {quantity}股\n"
            portfolio_info += f"你当前有{BoomDataManager.get_gold(uid)}金币。"
            await self.send_text(portfolio_info)
            return True, "查看持仓成功！", False
        
#查看历史价格
class StockHistoryCommand(BaseCommand):
    command_name = "stockhistory"
    command_description = "查看股票历史价格"

    command_pattern = r"^.历史价格 (?P<symbol>\w+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
            symbol = self.matched_groups.get("symbol")

            history = stock.get_stock_price_history(symbol)
            if not history:
                await self.send_text(f"股票代码{symbol}不存在或无历史价格数据！")
                return False, f"股票代码{symbol}不存在或无历史价格数据！", False

            stock_info = stock.get_stock_info(symbol)
            name = stock_info.name if stock_info else ""
            history_info = f"{symbol}{name}的历史：\n"
            for time_fmt, price in history:
                history_info += f"{time_fmt}: ${price}\n"

            await self.send_text(history_info)
            return True, f"查看股票{symbol}历史价格成功！", False

#.help命令
class HelpCommand(BaseCommand):
    command_name = "boom_help"
    command_description = "查看金币炸弹插件帮助信息"

    command_pattern = r"^.金币炸弹$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        help_text = (
            "金币炸弹插件帮助信息：\n"
            "1. .签到\n"
            "2. .金币炸弹 <数量>\n"
            "3. .市场 - 查看当前股票市场\n"
            "4. .购买<股票id> <数量>\n"
            "5. .卖出<股票id> <数量>\n"
            "6. .持仓 - 查看你当前持有的持仓\n"
            "7. .历史价格 <股票id>"
        )
        await self.send_text(help_text)
        return True, "查看帮助信息成功！", False

@register_plugin
class BoomPlugin(BasePlugin):

    # 插件基本信息
    plugin_name = "Boom_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = []
    config_file_name = "config.toml"
    config_schema = {}

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (BoomCommand.get_command_info(), BoomCommand),
            (CheckInCommand.get_command_info(), CheckInCommand),
            (MarketCommand.get_command_info(), MarketCommand),
            (BuyStockCommand.get_command_info(), BuyStockCommand),
            (PortfolioCommand.get_command_info(), PortfolioCommand),
            (SellStockCommand.get_command_info(), SellStockCommand),
            (HelpCommand.get_command_info(), HelpCommand),
            (StockHistoryCommand.get_command_info(), StockHistoryCommand),
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 尝试创建并启动一个轻量级调度器，供 MarketCommand 查询以及 stock 模块使用
        try:
            self.scheduler = SimpleScheduler()
            # 将 scheduler 传入 stock 中进行调度设置
            try:
                stock.schedule_stock_price_updates(self.scheduler)
            except Exception:
                logger.exception("调用 stock.schedule_stock_price_updates 时出错")
        except Exception:
            self.scheduler = None
            logger.exception("初始化 SimpleScheduler 失败")