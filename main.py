from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import datetime
import asyncio
import re
from astrbot.api import AstrBotConfig
from typing import Set
from astrbot.api.event.filter import event_message_type

@register("mahjong_manager", "YourName", "麻将局管理插件", "1.0.0")
class MahjongManager(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.mahjong_status = {
            1: {"tiles": 1, "players": [], "max_players": 4, "permanent": True},
            2: {"tiles": 2, "players": [], "max_players": 4, "permanent": True},
            3: {"tiles": 3, "players": [], "max_players": 4, "permanent": True},
            4: {"tiles": 4, "players": [], "max_players": 4, "permanent": True},
            5: {"tiles": 5, "players": [], "max_players": 4, "permanent": True},
        }
        self.next_custom_id = 6
        self.completed_mahjong = []
        self.push_groups = self.config.get("push_groups", [])
        self.push_start_time = self.config.get("push_start_time", 8)
        self.push_end_time = self.config.get("push_end_time", 22)
        self.creating_sessions: Set[str] = set()
        
        asyncio.create_task(self.reset_mahjong_id_daily())
        asyncio.create_task(self.hourly_status_update())
        asyncio.create_task(self.check_expired_mahjong())

    async def reset_mahjong_id_daily(self):
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second == 0:
                for i in range(1, 6):
                    self.mahjong_status[i]["players"] = []
                self.completed_mahjong = []
            await asyncio.sleep(1)

    async def hourly_status_update(self):
        while True:
            now = datetime.datetime.now()
            current_hour = now.hour
            if self.push_start_time <= current_hour < self.push_end_time:
                if now.minute == 0 and now.second == 0:
                    status_msg = self.generate_mahjong_status()
                    for group_id in self.push_groups:
                        self.context.send_message(group_id, status_msg)
            await asyncio.sleep(1)

    async def check_expired_mahjong(self):
        while True:
            now = datetime.datetime.now()
            to_remove = []
            for mahjong_id in list(self.mahjong_status.keys()):
                info = self.mahjong_status[mahjong_id]
                if not info.get("permanent", False):
                    created_at = info.get("created_at")
                    if created_at and (now - created_at).total_seconds() > 86400:
                        to_remove.append(mahjong_id)
            
            for mahjong_id in to_remove:
                del self.mahjong_status[mahjong_id]
            
            await asyncio.sleep(3600)

    def generate_mahjong_status(self):
        status = ["各麻将局状态："]
        sorted_ids = sorted(self.mahjong_status.keys())
        
        for mahjong_id in sorted_ids:
            info = self.mahjong_status[mahjong_id]
            player_count = len(info["players"])
            max_players = info["max_players"]
            tiles = info["tiles"]
            
            if player_count == 0:
                status_text = "暂时无人"
            elif player_count == max_players:
                status_text = "已满员"
            elif player_count >= max_players - 1:
                status_text = "即将满员"
            else:
                status_text = "可报名"
            
            status_line = f"【{mahjong_id}号局】{tiles}块🀄 {player_count}/{max_players}人（{status_text}）"
            status.append(status_line)
        
        status.append("\n操作提示：")
        status.append("- 发送「加X」加入其他局（如「加1」）")
        status.append("- 发送「退」退出当前局")
        status.append("- 发送「创建对局」创建新对局")
        
        return "\n".join(status)

    def update_mahjong_status(self, mahjong_id, action, user_id):
        if mahjong_id not in self.mahjong_status:
            return False, "无效局号"
        
        players = self.mahjong_status[mahjong_id]["players"]
        existing = any(player["id"] == user_id for player in players)
        
        if action == "add":
            if len(players) >= self.mahjong_status[mahjong_id]["max_players"]:
                return False, "满员"
            if existing:
                return False, "已存在"
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            players.append({"id": user_id, "join_time": current_time})
            return True, "成功"
        
        if action == "remove":
            if not existing:
                return False, "不存在"
            self.mahjong_status[mahjong_id]["players"] = [p for p in players if p["id"] != user_id]
            return True, "成功"
        
        return False, "未知操作"

    @filter.regex(r"^加\s*(\d+)")
    async def add_player(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        match = re.match(r"^加\s*(\d+)", event.message_str)
        
        if not match:
            yield event.plain_result("格式错误，请使用「加X」格式，如：加1")
            return

        try:
            mahjong_id = int(match.group(1))
        except ValueError:
            yield event.plain_result("无效的局号")
            return

        if mahjong_id not in self.mahjong_status:
            yield event.plain_result("无效的局号")
            return

        success, reason = self.update_mahjong_status(mahjong_id, "add", user_id)
        
        if not success:
            msg = {
                "满员": f"{mahjong_id}号局已满员",
                "已存在": "您已在局中"
            }.get(reason, "操作失败")
            yield event.plain_result(f"{user_name} {msg}！")
            return

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        missing = self.mahjong_status[mahjong_id]["max_players"] - len(self.mahjong_status[mahjong_id]["players"])
        
        yield event.plain_result(
            f"{user_name} 成功加入{mahjong_id}号局！\n"
            f"当前{mahjong_id}号局缺{missing}人\n"
            f"玩家加入时间：{current_time}\n\n"
            f"{self.generate_mahjong_status()}"
        )

        if missing == 0:
            await self.handle_full_mahjong(mahjong_id, event)

    @filter.regex(r"^(退|退出)\s*(\d+)?")
    async def remove_player(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        message = event.message_str
        
        match = re.search(r"(\d+)", message)
        if not match:
            yield event.plain_result("格式错误，请使用「退X」格式，如：退1")
            return

        try:
            mahjong_id = int(match.group(1))
        except ValueError:
            yield event.plain_result("无效的局号")
            return

        if mahjong_id not in self.mahjong_status:
            yield event.plain_result("无效的局号")
            return

        success, reason = self.update_mahjong_status(mahjong_id, "remove", user_id)
        
        if success:
            yield event.plain_result(f"{user_name} 已退出{mahjong_id}号局！\n{self.generate_mahjong_status()}")
        else:
            yield event.plain_result(f"{user_name} 未在{mahjong_id}号局中")

    @filter.regex(r"^换\s*(\d+)\s*→\s*(\d+)")
    async def swap_mahjong(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        match = re.match(r"^换\s*(\d+)\s*→\s*(\d+)", event.message_str)
        
        if not match:
            yield event.plain_result("格式错误，请使用「换X→Y」格式")
            return

        from_id = int(match.group(1))
        to_id = int(match.group(2))

        if from_id not in self.mahjong_status or to_id not in self.mahjong_status:
            yield event.plain_result("无效的局号")
            return

        success, _ = self.update_mahjong_status(from_id, "remove", user_id)
        if not success:
            yield event.plain_result(f"换局失败，您不在{from_id}号局中")
            return

        success, reason = self.update_mahjong_status(to_id, "add", user_id)
        if not success:
            self.update_mahjong_status(from_id, "add", user_id)
            msg = "目标牌局已满" if reason == "满员" else "换局失败"
            yield event.plain_result(f"{user_name} {msg}，已恢复原牌局")
            return

        yield event.plain_result(
            f"{user_name} 换局成功！\n"
            f"从{from_id}号局 → {to_id}号局\n"
            f"{self.generate_mahjong_status()}"
        )

    @filter.regex(r"^(查|状态)")
    async def check_status(self, event: AstrMessageEvent):
        yield event.plain_result(self.generate_mahjong_status())

    @filter.regex(r"^规则$")
    async def show_rules(self, event: AstrMessageEvent):
        rules = """【麻将局管理规则】
        
🀄 加入牌局：发送「加X」如「加1」
🚫 退出牌局：发送「退X」如「退1」
🔄 换局操作：发送「换X→Y」如「换1→2」
📊 查看状态：发送「查」或「状态」
📖 查看规则：发送「规则」
➕ 创建对局：发送「创建对局」按提示操作

⏰ 每日0点自动重置1-5号局
🕒 用户创建的对局24小时后自动取消"""
        yield event.plain_result(rules)

    @filter.regex(r"^创建对局$")
    async def create_mahjong(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        self.creating_sessions.add(user_id)
        yield event.plain_result("请输入创建参数（块数 最大人数），例如：3 4")

    @event_message_type(EventMessageType.ALL)
    async def handle_create_params(self, event: AstrMessageEvent):
        user_id = event.get_sender_id()
        if user_id not in self.creating_sessions:
            return
        
        self.creating_sessions.remove(user_id)
        params = event.message_str.split()
        
        if len(params) != 2:
            yield event.plain_result("参数格式错误，请发送「块数 最大人数」")
            return
        
        try:
            tiles = int(params[0])
            max_players = int(params[1])
        except ValueError:
            yield event.plain_result("参数必须为数字")
            return
        
        new_id = self.next_custom_id
        self.next_custom_id += 1
        
        self.mahjong_status[new_id] = {
            "tiles": tiles,
            "players": [],
            "max_players": max_players,
            "permanent": False,
            "created_at": datetime.datetime.now()
        }
        
        yield event.plain_result(
            f"✅ 成功创建{new_id}号局！\n"
            f"块数：{tiles}块｜最大人数：{max_players}人\n"
            f"{self.generate_mahjong_status()}"
        )

    async def handle_full_mahjong(self, mahjong_id, event):
        players = self.mahjong_status[mahjong_id]["players"]
        mentions = " ".join([f"@{self.get_player_name(p['id'])}" for p in players])
        
        record = (
            f"{mahjong_id}号局｜{len(players)}人｜"
            f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        self.completed_mahjong.append(record)
        
        yield event.plain_result(
            f"{mentions}\n"
            f"🎉 {mahjong_id}号局已满员！请及时开局\n"
            f"牌局已重置，可继续报名"
        )
        
        self.mahjong_status[mahjong_id]["players"] = []
        self.push_status_to_group(event)

    def get_player_name(self, user_id):
        return str(user_id)

    def push_status_to_group(self, event):
        group_id = event.get_group_id()
        if group_id:
            self.context.send_message(group_id, self.generate_mahjong_status())

    async def terminate(self):
        pass