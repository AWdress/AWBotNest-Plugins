# -----------------------------------------------------------------------------
# digital_pet/__init__.py - 电子宠物插件 V1.0
# -----------------------------------------------------------------------------

import time
import random
import json
import asyncio
from dataclasses import dataclass, asdict, field

# 插件元数据
__plugin__ = {
    "name": "电子宠物",
    "id": "digital_pet",
    "version": "1.1.0",
    "author": "AWdress & Hermes",
    "scope": "user",
    "description": "在 Telegram 养成你的专属电子宠物！支持喂食、玩耍、成长和进化。",
    "requirements": [], # V1 无需额外依赖
}

# -----------------------------------------------------------------------------
# 1. 宠物数据结构定义 (Pet Dataclass)
# -----------------------------------------------------------------------------

@dataclass
class Pet:
    """定义了宠物的全部属性"""
    user_id: int
    name: str
    species: str
    level: int = 1
    xp: int = 0
    hunger: float = 20.0
    happiness: float = 80.0
    cleanliness: float = 10.0
    # 使用 field 工厂函数确保每次创建实例时都获取当前时间
    last_update_ts: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        # 兼容旧数据，防止缺少字段
        data.pop('last_update_ts', None) 
        return cls(**data)


# -----------------------------------------------------------------------------
# 2. 核心逻辑与插件入口 (setup function)
# -----------------------------------------------------------------------------

