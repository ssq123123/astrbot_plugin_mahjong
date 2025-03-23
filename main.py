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
        self.completed_mahjong = []  # 用于记录已成牌局
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
                self.completed_mahjong = []  # 每日0点清空已成牌局记录
            await asyncio.sleep(60)

    def generate_mahjong_status(self):
        status = []
        for i in range(1, 6):
            if self.mahjong_status[i]["players"] == 0:
                color = "灰色"
                status_desc = "暂时无人"
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
                status.append(f"【🔥{i}号局】{i}🀄 {self.mahjong_status[i]['players']}/{self.mahjong_status[i]['max_players']}｜10码｜干捞1码 ({status_desc})")
            else:
                status.append(f"【{i}号局】{i}🀄 {self.mahjong_status[i]['players']}/{self.mahjong_status[i]['max_players']}｜10码｜干捞1码 ({status_desc})")
        
        # 添加已成牌局信息
        if self.completed_mahjong:
            status.append("\n今日已成牌局：")
            for mahjong in self.completed_mahjong:
                status.append(f"{mahjong}")
        
        return "\n".join(status)

    def update_mahjong_status(self, mahjong_id, action):
        if action == "add":
            if self.mahjong_status[mahjong_id]["players"] < self.mahjong_status[mahjong_id]["max_players"]:
                self.mahjong_status[mahjong_id]["players"] += 1
                # 如果加入后满员，记录到已成牌局
                if self.mahjong_status[mahjong_id]["players"] == self.mahjong_status[mahjong_id]["max_players"]:
                    self.completed_mahjong.append(f"{mahjong_id}号局：{mahjong_id}🀄，{self.mahjong_status[mahjong_id]['players']}/{self.mahjong_status[mahjong_id]['max_players']}，10码，干捞1码")
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

    @filter.command("remove", "退出")
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

    @filter.command("check", "查看")
    async def check_status(self, event: AstrMessageEvent):
        status_msg = self.generate_mahjong_status()
        yield event.plain_result(status_msg)

    @filter.command("rules")
    async def show_rules(self, event: AstrMessageEvent):
        rules_msg = """
        🔍 麻将局管理机器人使用规则：

        1. 加入牌局：
           - 发送“加X”（例如“加2”）加入对应的牌局。
           - 每个牌局最多容纳4人，加入后会自动更新牌局状态。

        2. 退出牌局：
           - 发送“退X”或“退出X”（例如“退2”或“退出2”）退出对应的牌局。
           - 如果牌局已满员，将无法加入；如果牌局当前无人，将无法退出。

        3. 查看牌局状态：
           - 发送“查”或“查看”查看所有牌局的实时状态。
           - 状态包括：可报名（绿色）、即将满员（黄色）、已满员（红色）、已过期（灰色）。

        4. 转换牌局：
           - 发送“换X→Y”（例如“换2→3”）从X局转至Y局。
           - 先自动退出当前牌局，再加入目标牌局。

        5. 查看规则：
           - 发送“规则”查看本使用规则。

        6. 麻将符号说明：
           - 🀅：代表麻将局
           - 🔥：满员提示
           - ⏳：临近自动解散倒计时
           - 🌟：高活跃玩家标记

        注意：24小时未约局将自动解散，计数重置为0。
        """
        yield event.plain_result(rules_msg)

    @filter.command("swap")
    async def swap_mahjong(self, event: AstrMessageEvent, command: str):
        user_name = event.get_sender_name()
        # 解析换局命令，格式为“换X→Y”
        if "→" in command:
            from_mahjong, to_mahjong = command.split("→")
            from_mahjong = int(from_mahjong)
            to_mahjong = int(to_mahjong)
            # 检查局号是否有效
            if 1 <= from_mahjong <= 5 and 1 <= to_mahjong <= 5:
                # 先退出原局
                if self.update_mahjong_status(from_mahjong, "remove"):
                    # 再加入新局
                    if self.update_mahjong_status(to_mahjong, "add"):
                        status_msg = self.generate_mahjong_status()
                        yield event.plain_result(f"{user_name} 已从 {from_mahjong} 号局转至 {to_mahjong} 号局！\n{status_msg}")
                    else:
                        # 如果加入新局失败，重新加入原局
                        self.update_mahjong_status(from_mahjong, "add")
                        yield event.plain_result(f"{to_mahjong} 号局已满员，无法转局！")
                else:
                    yield event.plain_result(f"{from_mahjong} 号局当前无人，无法转局！")
            else:
                yield event.plain_result("局号无效，请输入1-5之间的数字。")
        else:
            yield event.plain_result("换局命令格式错误，请使用“换X→Y”的格式。")

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''