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
            1: {"players": [], "max_players": 4, "status": "可报名"},
            2: {"players": [], "max_players": 4, "status": "可报名"},
            3: {"players": [], "max_players": 4, "status": "可报名"},
            4: {"players": [], "max_players": 4, "status": "可报名"},
            5: {"players": [], "max_players": 4, "status": "可报名"}
        }
        self.completed_mahjong = []  # 用于记录已成牌局
        # 每日0点重置局号系统
        asyncio.create_task(self.reset_mahjong_id_daily())
        # 每小时输出牌局信息
        asyncio.create_task(self.hourly_status_update())

    async def reset_mahjong_id_daily(self):
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second == 0:
                self.mahjong_status = {
                    1: {"players": [], "max_players": 4, "status": "可报名"},
                    2: {"players": [], "max_players": 4, "status": "可报名"},
                    3: {"players": [], "max_players": 4, "status": "可报名"},
                    4: {"players": [], "max_players": 4, "status": "可报名"},
                    5: {"players": [], "max_players": 4, "status": "可报名"}
                }
                self.completed_mahjong = []  # 每日0点清空已成牌局记录
            await asyncio.sleep(60)

    async def hourly_status_update(self):
        while True:
            # 每小时整点时推送牌局信息
            now = datetime.datetime.now()
            if now.minute == 0 and now.second == 0:
                status_msg = self.generate_mahjong_status()
                # 获取所有群聊的统一消息来源ID（假设你有多个群聊需要推送）
                # 这里需要根据你的实际需求进行调整
                # 示例中假设你有一个方法 get_all_group_ids() 获取所有群聊ID
                group_ids = self.get_all_group_ids()
                for group_id in group_ids:
                    self.context.send_message(group_id, status_msg)
            await asyncio.sleep(60)

    def get_all_group_ids(self):
        # 这里需要根据你的实际需求实现获取所有群聊ID的逻辑
        # 可能需要从上下文或其他配置中获取
        # 示例返回一个空列表，你需要根据实际情况修改
        return []

    def generate_mahjong_status(self):
        status = []
        for i in range(1, 6):
            players = self.mahjong_status[i]["players"]
            player_count = len(players)
            max_players = self.mahjong_status[i]["max_players"]
            
            # 获取玩家加入时间信息
            join_times = [player["join_time"] for player in players]
            join_times_str = ", ".join(join_times) if join_times else "暂无玩家加入"
            
            if player_count == 0:
                color = "灰色"
                status_desc = "暂时无人"
            elif player_count < max_players - 1:
                color = "绿色"
                status_desc = "可报名"
            elif player_count == max_players - 1:
                color = "黄色"
                status_desc = "即将满员"
            else:
                color = "红色"
                status_desc = "已满员"
            
            status.append(f"【{i}号局】{i}块🀄 {player_count}/{max_players}｜10码｜干捞1码 ({status_desc})")
            status.append(f"玩家加入时间：{join_times_str}")
        
        # 添加已成牌局信息
        if self.completed_mahjong:
            status.append("\n今日已成牌局：")
            for mahjong in self.completed_mahjong:
                status.append(f"{mahjong}")
        
        return "\n".join(status)

    def update_mahjong_status(self, mahjong_id, action, user_id):
        if action == "add":
            if len(self.mahjong_status[mahjong_id]["players"]) < self.mahjong_status[mahjong_id]["max_players"]:
                if user_id not in [player["id"] for player in self.mahjong_status[mahjong_id]["players"]]:
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.mahjong_status[mahjong_id]["players"].append({"id": user_id, "join_time": current_time})
                    return True
                else:
                    return False  # 用户已在该局中
            else:
                return False  # 牌局已满
        elif action == "remove":
            for player in self.mahjong_status[mahjong_id]["players"]:
                if player["id"] == user_id:
                    self.mahjong_status[mahjong_id]["players"].remove(player)
                    return True
            return False  # 用户不在该局中
        return False

    @filter.command("加", "add")
    async def add_player(self, event: AstrMessageEvent, mahjong_id: int):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()  # 获取用户ID
        if 1 <= mahjong_id <= 5:
            if self.update_mahjong_status(mahjong_id, "add", user_id):
                status_msg = self.generate_mahjong_status()
                yield event.plain_result(f"{user_name} 已加入 {mahjong_id} 号局！\n{status_msg}")
                
                # 计算当前牌局还缺少的人数
                current_players = len(self.mahjong_status[mahjong_id]["players"])
                missing_players = self.mahjong_status[mahjong_id]["max_players"] - current_players
                
                # 获取已加入用户的ID列表
                player_ids = [player["id"] for player in self.mahjong_status[mahjong_id]["players"]]
                
                # 获取已加入用户的名称（假设有一个方法get_player_name可以根据用户ID获取名称）
                player_names = [self.get_player_name(player_id) for player_id in player_ids]
                
                # 生成@所有人的消息
                mention_msg = " ".join([f"@{name}" for name in player_names])
                
                # 发送提醒消息
                reminder_msg = f"{mention_msg}，目前{mahjong_id}号局已有{current_players}人加入，还缺少{missing_players}人，请尽快邀请其他人加入！"
                yield event.plain_result(reminder_msg)
                
                # 检查是否满员
                if len(self.mahjong_status[mahjong_id]["players"]) == self.mahjong_status[mahjong_id]["max_players"]:
                    # 满员处理
                    await self.handle_full_mahjong(mahjong_id, event)
                
                # 加入后立即推送牌局信息到群聊
                self.push_status_to_group(event)
            else:
                yield event.plain_result(f"{user_name} 已在 {mahjong_id} 号局中，无需重复加入！")
        else:
            yield event.plain_result("局号无效，请输入1-5之间的数字。")

    async def handle_full_mahjong(self, mahjong_id, event):
        # 获取该牌局的所有参与者
        players = self.mahjong_status[mahjong_id]["players"]
        # 获取参与者的名字（这里需要根据实际情况实现获取名字的逻辑）
        player_names = [self.get_player_name(player["id"]) for player in players]
        # 生成@所有人的消息
        mention_msg = " ".join([f"@{name}" for name in player_names])
        # 发送通知
        full_msg = f"{mention_msg}，{mahjong_id} 号局已满员，请尽快约定时间地点开局！"
        yield event.plain_result(full_msg)
        # 记录到已成牌局
        self.completed_mahjong.append(f"{mahjong_id}号局：{mahjong_id}块🀄，{len(players)}/{self.mahjong_status[mahjong_id]['max_players']}，10码，干捞1码")
        # 刷新该牌局的人员信息
        self.mahjong_status[mahjong_id]["players"] = []

    def get_player_name(self, user_id):
        # 这里需要根据实际情况实现获取用户名字的逻辑
        # 示例中返回用户ID作为名字，你需要根据实际情况修改
        return str(user_id)

    def push_status_to_group(self, event):
        status_msg = self.generate_mahjong_status()
        # 获取当前事件的群聊ID（假设事件发生在群聊中）
        group_id = event.get_group_id()
        if group_id:
            self.context.send_message(group_id, status_msg)

    @filter.command("退", "退出", "remove")
    async def remove_player(self, event: AstrMessageEvent, mahjong_id: int):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()  # 获取用户ID
        if 1 <= mahjong_id <= 5:
            if self.update_mahjong_status(mahjong_id, "remove", user_id):
                status_msg = self.generate_mahjong_status()
                yield event.plain_result(f"{user_name} 已退出 {mahjong_id} 号局！\n{status_msg}")
            else:
                yield event.plain_result(f"{user_name} 不在 {mahjong_id} 号局中，无需退出！")
        else:
            yield event.plain_result("局号无效，请输入1-5之间的数字。")

    @filter.command("查", "查看", "check")
    async def check_status(self, event: AstrMessageEvent):
        status_msg = self.generate_mahjong_status()
        yield event.plain_result(status_msg)

    @filter.command("规则")
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

    @filter.command("换")
    async def swap_mahjong(self, event: AstrMessageEvent, command: str):
        user_name = event.get_sender_name()
        user_id = event.get_sender_id()  # 获取用户ID
        # 解析换局命令，格式为“换X→Y”
        if "→" in command:
            from_mahjong, to_mahjong = command.split("→")
            from_mahjong = int(from_mahjong)
            to_mahjong = int(to_mahjong)
            # 检查局号是否有效
            if 1 <= from_mahjong <= 5 and 1 <= to_mahjong <= 5:
                # 检查用户是否在原局中
                player_exists = False
                for player in self.mahjong_status[from_mahjong]["players"]:
                    if player["id"] == user_id:
                        player_exists = True
                        break
                if player_exists:
                    # 先退出原局
                    self.update_mahjong_status(from_mahjong, "remove", user_id)
                    # 再加入新局
                    if self.update_mahjong_status(to_mahjong, "add", user_id):
                        status_msg = self.generate_mahjong_status()
                        yield event.plain_result(f"{user_name} 已从 {from_mahjong} 号局转至 {to_mahjong} 号局！\n{status_msg}")
                    else:
                        # 如果加入新局失败，重新加入原局
                        self.update_mahjong_status(from_mahjong, "add", user_id)
                        yield event.plain_result(f"{to_mahjong} 号局已满员，无法转局！")
                else:
                    yield event.plain_result(f"{user_name} 不在 {from_mahjong} 号局中，无法转局！")
            else:
                yield event.plain_result("局号无效，请输入1-5之间的数字。")
        else:
            yield event.plain_result("换局命令格式错误，请使用“换X→Y”的格式。")

    async def terminate(self):
        '''可选择实现 terminate 函数，当插件被卸载/停用时会调用。'''