async def setup(ctx):
    """插件的主入口，所有逻辑都在这里注册"""

    # --- 2.1 辅助函数 (Helpers) ---

    async def get_pet_owners() -> list[int]:
        """获取所有养了宠物的用户ID列表"""
        owners_json = await ctx.kv.get("pet_owners_list")
        if not owners_json:
            return []
        try:
            return json.loads(owners_json)
        except (json.JSONDecodeError, TypeError):
            ctx.log.warning("宠物主人列表数据损坏，已重置。")
            await ctx.kv.delete("pet_owners_list")
            return []

    async def add_pet_owner(user_id: int):
        """添加一个新的宠物主人"""
        owners = await get_pet_owners()
        if user_id not in owners:
            owners.append(user_id)
            await ctx.kv.set("pet_owners_list", json.dumps(owners))
    
    async def remove_pet_owner(user_id: int):
        """移除一个宠物主人"""
        owners = await get_pet_owners()
        if user_id in owners:
            owners.remove(user_id)
            await ctx.kv.set("pet_owners_list", json.dumps(owners))

    def update_pet_state(pet: Pet) -> Pet:
        """
        【核心】根据时间流逝，计算宠物状态的自然变化。
        这个函数只计算，不保存。
        """
        now = int(time.time())
        elapsed_hours = (now - pet.last_update_ts) / 3600.0
        
        # 每小时状态变化率
        hunger_rate = 5
        happiness_rate = 3
        cleanliness_rate = 2

        pet.hunger = min(100, pet.hunger + hunger_rate * elapsed_hours)
        pet.happiness = max(0, pet.happiness - happiness_rate * elapsed_hours)
        pet.cleanliness = min(100, pet.cleanliness + cleanliness_rate * elapsed_hours)
        
        pet.last_update_ts = now
        return pet

    async def get_and_update_pet(user_id: int) -> Pet | None:
        """获取宠物信息，并立即更新其状态"""
        pet_data = await ctx.kv.get(f"pet_{user_id}")
        if not pet_data:
            return None
        
        try:
            pet = Pet.from_dict(json.loads(pet_data))
            return update_pet_state(pet)
        except (json.JSONDecodeError, TypeError):
            ctx.log.warning(f"用户 {user_id} 的宠物数据损坏，已忽略。")
            return None
    
    async def save_pet(user_id: int, pet: Pet):
        """保存宠物状态到数据库"""
        await ctx.kv.set(f"pet_{user_id}", json.dumps(pet.to_dict()))

    # --- 2.2 用户交互指令 (Commands) ---

    @ctx.on_message(ctx.filters.command("adopt", prefixes="/."))
    async def handle_adopt(client, message):
        user_id = message.from_user.id
        if await get_and_update_pet(user_id):
            await message.reply("你已经有一只宠物了！使用 /status 查看它吧。")
            return

        pet_name = message.command[1] if len(message.command) > 1 else "小可爱"
        species = random.choice(["电子狗 🐕", "像素猫 🐈", "机械龙 🐉"])
        
        new_pet = Pet(user_id=user_id, name=pet_name, species=species)
        await save_pet(user_id, new_pet)
        await add_pet_owner(user_id) # 注册到主人列表

        await message.reply(
            f"🎉 恭喜！你领养了一只叫做 **{new_pet.name}** 的{new_pet.species}！\n"
            "快来和它互动吧：\n"
            "/status - 查看状态\n"
            "/feed - 喂食\n"
            "/play - 玩耍\n"
            "/clean - 清洁"
        )

    @ctx.on_message(ctx.filters.command("status", prefixes="/."))
    async def handle_status(client, message):
        user_id = message.from_user.id
        
        # 发送一个“正在加载”的提示，提升体验
        loading_message = await message.reply("正在生成宠物状态图，请稍候...")

        pet = await get_and_update_pet(user_id)

        if not pet:
            await loading_message.edit("你还没有领养宠物呢！快使用 /adopt [名字] 来领养一只吧。")
            return
        
        await save_pet(user_id, pet) # 保存更新后的状态

        # --- 动态生成 Prompt ---
        mood = "happy"
        if pet.happiness < 30 or pet.hunger > 70:
            mood = "sad"
        if pet.happiness < 10 or pet.hunger > 90:
            mood = "crying"
        
        # 移除物种中的 emoji
        species_clean = pet.species.split(" ")[0]
        
        prompt = (
            f"a cute {species_clean}, digital pet, pixel art, {mood} expression, "
            f"simple white background, 8-bit, nostalgic, tamagotchi style"
        )

        # --- 生成图片 ---
        image_url = None
        # 假设平台提供了 ctx.generate_image, 如果没有，则会 gracefully fallback
        if hasattr(ctx, 'generate_image') and callable(ctx.generate_image):
            try:
                # 增加超时以防万一
                image_url = await asyncio.wait_for(ctx.generate_image(prompt), timeout=60)
            except (asyncio.TimeoutError, Exception) as e:
                ctx.log.warning(f"宠物图片生成失败: {e}")
        else:
            ctx.log.info("ctx.generate_image 不可用，跳过图片生成。")


        # --- 组合并发送最终消息 ---
        status_text = (
            f"名字: **{pet.name}**\n"
            f"物种: {pet.species}\n"
            f"等级: **{pet.level}** (XP: {int(pet.xp)}/{pet.level * 100})\n"
            "-------------------\n"
            f"❤️ 快乐度: {'🟩' * int(pet.happiness/10)}{'🟥' * (10 - int(pet.happiness/10))} [{int(pet.happiness)}%]\n"
            f"🍖 饥饿度: {'🟥' * int(pet.hunger/10)}{'🟩' * (10 - int(pet.hunger/10))} [{int(pet.hunger)}%]\n"
            f"🧼 清洁度: {'🟥' * int(pet.cleanliness/10)}{'🟩' * (10 - int(pet.cleanliness/10))} [{int(pet.cleanliness)}%]"
        )

        if image_url:
            # 如果有图片，图文一起发送
            await client.send_photo(
                chat_id=message.chat.id,
                photo=image_url,
                caption=status_text
            )
            await loading_message.delete() # 删除“正在加载”提示
        else:
            # 如果没有图片，编辑原消息
            await loading_message.edit(f"**宠物状态**\n\n{status_text}")

    async def interact(message, action: str):
        user_id = message.from_user.id
        pet = await get_and_update_pet(user_id)

        if not pet:
            await message.reply("你要和谁互动呀？先用 /adopt 领养一只宠物吧。")
            return
        
        reply_text = ""
        xp_gain = 0

        if action == "feed":
            change = random.randint(25, 40)
            pet.hunger = max(0, pet.hunger - change)
            pet.happiness = min(100, pet.happiness + 5)
            xp_gain = 10
            reply_text = f"你喂了 {pet.name} 一些好吃的，它满足地打了个嗝。"
        
        elif action == "play":
            if pet.hunger > 80:
                await message.reply(f"{pet.name} 饿得没力气玩了，先喂喂它吧！")
                return
            change = random.randint(20, 35)
            pet.happiness = min(100, pet.happiness + change)
            pet.hunger = min(100, pet.hunger + 10)
            xp_gain = 15
            reply_text = f"你和 {pet.name} 玩了一会儿球，它看起来开心极了！"
        
        elif action == "clean":
            change = random.randint(30, 50)
            pet.cleanliness = max(0, pet.cleanliness - change)
            pet.happiness = min(100, pet.happiness + 10)
            xp_gain = 5
            reply_text = f"你给 {pet.name} 洗了个澡，它现在香喷喷的！"
        
        pet.xp += xp_gain
        await message.reply(f"{reply_text} (XP +{xp_gain})")

        # 检查是否升级
        if pet.xp >= pet.level * 100:
            pet.level += 1
            pet.xp = 0
            # 升级后属性略微提升
            pet.happiness = min(100, pet.happiness + 20)
            await message.reply(f"🎉 **升级了！** 你的 {pet.name} 升到了 **{pet.level}** 级！")

        await save_pet(user_id, pet)

    @ctx.on_message(ctx.filters.command("feed", prefixes="/."))
    async def handle_feed(client, message):
        await interact(message, "feed")

    @ctx.on_message(ctx.filters.command("play", prefixes="/."))
    async def handle_play(client, message):
        await interact(message, "play")

    @ctx.on_message(ctx.filters.command("clean", prefixes="/."))
    async def handle_clean(client, message):
        await interact(message, "clean")


    # --- 2.3 后台心跳任务 (Heartbeat Task) ---

    async def pet_heartbeat():
        ctx.log.info("执行电子宠物心跳任务...")
        owners = await get_pet_owners()
        dead_pets_owners = []

        for user_id in owners:
            # 使用 asyncio.sleep(0.1) 防止长时间循环阻塞平台
            await asyncio.sleep(0.1) 
            
            pet = await get_and_update_pet(user_id)
            if not pet:
                continue

            # 离家出走逻辑
            if pet.happiness <= 0 and pet.hunger >= 100:
                dead_pets_owners.append(user_id)
                await ctx.kv.delete(f"pet_{user_id}")
                await ctx.notify(
                    user_id,
                    f"💔 你的宠物 **{pet.name}** 因为长期得不到照顾，已经离家出走了...",
                    level="warning"
                )
                continue
            
            # 状态告警逻辑
            if 80 < pet.hunger < 95 and random.random() < 0.5: # 50%概率提醒
                 await ctx.notify(
                    user_id,
                    f"🥺 你的宠物 **{pet.name}** 非常饿了，快给它喂点东西吧！ (/feed)",
                    level="info"
                )
            
            await save_pet(user_id, pet)
        
        # 清理已“死亡”的宠物主人
        if dead_pets_owners:
            ctx.log.info(f"清理 {len(dead_pets_owners)} 只离家出走的宠物。")
            current_owners = await get_pet_owners()
            updated_owners = [uid for uid in current_owners if uid not in dead_pets_owners]
            await ctx.kv.set("pet_owners_list", json.dumps(updated_owners))
        
        ctx.log.info("电子宠物心跳任务完成。")
    
    # 在 setup 的末尾正确注册定时任务
    ctx.schedule(pet_heartbeat, hour="*/1")
