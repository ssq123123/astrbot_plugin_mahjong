from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import datetime
import asyncio
import re

@register("mahjong_manager", "YourName", "麻将局管理插件", "1.0.0")
class MahjongManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mahjong_status = {
            1: {"players": [], "max_players": 4, "status": "可报名"},
            2: {"players": [], "max_players": 4, "status": "可报名"},
            3: {"players": [], "max_players": 4, "status": "可报名"},
            4: {"players": [], "max_players": 4, "status": "可报名"},
            5: {"players": [], "max_players": 4, "status": "可报名"}
        }
        self.completed_mahjong = []
        asyncio.create_task(self.reset_mahjong_id_daily())
        asyncio.create_task(self.hourly_status_update())

    async def reset_mahjong_id_daily(self):
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second == 0:
                self.mahjong_status = {i: {"players": [], "max_players": 4, "status": "可报名"} for i in range(1,6)}
                self.completed_mahjong = []
            await asyncio.sleep(1)

    async def hourly_status_update(self):
        while True:
            now = datetime.datetime.now()
            if now.minute == 0 and now.second == 0:
                status_msg = self.generate_mahjong_status()
                group_ids = self.get_all_group_ids()
                for group_id in group_ids:
                    self.context.send_message(group_id, status_msg)
            await asyncio.sleep(1)

    def get_all_group_ids(self):
        return []

    def generate_mahjong_status(self):
        status = []
        for i in range(1, 6):
            players = self.mahjong_status[i]["players"]
            player_count = len(players)
            max_players = self.mahjong_status[i]["max_players"]
            
            join_times = [player["join_time"] for player in players]
            join_times_str = ", ".join(join_times) if join_times else "暂无玩家加入"
            
            color_status = {
                0: ("灰色", "暂时无人"),
                1: ("绿色", "可报名"),
                2: ("绿色", "可报名"),
                3: ("黄色", "即将满员"),
                4: ("红色", "已满员")
            }.get(player_count, ("灰色", "异常状态"))
            
            status.append(f"【{i}号局】{i}块🀄 {player_count}/{max_players}｜10码｜干捞1码 ({color_status[1]})")
            status.append(f"玩家加入时间：{join_times_str}")
        
        if self.completed_mahjong:
            status.append("\n今日已成牌局：")
            status.extend(self.completed_mahjong)
        
        return "\n".join(status)

    def update_mahjong_status(self, mahjong_id, action, user_id):
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

        if not 1 <= mahjong_id <= 5:
            yield event.plain_result("局号需为1-5之间的数字")
            return

        success, reason = self.update_mahjong_status(mahjong_id, "add", user_id)
        
        if not success:
            msg = {
                "满员": f"{mahjong_id}号局已满员",
                "已存在": "您已在局中"
            }.get(reason, "操作失败")
            yield event.plain_result(f"{user_name} {msg}！")
            return

        status_msg = self.generate_mahjong_status()
        current_players = len(self.mahjong_status[mahjong_id]["players"])
        missing = self.mahjong_status[mahjong_id]["max_players"] - current_players
        
        # 生成@消息
        player_ids = [p["id"] for p in self.mahjong_status[mahjong_id]["players"]]
        mentions = " ".join([f"@{self.get_player_name(pid)}" for pid in player_ids])
        
        yield event.plain_result(
            f"{user_name} 成功加入{mahjong_id}号局！\n"
            f"{mentions} 当前{mahjong_id}号局缺{missing}人\n"
            f"{status_msg}"
        )

        if missing == 0:
            await self.handle_full_mahjong(mahjong_id, event)

    @filter.regex(r"^(退|退出)\s*(\d+)?")
    async def remove_player(self, event: AstrMessageEvent):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()
        message = event.message_str
        
        # 处理两种格式：退1 或 退出1
        match = re.search(r"(\d+)", message)
        if not match:
            yield event.plain_result("格式错误，请使用「退X」格式，如：退1")
            return

        try:
            mahjong_id = int(match.group(1))
        except ValueError:
            yield event.plain_result("无效的局号")
            return

        if not 1 <= mahjong_id <= 5:
            yield event.plain_result("局号需为1-5之间的数字")
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

        # 先退出原局
        success, _ = self.update_mahjong_status(from_id, "remove", user_id)
        if not success:
            yield event.plain_result(f"换局失败，您不在{from_id}号局中")
            return

        # 加入新局
        success, reason = self.update_mahjong_status(to_id, "add", user_id)
        if not success:
            # 回滚操作
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

⏰ 每日0点自动重置局号
🕒 每小时整点播报状态
🔔 满员自动通知并清空牌局"""
        yield event.plain_result(rules)

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