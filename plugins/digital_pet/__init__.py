# -----------------------------------------------------------------------------
# digital_pet/__init__.py - 电子宠物插件
# -----------------------------------------------------------------------------

import time
import random
import json
import asyncio
import re
from dataclasses import dataclass, asdict

# 插件元数据
__plugin__ = {
    "name": "电子宠物",
    "id": "digital_pet",
    "version": "1.5.3",
    "author": "AWdress",
    "scope": "user",
    "description": "在 Telegram 养成你的专属电子宠物！支持领养、喂食、玩耍、清洁、成长和定时状态提醒。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/digital_pet/logo.png",
    "changelog": "v1.5.3 参照示例文件修复命令无响应的根本原因\n- 移除对 ctx.kv 的所有 await 调用，对齐平台KV接口\n- 确保命令监听器使用正确的 filters.outgoing & filters.text\n\nv1.5.2 修复命令无响应 - reply改为edit\n\nv1.5.1 增加完整异常捕获和错误日志",
    "requirements": [],
    "default_enabled": False,
    "config_schema": {
        "auto_reminder_enabled": {
            "type": "boolean",
            "default": True,
            "label": "启用自动提醒",
            "section": "运行设置",
        },
        "heartbeat_interval_min": {
            "type": "slider",
            "default": 60,
            "label": "状态检查间隔（分钟）",
            "min": 10,
            "max": 360,
            "step": 10,
            "section": "运行设置",
        },
        "decay_multiplier": {
            "type": "slider",
            "default": 100,
            "label": "状态衰减倍率（%）",
            "min": 50,
            "max": 300,
            "step": 10,
            "section": "运行设置",
        },
        "adopt_command": {
            "type": "string",
            "default": "/adopt",
            "label": "领养命令",
            "section": "命令说明",
        },
        "info": {
            "type": "info",
            "label": "玩法说明",
            "section": "命令说明",
            "text": "先发送 /adopt 名字 领养宠物，再用 /status、/feed、/play、/clean 与它互动。改动检查间隔后建议重载插件生效。"
        }
    },
}

@dataclass
class Pet:
    user_id: int
    name: str
    species: str
    level: int = 1
    xp: int = 0
    hunger: float = 20.0
    happiness: float = 80.0
    cleanliness: float = 10.0
    last_update_ts: int = 0
    def __post_init__(self):
        if self.last_update_ts == 0:
            self.last_update_ts = int(time.time())
    def to_dict(self):
        return asdict(self)
    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data.get("user_id", 0),
            name=data.get("name", "未命名"),
            species=data.get("species", "未知"),
            level=data.get("level", 1),
            xp=data.get("xp", 0),
            hunger=data.get("hunger", 20.0),
            happiness=data.get("happiness", 80.0),
            cleanliness=data.get("cleanliness", 10.0),
            last_update_ts=data.get("last_update_ts", int(time.time())),
        )

