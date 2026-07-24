# -----------------------------------------------------------------------------
# digital_pet/__init__.py - 电子宠物插件
# -----------------------------------------------------------------------------

import time
import random
import json
import asyncio
from pathlib import Path
from dataclasses import dataclass, asdict

__plugin__ = {
    "name": "电子宠物",
    "id": "digital_pet",
    "version": "2.1.0",
    "author": "AWdress",
    "scope": "user",
    "description": "在 Telegram 养成你的专属电子宠物！支持领养、喂食、玩耍、清洁、成长、进化、道具、随机事件和视觉表现。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/digital_pet/logo.png",
    "changelog": "v2.1.0 电子宠物终版增强更新\n- 新增全身像视觉系统、动作图、事件图、成长进化立绘\n- 支持三物种差异化成长：电子狗、像素猫、机械龙\n- 新增随机事件、升级奖励、周期播报、背包与道具体系\n- 新增 /档案、/背包、/使用 等命令\n- 新增命令冷却时间与冷却设置配置项\n- 全部命令彻底中文化，玩法说明和配置界面同步完善",
    "requirements": [],
    "default_enabled": False,
    "config_schema": {
        "auto_reminder_enabled": {"type": "boolean","default": True,"label": "启用自动提醒","section": "运行设置"},
        "heartbeat_interval_min": {"type": "slider","default": 60,"label": "状态检查间隔（分钟）","min": 10,"max": 360,"step": 10,"section": "运行设置"},
        "decay_multiplier": {"type": "slider","default": 100,"label": "状态衰减倍率（%）","min": 50,"max": 300,"step": 10,"section": "运行设置"},
        "auto_delete_replies": {"type": "boolean","default": True,"label": "自动删除插件回复","section": "消息清理"},
        "delete_delay_seconds": {"type": "slider","default": 30,"label": "回复消息保留时间（秒）","min": 5,"max": 300,"step": 5,"section": "消息清理"},
        "show_pet_image": {"type": "boolean","default": True,"label": "状态时显示宠物图片","section": "视觉表现"},
        "use_fullbody_art": {"type": "boolean","default": True,"label": "启用全身像视觉系统","section": "视觉表现"},
        "random_events_enabled": {"type": "boolean","default": True,"label": "启用随机事件","section": "高级玩法"},
        "event_chance_percent": {"type": "slider","default": 25,"label": "随机事件触发概率（%）","min": 0,"max": 100,"step": 5,"section": "高级玩法"},
        "daily_brief_enabled": {"type": "boolean","default": True,"label": "启用周期状态播报","section": "高级玩法"},
        "daily_brief_chance_percent": {"type": "slider","default": 20,"label": "每轮播报概率（%）","min": 0,"max": 100,"step": 5,"section": "高级玩法"},
        "status_cooldown_seconds": {"type": "slider","default": 10,"label": "状态命令冷却（秒）","min": 0,"max": 120,"step": 5,"section": "冷却设置"},
        "action_cooldown_seconds": {"type": "slider","default": 20,"label": "互动命令冷却（秒）","min": 0,"max": 180,"step": 5,"section": "冷却设置"},
        "use_item_cooldown_seconds": {"type": "slider","default": 15,"label": "使用道具冷却（秒）","min": 0,"max": 180,"step": 5,"section": "冷却设置"},
        "info": {"type": "info","label": "玩法说明","section": "命令说明","text": "先发送 /领养 名字 或 .领养 名字 来领养宠物；领养后可用 /状态、/喂食、/玩耍、/清洁 与它互动。用 /档案 查看成长档案，用 /背包 查看道具，用 /使用 道具名 来使用道具。"}
    },
}


DEFAULT_INVENTORY = {"零食": 0, "玩具球": 0, "泡泡浴球": 0, "能量核心": 0}


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
    inventory: dict = None

    def __post_init__(self):
        if self.last_update_ts == 0:
            self.last_update_ts = int(time.time())
        if self.inventory is None:
            self.inventory = DEFAULT_INVENTORY.copy()
        else:
            for k, v in DEFAULT_INVENTORY.items():
                self.inventory.setdefault(k, v)

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
            inventory=data.get("inventory") or DEFAULT_INVENTORY.copy(),
        )


