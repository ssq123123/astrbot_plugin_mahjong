from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import datetime
import asyncio

@register("mahjong_manager", "YourName", "麻将局管理插件", "1.0.0")
class MahjongManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mahjong_status = {
            1: {"players": 0, "max_players": 4, "status": "可报名"},
            2: {"players": 0, "max_players": 4, "status": "可报名"},
            3: {"players": 0, "max_players": 4, "status": "可报名"},
            4: {"players": 0, "max_players": 4, "status": "可报名"},
            5: {"players": 0, "max_players": 4, "status": "可报名"}
        }
        # 每日0点重置局号系统
        asyncio.create_task(self.reset_mahjong_id_daily())

    async def reset_mahjong_id_daily(self):
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second == 0:
                self.mahjong_status = {
                    1: {"players": 0, "max_players": 4, "status": "可报名"},
                    2: {"players": 0, "max_players": 4, "status": "可报名"},
                    3: {"players": 0, "max_players": 4, "status": "可报名"},
                    4: {"players": 0, "max_players": 4, "status": "可报名"},
                    5: {"players": 0, "max_players": 4, "status": "可报名"}
                }
            await asyncio.sleep(60)

    def generate_mahjong_status(self):
        status = []
        for i in range(1, 6):
            if self.mahjong_status[i]["players"] == 0:
                color = "灰色"
                status_desc = "已过期"
            elif self.mahjong_status[i]["players"] < self.mahjong_status[i]["max_players"] - 1:
                color = "绿色"
                status_desc = "可报名"
            elif self.mahjong_status[i]["players"] == self.mahjong_status[i]["max_players"] - 1:
                color = "黄色"
                status_desc = "即将满员"
            else:
                color = "红色"
                status_desc = "已满员"
            
            if self.mahjong_status[i]["players"] == self.mahjong_status[i]["max_players"]:
                status.append(f"【🔥{i}号局】{i}🀇 {self.mahjong_status[i]['players']}/{self.mahjong_status[i]['max_players']}｜10码｜干捞1码 ({status_desc})")
            else:
                status.append(f"【{i}号局】{i}🀇 {self.mahjong_status[i]['players']}/{self.mahjong_status[i]['max_players']}｜10码｜干捞1码 ({status_desc})")
        return "\n".join(status)

    def update_mahjong_status(self, mahjong_id, action):
        if action == "add":
            if self.mahjong_status[mahjong_id]["players"] < self.mahjong_status[mahjong_id]["max_players"]:
                self.mahjong_status[mahjong_id]["players"] += 1
                return True
            else:
                return False
        elif action == "remove":
            if self.mahjong_status[mahjong_id]["players"] > 0:
                self.mahjong_status[mahjong_id]["players"] -= 1
                return True
            else:
                return False
        return False

    @filter.command("add")
    async def add_player(self, event: AstrMessageEvent, mahjong_id: int):
        user_name = event.get_sender_name()
        if 1 <= mahjong_id <= 5:
            if self.update_mahjong_status(mahjong_id, "add"):
                status_msg = self.generate_mahjong_status()
                yield event.plain_result(f"{user_name} 已加入 {mahjong_id} 号局！\n{status_msg}")
            else:
                yield event.plain_result(f"{mahjong_id} 号局已满员，无法加入！")
        else:
            yield event.plain_result("局号无效，请输入1-5之间的数字。")

    @filter.command("remove")
    async def remove_player(self, event: AstrMessageEvent, mahjong_id: int):
        user_name = event.get_sender_name()
        if 1 <= mahjong_id <= 5:
            if self.update_mahjong_status(mahjong_id, "remove"):
                status_msg = self.generate_mahjong_status()
                yield event.plain_result(f"{user_name} 已退出 {mahjong_id} 号局！\n{status_msg}")
            else:
                yield event.plain_result(f"{mahjong_id} 号局当前无人，无法退出！")
        else:
            yield event.plain_result("局号无效，请输入1-5之间的数字。")

    @filter.command("check")
    async def check_status(self, event: AstrMessageEvent):
        status_msg = self.generate_mahjong_status()
        yield event.plain_result(status_msg)

    @filter.command("rules")
    async def show_rules(self, event: AstrMessageEvent):
        rules_msg = """
        🔍 规则说明：
        🀇=筒子局 🏷=底分10码 🎣=干捞1码
        """
        yield event.plain_result(rules_msg)

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''