async def setup(ctx):
    def get_pet_owners():
        owners_json = ctx.kv.get("pet_owners_list")
        if not owners_json:
            return []
        try:
            return json.loads(owners_json)
        except (json.JSONDecodeError, TypeError) as e:
            ctx.log.warning(f"宠物主人列表数据损坏: {e}")
            ctx.kv.delete("pet_owners_list")
            return []

    def add_pet_owner(user_id: int):
        owners = get_pet_owners()
        if user_id not in owners:
            owners.append(user_id)
            ctx.kv.set("pet_owners_list", json.dumps(owners))

    def update_pet_state(pet: Pet) -> Pet:
        now = int(time.time())
        elapsed_hours = (now - pet.last_update_ts) / 3600.0
        if elapsed_hours < 0: elapsed_hours = 0
        try:
            decay_multiplier = float(ctx.config.get("decay_multiplier", 100) or 100) / 100.0
        except (ValueError, TypeError):
            decay_multiplier = 1.0
        decay_multiplier = max(0.5, min(decay_multiplier, 3.0))
        hunger_rate, happiness_rate, cleanliness_rate = 5 * decay_multiplier, 3 * decay_multiplier, 2 * decay_multiplier
        pet.hunger = min(100, pet.hunger + hunger_rate * elapsed_hours)
        pet.happiness = max(0, pet.happiness - happiness_rate * elapsed_hours)
        pet.cleanliness = min(100, pet.cleanliness + cleanliness_rate * elapsed_hours)
        pet.last_update_ts = now
        return pet

    def get_and_update_pet(user_id: int):
        pet_data = ctx.kv.get(f"pet_{user_id}")
        if not pet_data: return None
        try:
            pet = Pet.from_dict(json.loads(pet_data))
            return update_pet_state(pet)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            ctx.log.warning(f"用户 {user_id} 的宠物数据损坏: {e}")
            return None

    def save_pet(user_id: int, pet: Pet):
        ctx.kv.set(f"pet_{user_id}", json.dumps(pet.to_dict()))

    def _bare(command: str, fallback: str) -> str:
        return (command or "").lstrip("/.").strip().lower() or fallback
    def _matches(text: str, bare: str) -> bool:
        head = text.split(maxsplit=1)[0].lower() if text else ""
        return head in (f"/{bare}", f".{bare}")

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-12)
    async def pet_commands(client, message):
        text = message.text or ""
        adopt_bare = _bare(ctx.config.get("adopt_command", "/adopt"), "adopt")
        async def handle_adopt_cmd():
            user_id = message.from_user.id
            if get_and_update_pet(user_id): return await message.edit("你已经有一只宠物了！使用 /status 查看它吧。")
            parts = text.split(maxsplit=1)
            pet_name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "小可爱"
            species = random.choice(["电子狗 🐕", "像素猫 🐈", "机械龙 🐉"])
            new_pet = Pet(user_id=user_id, name=pet_name, species=species)
            save_pet(user_id, new_pet); add_pet_owner(user_id)
            await message.edit(f"🎉 恭喜！你领养了一只叫做 **{new_pet.name}** 的{new_pet.species}！\n快来和它互动吧：\n/status - 查看状态\n/feed - 喂食\n/play - 玩耍\n/clean - 清洁")
        async def handle_status_cmd():
            user_id = message.from_user.id
            pet = get_and_update_pet(user_id)
            if not pet: return await message.edit("你还没有领养宠物呢！快使用 /adopt [名字] 来领养一只吧。")
            save_pet(user_id, pet)
            mood_emoji = "😊";
            if pet.happiness < 30 or pet.hunger > 70: mood_emoji = "😟"
            if pet.happiness < 10 or pet.hunger > 90: mood_emoji = "😭"
            status_text = (f"**宠物状态** {mood_emoji}\n\n名字: **{pet.name}**\n物种: {pet.species}\n等级: **{pet.level}** (XP: {int(pet.xp)}/{pet.level * 100})\n-------------------\n❤️ 快乐度: {'🟩' * int(pet.happiness/10)}{'🟥' * (10 - int(pet.happiness/10))} [{int(pet.happiness)}%]\n🍖 饥饿度: {'🟥' * int(pet.hunger/10)}{'🟩' * (10 - int(pet.hunger/10))} [{int(pet.hunger)}%]\n🧼 清洁度: {'🟥' * int(pet.cleanliness/10)}{'🟩' * (10 - int(pet.cleanliness/10))} [{int(pet.cleanliness)}%]")
            await message.edit(status_text)
        async def _interact(action: str):
            user_id = message.from_user.id
            pet = get_and_update_pet(user_id)
            if not pet: return await message.edit("你要和谁互动呀？先用 /adopt 领养一只宠物吧。")
            reply_text, xp_gain = "", 0
            if action == "feed":
                change = random.randint(25, 40); pet.hunger = max(0, pet.hunger - change); pet.happiness = min(100, pet.happiness + 5); xp_gain, reply_text = 10, f"你喂了 {pet.name} 一些好吃的，它满足地打了个嗝。"
            elif action == "play":
                if pet.hunger > 80: return await message.edit(f"{pet.name} 饿得没力气玩了，先喂喂它吧！")
                change = random.randint(20, 35); pet.happiness = min(100, pet.happiness + change); pet.hunger = min(100, pet.hunger + 10); xp_gain, reply_text = 15, f"你和 {pet.name} 玩了一会儿球，它看起来开心极了！"
            elif action == "clean":
                change = random.randint(30, 50); pet.cleanliness = max(0, pet.cleanliness - change); pet.happiness = min(100, pet.happiness + 10); xp_gain, reply_text = 5, f"你给 {pet.name} 洗了个澡，它现在香喷喷的！"
            pet.xp += xp_gain; await message.edit(f"{reply_text} (XP +{xp_gain})")
            if pet.xp >= pet.level * 100:
                pet.level += 1; pet.xp = 0; pet.happiness = min(100, pet.happiness + 20)
                await asyncio.sleep(1); await message.edit(f"🎉 **升级了！** 你的 {pet.name} 升到了 **{pet.level}** 级！")
            save_pet(user_id, pet)
        if _matches(text, adopt_bare): return await handle_adopt_cmd()
        if _matches(text, "status"): return await handle_status_cmd()
        if _matches(text, "feed"): return await _interact("feed")
        if _matches(text, "play"): return await _interact("play")
        if _matches(text, "clean"): return await _interact("clean")

    async def pet_heartbeat():
        if not ctx.config.get("auto_reminder_enabled", True): return
        ctx.log.info("执行电子宠物心跳任务...")
        owners = get_pet_owners(); dead_pets_owners = []
        for user_id in owners:
            await asyncio.sleep(0.1); pet = get_and_update_pet(user_id)
            if not pet: continue
            if pet.happiness <= 0 and pet.hunger >= 100:
                dead_pets_owners.append(user_id); ctx.kv.delete(f"pet_{user_id}")
                try: await ctx.bot.send_message(user_id, f"💔 你的宠物 **{pet.name}** 因为长期得不到照顾，已经离家出走了...")
                except Exception as e: ctx.log.warning(f"无法向用户 {user_id} 发送离家出走通知: {e}")
                continue
            if 80 < pet.hunger < 95 and random.random() < 0.5:
                try: await ctx.bot.send_message(user_id, f"🥺 你的宠物 **{pet.name}** 非常饿了，快给它喂点东西吧！ (/feed)")
                except Exception as e: ctx.log.warning(f"无法向用户 {user_id} 发送饥饿提醒: {e}")
            save_pet(user_id, pet)
        if dead_pets_owners:
            ctx.log.info(f"清理 {len(dead_pets_owners)} 只离家出走的宠物。")
            current_owners = get_pet_owners(); updated_owners = [uid for uid in current_owners if uid not in dead_pets_owners]; ctx.kv.set("pet_owners_list", json.dumps(updated_owners))
        ctx.log.info("电子宠物心跳任务完成。")
    try: interval = int(ctx.config.get("heartbeat_interval_min", 60) or 60)
    except (ValueError, TypeError): interval = 60
    interval = max(10, min(interval, 360))
    if interval < 60: ctx.schedule(pet_heartbeat, "cron", minute=f"*/{interval}", id="电子宠物心跳")
    elif interval == 60: ctx.schedule(pet_heartbeat, "cron", minute="0", id="电子宠物心跳")
    else: hours = max(1, interval // 60); ctx.schedule(pet_heartbeat, "cron", hour=f"*/{hours}", minute="0", id="电子宠物心跳")

async def teardown(ctx):
    ctx.log.info("电子宠物插件正在卸载...")