async def setup(ctx):
    base_dir = Path(__file__).resolve().parent

    def get_pet_owners():
        d = ctx.kv.get("pet_owners_list")
        if not d:
            return []
        try:
            return json.loads(d)
        except (json.JSONDecodeError, TypeError) as e:
            ctx.log.warning(f"宠物主人列表数据损坏: {e}")
            ctx.kv.delete("pet_owners_list")
            return []

    def add_pet_owner(uid):
        owners = get_pet_owners()
        if uid not in owners:
            owners.append(uid)
            ctx.kv.set("pet_owners_list", json.dumps(owners))

    def save_pet(uid, pet: Pet):
        ctx.kv.set(f"pet_{uid}", json.dumps(pet.to_dict()))

    def get_pet(uid):
        d = ctx.kv.get(f"pet_{uid}")
        if not d:
            return None
        try:
            return Pet.from_dict(json.loads(d))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            ctx.log.warning(f"用户 {uid} 的宠物数据损坏: {e}")
            return None

    def species_factors(species):
        return {
            '电子狗 🐕': (1.0, 0.9, 1.0),
            '像素猫 🐈': (0.9, 1.0, 1.15),
            '机械龙 🐉': (1.1, 0.85, 0.9),
        }.get(species, (1.0, 1.0, 1.0))

    def update_pet_state(p: Pet) -> Pet:
        now = int(time.time())
        elapsed_hours = max(0, (now - p.last_update_ts) / 3600.0)
        try:
            m = float(ctx.config.get("decay_multiplier", 100) or 100) / 100.0
        except (ValueError, TypeError):
            m = 1.0
        m = max(0.5, min(m, 3.0))
        sf = species_factors(p.species)
        hr, happyr, cr = 5 * m * sf[0], 3 * m * sf[1], 2 * m * sf[2]
        p.hunger = min(100, p.hunger + hr * elapsed_hours)
        p.happiness = max(0, p.happiness - happyr * elapsed_hours)
        p.cleanliness = min(100, p.cleanliness + cr * elapsed_hours)
        p.last_update_ts = now
        return p

    def get_and_update_pet(uid):
        pet = get_pet(uid)
        if not pet:
            return None
        return update_pet_state(pet)

    def stage_for_level(level: int) -> int:
        if level >= 10:
            return 3
        if level >= 5:
            return 2
        return 1

    def species_key(species: str) -> str:
        return {
            '电子狗 🐕': 'dog',
            '像素猫 🐈': 'cat',
            '机械龙 🐉': 'dragon',
        }.get(species, 'dog')

    def _status_image_name(p):
        if p.happiness < 15:
            mood = 'sad'
        elif p.hunger >= 70:
            mood = 'hungry'
        elif p.cleanliness >= 60:
            mood = 'dirty'
        elif p.happiness >= 85 and p.hunger <= 30 and p.cleanliness <= 30:
            mood = 'happy'
        else:
            mood = 'normal'
        if ctx.config.get('use_fullbody_art', True):
            return f"assets_v2/{species_key(p.species)}_{mood}.png"
        return f"assets/{species_key(p.species)}_{mood}.png"

    def _action_image_name(p, action):
        if ctx.config.get('use_fullbody_art', True):
            return f"assets_v2/{species_key(p.species)}_{action}.png"
        return None

    def _evolution_image_name(p):
        return f"evolution/{species_key(p.species)}_stage{stage_for_level(p.level)}.png"

    def _event_pool(p):
        common = [
            {"text": f"✨ {p.name} 在角落里发现了一颗亮晶晶的小零件，看起来心情不错。", "happiness": 8, "xp": 6, "item": "能量核心"},
            {"text": f"😴 {p.name} 打了个哈欠，伸了伸懒腰，今天似乎有点犯困。", "happiness": -3, "hunger": 6},
            {"text": f"🫧 {p.name} 玩着玩着把自己弄脏了一点。", "cleanliness": 12},
            {"text": f"🎁 {p.name} 叼来了一个小玩具，兴奋地围着你转圈。", "happiness": 10, "xp": 8, "item": "玩具球"},
        ]
        by_species = {
            '电子狗 🐕': [
                {"text": f"🐾 {p.name} 追着虚拟球跑了好几圈，开心得尾巴都要摇断了。", "happiness": 12, "hunger": 8, "xp": 10},
            ],
            '像素猫 🐈': [
                {"text": f"🐈 {p.name} 高冷地巡视了一圈领地，然后满意地蹭了蹭你。", "happiness": 9, "xp": 7, "item": "零食"},
            ],
            '机械龙 🐉': [
                {"text": f"🔥 {p.name} 体内的小型能量炉稳定运行，精神状态明显变好了。", "happiness": 7, "cleanliness": -4, "xp": 9, "item": "能量核心"},
            ],
        }
        return common + by_species.get(p.species, [])

    def _apply_event(p, ev):
        p.happiness = max(0, min(100, p.happiness + ev.get('happiness', 0)))
        p.hunger = max(0, min(100, p.hunger + ev.get('hunger', 0)))
        p.cleanliness = max(0, min(100, p.cleanliness + ev.get('cleanliness', 0)))
        p.xp += ev.get('xp', 0)
        item = ev.get('item')
        item_line = ""
        if item:
            p.inventory[item] = p.inventory.get(item, 0) + 1
            item_line = f"\n获得道具：{item} ×1"
        return ev['text'] + item_line

    def _event_image_name(event_text):
        if not event_text:
            return None
        mapping = [
            ('亮晶晶的小零件', 'event_found_item.png'),
            ('打了个哈欠', 'event_sleepy.png'),
            ('弄脏了一点', 'event_dirty.png'),
            ('叼来了一个小玩具', 'event_happy.png'),
        ]
        for key, fn in mapping:
            if key in event_text:
                return f"assets_v2/{fn}"
        return None

    def _maybe_random_event(p):
        if not ctx.config.get('random_events_enabled', True):
            return None
        try:
            chance = int(ctx.config.get('event_chance_percent', 25) or 25)
        except (TypeError, ValueError):
            chance = 25
        chance = max(0, min(100, chance))
        if random.randint(1, 100) > chance:
            return None
        return _apply_event(p, random.choice(_event_pool(p)))

    def _mood_line(p):
        if p.hunger >= 80:
            return f"{p.name} 正眼巴巴地看着你，像是在说：我真的饿啦。"
        if p.cleanliness >= 70:
            return f"{p.name} 看起来灰扑扑的，似乎很想洗个澡。"
        if p.happiness <= 20:
            return f"{p.name} 情绪有点低落，需要你多陪陪它。"
        if p.happiness >= 85:
            return f"{p.name} 今天状态超棒，整只宠物都在发光。"
        return f"{p.name} 正安稳地陪在你身边。"

    def _level_bonus_text(p):
        if p.species == '电子狗 🐕':
            return '汪汪冲刺奖励：快乐度额外 +8'
        if p.species == '像素猫 🐈':
            return '猫猫优雅奖励：清洁度额外 -8'
        if p.species == '机械龙 🐉':
            return '机械龙核心奖励：额外 XP +15'
        return '成长奖励已发放'

    def _inventory_text(p):
        lines = [f"- {k} × {v}" for k, v in p.inventory.items()]
        return "\n".join(lines)

    def _cd_key(uid, name):
        return f"pet_cd:{uid}:{name}"

    def _cooldown_seconds(name):
        mapping = {
            '状态': int(ctx.config.get('status_cooldown_seconds', 10) or 10),
            '喂食': int(ctx.config.get('action_cooldown_seconds', 20) or 20),
            '玩耍': int(ctx.config.get('action_cooldown_seconds', 20) or 20),
            '清洁': int(ctx.config.get('action_cooldown_seconds', 20) or 20),
            '使用': int(ctx.config.get('use_item_cooldown_seconds', 15) or 15),
        }
        return max(0, mapping.get(name, 0))

    def _check_cd(uid, name):
        now = int(time.time())
        raw = ctx.kv.get(_cd_key(uid, name))
        if not raw:
            return 0
        try:
            ts = int(raw)
        except Exception:
            return 0
        remain = ts - now
        return remain if remain > 0 else 0

    def _set_cd(uid, name):
        sec = _cooldown_seconds(name)
        if sec <= 0:
            return
        expire_at = int(time.time()) + sec
        ctx.kv.set(_cd_key(uid, name), str(expire_at))

    async def _edit(m, t):
        try:
            edited = await m.edit(t)
            if ctx.config.get("auto_delete_replies", True):
                d = int(ctx.config.get("delete_delay_seconds", 30) or 30)
                await asyncio.sleep(d)
                await edited.delete()
        except Exception as e:
            ctx.log.debug(f"[电子宠物] 自动删除消息失败: {e!r}")

    async def _send_photo_and_autodelete(client, chat_id, photo_path, caption):
        sent = await client.send_photo(chat_id, str(photo_path), caption=caption)
        if ctx.config.get("auto_delete_replies", True):
            try:
                d = int(ctx.config.get("delete_delay_seconds", 30) or 30)
                await asyncio.sleep(d)
                await sent.delete()
            except Exception as e:
                ctx.log.debug(f"[电子宠物] 自动删除图片消息失败: {e!r}")
        return sent

    def _is_cmd(text, *names):
        head = text.split(maxsplit=1)[0].strip() if text else ""
        return head in names

    @ctx.on_message(ctx.filters.outgoing & ctx.filters.text, group=-12)
    async def pet_commands(client, message):
        text = (message.text or "").strip()

        async def do_adopt():
            uid = message.from_user.id
            if get_and_update_pet(uid):
                return await _edit(message, "你已经有一只宠物了！使用 /状态 查看它吧。")
            parts = text.split(maxsplit=1)
            name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "小可爱"
            species = random.choice(["电子狗 🐕", "像素猫 🐈", "机械龙 🐉"])
            p = Pet(user_id=uid, name=name, species=species)
            save_pet(uid, p)
            add_pet_owner(uid)
            await _edit(message, f"🎉 恭喜！你领养了一只叫做 **{p.name}** 的{p.species}！\n快来和它互动吧：\n/状态 - 查看宠物状态\n/喂食 - 给宠物喂食\n/玩耍 - 和宠物玩耍\n/清洁 - 给宠物清洁\n/档案 - 查看成长档案\n/背包 - 查看拥有的道具")

        async def do_status():
            uid = message.from_user.id
            remain = _check_cd(uid, '状态')
            if remain > 0:
                return await _edit(message, f"⏳ 状态命令冷却中，还需等待 {remain} 秒。")
            _set_cd(uid, '状态')
            p = get_and_update_pet(uid)
            if not p:
                return await _edit(message, "你还没有领养宠物呢！快使用 /领养 [名字] 来领养一只吧。")
            event_text = _maybe_random_event(p)
            save_pet(uid, p)
            mood = _mood_line(p)
            emoji = "😊"
            if p.happiness < 30 or p.hunger > 70:
                emoji = "😟"
            if p.happiness < 10 or p.hunger > 90:
                emoji = "😭"
            extra = f"\n\n**今日动态**\n{event_text}" if event_text else ""
            st = (f"**宠物状态** {emoji}\n\n名字: **{p.name}**\n物种: {p.species}\n等级: **{p.level}** (XP: {int(p.xp)}/{p.level*100})\n成长阶段: **{stage_for_level(p.level)}**\n-------------------\n❤️ 快乐度: {'🟩'*int(p.happiness/10)}{'🟥'*(10-int(p.happiness/10))} [{int(p.happiness)}%]\n🍖 饥饿度: {'🟥'*int(p.hunger/10)}{'🟩'*(10-int(p.hunger/10))} [{int(p.hunger)}%]\n🧼 清洁度: {'🟥'*int(p.cleanliness/10)}{'🟩'*(10-int(p.cleanliness/10))} [{int(p.cleanliness)}%]\n\n**心情描述**\n{mood}{extra}")
            if ctx.config.get("show_pet_image", True):
                try:
                    event_img = _event_image_name(event_text)
                    img = base_dir / (event_img or _status_image_name(p))
                    await _send_photo_and_autodelete(client, message.chat.id, img, st)
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    return
                except Exception as e:
                    ctx.log.warning(f"[电子宠物] 发送状态图片失败，回退文字: {e!r}")
            await _edit(message, st)

        async def do_profile():
            uid = message.from_user.id
            p = get_and_update_pet(uid)
            if not p:
                return await _edit(message, "你还没有领养宠物呢！快使用 /领养 [名字] 来领养一只吧。")
            save_pet(uid, p)
            text_out = (f"**宠物成长档案**\n\n名字: **{p.name}**\n物种: {p.species}\n等级: **{p.level}**\nXP: {int(p.xp)}/{p.level*100}\n成长阶段: **{stage_for_level(p.level)}**\n\n**成长特性**\n"
                        f"- 电子狗：更稳定更活泼\n- 像素猫：更优雅但更容易变脏\n- 机械龙：更偏能量成长型")
            try:
                img = base_dir / _evolution_image_name(p)
                await _send_photo_and_autodelete(client, message.chat.id, img, text_out)
                try:
                    await message.delete()
                except Exception:
                    pass
            except Exception:
                await _edit(message, text_out)

        async def do_inventory():
            uid = message.from_user.id
            p = get_and_update_pet(uid)
            if not p:
                return await _edit(message, "你还没有领养宠物呢！快使用 /领养 [名字] 来领养一只吧。")
            save_pet(uid, p)
            await _edit(message, f"**{p.name} 的背包**\n\n{_inventory_text(p)}")

        async def do_use_item():
            uid = message.from_user.id
            remain = _check_cd(uid, '使用')
            if remain > 0:
                return await _edit(message, f"⏳ 使用道具冷却中，还需等待 {remain} 秒。")
            _set_cd(uid, '使用')
            p = get_and_update_pet(uid)
            if not p:
                return await _edit(message, "你还没有领养宠物呢！快使用 /领养 [名字] 来领养一只吧。")
            parts = text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return await _edit(message, "请指定要使用的道具，例如：/使用 零食")
            item = parts[1].strip()
            if p.inventory.get(item, 0) <= 0:
                return await _edit(message, f"背包里没有【{item}】。")
            p.inventory[item] -= 1
            if item == '零食':
                p.hunger = max(0, p.hunger - 20)
                p.happiness = min(100, p.happiness + 4)
                msg = f"🍪 你给 {p.name} 吃了零食，它看起来满足多了。"
            elif item == '玩具球':
                p.happiness = min(100, p.happiness + 18)
                p.hunger = min(100, p.hunger + 6)
                msg = f"⚽ 你拿出玩具球陪 {p.name} 玩了一会儿，它开心得不行。"
            elif item == '泡泡浴球':
                p.cleanliness = max(0, p.cleanliness - 28)
                p.happiness = min(100, p.happiness + 6)
                msg = f"🛁 你给 {p.name} 用了泡泡浴球，它现在香喷喷的。"
            elif item == '能量核心':
                p.xp += 20
                msg = f"🔋 你为 {p.name} 装上了能量核心，经验明显提升了。"
            else:
                msg = f"你使用了【{item}】，不过好像没什么特别的反应。"
            save_pet(uid, p)
            await _edit(message, f"{msg}\n\n剩余【{item}】× {p.inventory.get(item, 0)}")

        async def do_interact(action):
            uid = message.from_user.id
            remain = _check_cd(uid, {'feed':'喂食','play':'玩耍','clean':'清洁'}.get(action, action))
            if remain > 0:
                return await _edit(message, f"⏳ 指令冷却中，还需等待 {remain} 秒。")
            _set_cd(uid, {'feed':'喂食','play':'玩耍','clean':'清洁'}.get(action, action))
            p = get_and_update_pet(uid)
            if not p:
                return await _edit(message, "你要和谁互动呀？先用 /领养 [名字] 领养一只宠物吧。")
            reply_text, xp_gain = "", 0
            if action == 'feed':
                change = random.randint(25, 40)
                p.hunger = max(0, p.hunger - change)
                p.happiness = min(100, p.happiness + 5)
                xp_gain = 10
                reply_text = f"你喂了 {p.name} 一些好吃的，它满足地打了个嗝。"
            elif action == 'play':
                if p.hunger > 80:
                    return await _edit(message, f"{p.name} 饿得没力气玩了，先喂喂它吧！")
                change = random.randint(20, 35)
                p.happiness = min(100, p.happiness + change)
                p.hunger = min(100, p.hunger + 10)
                xp_gain = 15
                reply_text = f"你和 {p.name} 玩了一会儿球，它看起来开心极了！"
            elif action == 'clean':
                change = random.randint(30, 50)
                p.cleanliness = max(0, p.cleanliness - change)
                p.happiness = min(100, p.happiness + 10)
                xp_gain = 5
                reply_text = f"你给 {p.name} 洗了个澡，它现在香喷喷的！"
            p.xp += xp_gain
            event_text = _maybe_random_event(p)
            extra = f"\n\n**突发事件**\n{event_text}" if event_text else ""
            preferred = _event_image_name(event_text) or _action_image_name(p, action)
            if preferred:
                try:
                    await _send_photo_and_autodelete(client, message.chat.id, base_dir / preferred, f"{reply_text} (XP +{xp_gain}){extra}")
                    try:
                        await message.delete()
                    except Exception:
                        pass
                except Exception:
                    await _edit(message, f"{reply_text} (XP +{xp_gain}){extra}")
            else:
                await _edit(message, f"{reply_text} (XP +{xp_gain}){extra}")
            if p.xp >= p.level * 100:
                p.level += 1
                p.xp = 0
                p.happiness = min(100, p.happiness + 20)
                bonus = _level_bonus_text(p)
                if p.species == '电子狗 🐕':
                    p.happiness = min(100, p.happiness + 8)
                elif p.species == '像素猫 🐈':
                    p.cleanliness = max(0, p.cleanliness - 8)
                elif p.species == '机械龙 🐉':
                    p.xp += 15
                await asyncio.sleep(1)
                await _edit(message, f"🎉 **升级了！** 你的 {p.name} 升到了 **{p.level}** 级！\n**升级奖励**：{bonus}")
            save_pet(uid, p)

        if _is_cmd(text, "/领养", ".领养"):
            return await do_adopt()
        if _is_cmd(text, "/状态", ".状态"):
            return await do_status()
        if _is_cmd(text, "/档案", ".档案"):
            return await do_profile()
        if _is_cmd(text, "/背包", ".背包"):
            return await do_inventory()
        if text.startswith('/使用 ') or text.startswith('.使用 '):
            return await do_use_item()
        if _is_cmd(text, "/喂食", ".喂食"):
            return await do_interact('feed')
        if _is_cmd(text, "/玩耍", ".玩耍"):
            return await do_interact('play')
        if _is_cmd(text, "/清洁", ".清洁"):
            return await do_interact('clean')

    async def pet_heartbeat():
        if not ctx.config.get("auto_reminder_enabled", True):
            return
        owners = get_pet_owners()
        dead = []
        for uid in owners:
            await asyncio.sleep(0.1)
            p = get_and_update_pet(uid)
            if not p:
                continue
            if p.happiness <= 0 and p.hunger >= 100:
                dead.append(uid)
                ctx.kv.delete(f"pet_{uid}")
                try:
                    await ctx.bot.send_message(uid, f"💔 你的宠物 **{p.name}** 因为长期得不到照顾，已经离家出走了...")
                except Exception as e:
                    ctx.log.warning(f"无法向用户 {uid} 发送离家出走通知: {e}")
                continue
            if 80 < p.hunger < 95 and random.random() < 0.5:
                try:
                    await ctx.bot.send_message(uid, f"🥺 你的宠物 **{p.name}** 非常饿了，快给它喂点东西吧！（/喂食）")
                except Exception as e:
                    ctx.log.warning(f"无法向用户 {uid} 发送饥饿提醒: {e}")
            if ctx.config.get('daily_brief_enabled', True):
                try:
                    chance = int(ctx.config.get('daily_brief_chance_percent', 20) or 20)
                except (TypeError, ValueError):
                    chance = 20
                chance = max(0, min(100, chance))
                if random.randint(1, 100) <= chance:
                    brief = _mood_line(p)
                    try:
                        await ctx.bot.send_message(uid, f"📮 **{p.name} 的近况播报**\n{brief}\n\n当前：快乐 {int(p.happiness)} / 饥饿 {int(p.hunger)} / 清洁 {int(p.cleanliness)}")
                    except Exception as e:
                        ctx.log.warning(f"无法向用户 {uid} 发送周期播报: {e}")
            save_pet(uid, p)
        if dead:
            owners = [i for i in get_pet_owners() if i not in dead]
            ctx.kv.set("pet_owners_list", json.dumps(owners))

    try:
        interval = int(ctx.config.get("heartbeat_interval_min", 60) or 60)
    except (ValueError, TypeError):
        interval = 60
    interval = max(10, min(interval, 360))
    if interval < 60:
        ctx.schedule(pet_heartbeat, "cron", minute=f"*/{interval}", id="电子宠物心跳")
    elif interval == 60:
        ctx.schedule(pet_heartbeat, "cron", minute="0", id="电子宠物心跳")
    else:
        hours = max(1, interval // 60)
        ctx.schedule(pet_heartbeat, "cron", hour=f"*/{hours}", minute="0", id="电子宠物心跳")


async def teardown(ctx):
    ctx.log.info("电子宠物插件正在卸载...")
