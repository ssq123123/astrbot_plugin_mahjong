from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import datetime
import asyncio
import re

@register(
    "mahjong_manager", 
    "YourName", 
    "麻将局管理插件", 
    "1.0.0",
    config_schema={
        "hourly_push_groups": {
            "type": "array",
            "items": {"type": "string"},
            "title": "每小时推送的群号列表",
            "description": "在此添加需要接收每小时状态推送的群号，每个群号占一行",
            "default": []
        }
    }
)
class MahjongManager(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config = context.config
        self.mahjong_data = {}  # {group_id: {mahjong_status: {}, completed: []}}
        self.tasks = []
        
        # 初始化定时任务
        self.tasks.append(asyncio.create_task(self.reset_mahjong_id_daily()))
        self.tasks.append(asyncio.create_task(self.hourly_status_update()))
        
    def _init_group(self, group_id):
        """初始化群组数据"""
        if group_id not in self.mahjong_data:
            self.mahjong_data[group_id] = {
                "mahjong_status": {
                    i: {"players": [], "max_players": 4, "status": "可报名"}
                    for i in range(1,6)
                },
                "completed": []
            }

    async def reset_mahjong_id_daily(self):
        """每日零点重置牌局"""
        while True:
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0 and now.second == 0:
                for group_data in self.mahjong_data.values():
                    group_data["mahjong_status"] = {
                        i: {"players": [], "max_players": 4, "status": "可报名"}
                        for i in range(1,6)
                    }
                    group_data["completed"] = []
            await asyncio.sleep(1)

    async def hourly_status_update(self):
        """每小时推送状态"""
        while True:
            now = datetime.datetime.now()
            if now.minute == 0 and now.second == 0:
                push_groups = self.config.get("hourly_push_groups", [])
                for group_id in push_groups:
                    self._init_group(group_id)
                    status_msg = self._generate_status(group_id)
                    self.context.send_message(group_id, status_msg)
            await asyncio.sleep(1)

    def _generate_status(self, group_id):
        """生成状态信息"""
        data = self.mahjong_data.get(group_id)
        if not data:
            return "当前群组未初始化"
        
        status = []
        for i in range(1, 6):
            game = data["mahjong_status"][i]
            players = game["players"]
            player_count = len(players)
            
            # 状态颜色逻辑
            color_status = {
                0: ("灰色", "暂时无人"),
                1: ("绿色", "可报名"),
                2: ("绿色", "可报名"),
                3: ("黄色", "即将满员"),
                4: ("红色", "已满员")
            }.get(player_count, ("灰色", "异常状态"))
            
            # 玩家加入时间
            join_times = ", ".join(p["join_time"] for p in players) if players else "暂无玩家加入"
            
            status.append(
                f"【{i}号局】{i}块🀄 {player_count}/4｜10码｜干捞1码 ({color_status[1]})\n"
                f"玩家加入时间：{join_times}"
            )
        
        # 已完成牌局
        if data["completed"]:
            status.append("\n今日已成牌局：")
            status.extend(data["completed"])
        
        return "\n\n".join(status)

    def _update_game(self, group_id, mahjong_id, action, user_id, user_name):
        """更新牌局状态"""
        self._init_group(group_id)
        game = self.mahjong_data[group_id]["mahjong_status"][mahjong_id]
        
        if action == "add":
            if len(game["players"]) >= 4:
                return False, "满员"
            if any(p["id"] == user_id for p in game["players"]):
                return False, "已存在"
            
            game["players"].append({
                "id": user_id,
                "name": user_name,
                "join_time": datetime.datetime.now().strftime("%H:%M:%S")
            })
            return True, "成功"
        
        if action == "remove":
            original_count = len(game["players"])
            game["players"] = [p for p in game["players"] if p["id"] != user_id]
            return len(game["players"]) < original_count, "成功"
        
        return False, "未知操作"

    @filter.regex(r"^加\s*(\d+)")
    async def add_player(self, event: AstrMessageEvent):
        """加入牌局"""
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        match = re.match(r"^加\s*(\d+)", event.message_str)
        if not match:
            yield event.plain_result("格式错误，请使用「加X」格式，如：加1")
            return
        
        try:
            mahjong_id = int(match.group(1))
            if not 1 <= mahjong_id <= 5:
                raise ValueError
        except:
            yield event.plain_result("局号需为1-5之间的数字")
            return
        
        success, reason = self._update_game(group_id, mahjong_id, "add", user_id, user_name)
        
        if not success:
            msg_map = {"满员": "该局已满员", "已存在": "您已在局中"}
            yield event.plain_result(f"{user_name} {msg_map.get(reason, '操作失败')}！")
            return
        
        # 生成@消息
        players = self.mahjong_data[group_id]["mahjong_status"][mahjong_id]["players"]
        mentions = " ".join(f"@{p['name']}" for p in players)
        missing = 4 - len(players)
        
        response = (
            f"{user_name} 成功加入{mahjong_id}号局！\n"
            f"{mentions} 当前缺{missing}人\n\n"
            f"{self._generate_status(group_id)}"
        )
        
        # 满员处理
        if missing == 0:
            self.mahjong_data[group_id]["completed"].append(
                f"{mahjong_id}号局｜{datetime.datetime.now().strftime('%m-%d %H:%M')}"
            )
            self.mahjong_data[group_id]["mahjong_status"][mahjong_id]["players"] = []
            response += "\n\n🎉 牌局已满员，自动重置！"
        
        yield event.plain_result(response)

    @filter.regex(r"^(退|退出)\s*(\d+)?")
    async def remove_player(self, event: AstrMessageEvent):
        """退出牌局"""
        group_id = event.get_group_id()
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        match = re.search(r"(\d+)", event.message_str)
        if not match:
            yield event.plain_result("格式错误，请使用「退X」格式，如：退1")
            return
        
        try:
            mahjong_id = int(match.group(1))
            if not 1 <= mahjong_id <= 5:
                raise ValueError
        except:
            yield event.plain_result("局号需为1-5之间的数字")
            return
        
        success, _ = self._update_game(group_id, mahjong_id, "remove", user_id, None)
        
        if success:
            response = f"{user_name} 已退出{mahjong_id}号局！\n\n{self._generate_status(group_id)}"
        else:
            response = f"{user_name} 未在{mahjong_id}号局中"
        
        yield event.plain_result(response)

    async def terminate(self):
        """插件卸载时清理资源"""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)