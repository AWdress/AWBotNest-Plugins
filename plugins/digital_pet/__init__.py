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
    "version": "1.5.4",
    "author": "AWdress",
    "scope": "user",
    "description": "在 Telegram 养成你的专属电子宠物！支持领养、喂食、玩耍、清洁、成长和定时状态提醒。",
    "icon": "https://raw.githubusercontent.com/AWdress/AWBotNest-Plugins/main/plugins/digital_pet/logo.png",
    "changelog": "v1.5.4 增加回复消息自动删除功能\n- 所有插件回复都改为发出后按配置延时自动删除\n- 新增“自动删除插件回复”开关和“回复消息保留时间”配置项",
    "requirements": [],
    "default_enabled": False,
    "config_schema": {
        "auto_reminder_enabled": {"type": "boolean","default": True,"label": "启用自动提醒","section": "运行设置",},
        "heartbeat_interval_min": {"type": "slider","default": 60,"label": "状态检查间隔（分钟）","min": 10,"max": 360,"step": 10,"section": "运行设置",},
        "decay_multiplier": {"type": "slider","default": 100,"label": "状态衰减倍率（%）","min": 50,"max": 300,"step": 10,"section": "运行设置",},
        "auto_delete_replies": {"type": "boolean","default": True,"label": "自动删除插件回复","section": "消息清理",},
        "delete_delay_seconds": {"type": "slider","default": 30,"label": "回复消息保留时间（秒）","min": 5,"max": 300,"step": 5,"section": "消息清理",},
        "adopt_command": {"type": "string","default": "/adopt","label": "领养命令","section": "命令说明",},
        "info": {"type": "info","label": "玩法说明","section": "命令说明","text": "先发送 /adopt 名字 领养宠物，再用 /status、/feed、/play、/clean 与它互动。改动检查间隔后建议重载插件生效。"}
    },
}

@dataclass
class Pet:
    user_id: int; name: str; species: str; level: int = 1; xp: int = 0; hunger: float = 20.0; happiness: float = 80.0; cleanliness: float = 10.0; last_update_ts: int = 0
    def __post_init__(self):
        if self.last_update_ts == 0: self.last_update_ts = int(time.time())
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data):
        return cls(user_id=data.get("user_id",0),name=data.get("name","未命名"),species=data.get("species","未知"),level=data.get("level",1),xp=data.get("xp",0),hunger=data.get("hunger",20.0),happiness=data.get("happiness",80.0),cleanliness=data.get("cleanliness",10.0),last_update_ts=data.get("last_update_ts",int(time.time())))

async def setup(ctx):
    def get_pet_owners():
        d=ctx.kv.get("pet_owners_list");
        if not d: return []
        try: return json.loads(d)
        except (json.JSONDecodeError,TypeError) as e: ctx.log.warning(f"宠物主人列表数据损坏: {e}"); ctx.kv.delete("pet_owners_list"); return []
    def add_pet_owner(uid): o=get_pet_owners(); o.append(uid) if uid not in o else None; ctx.kv.set("pet_owners_list",json.dumps(o))
    def update_pet_state(p:Pet)->Pet:
        n,eh=int(time.time()),(int(time.time())-p.last_update_ts)/3600.0; eh=max(0,eh)
        try: m=float(ctx.config.get("decay_multiplier",100) or 100)/100.0
        except(ValueError,TypeError): m=1.0
        m=max(0.5,min(m,3.0)); hr,happyr,cr=5*m,3*m,2*m; p.hunger=min(100,p.hunger+hr*eh); p.happiness=max(0,p.happiness-happyr*eh); p.cleanliness=min(100,p.cleanliness+cr*eh); p.last_update_ts=n; return p
    def get_and_update_pet(uid):
        d=ctx.kv.get(f"pet_{uid}");
        if not d: return None
        try: p=Pet.from_dict(json.loads(d)); return update_pet_state(p)
        except(json.JSONDecodeError,TypeError,ValueError)as e: ctx.log.warning(f"用户 {uid} 的宠物数据损坏: {e}"); return None
    def save_pet(uid,p:Pet): ctx.kv.set(f"pet_{uid}",json.dumps(p.to_dict()))
    def _b(c,f): return(c or "").lstrip("/.").strip().lower() or f
    def _m(t,b): h=t.split(maxsplit=1)[0].lower() if t else ""; return h in(f"/{b}",f".{b}")

    async def _edit(m,t):
        try:
            m=await m.edit(t)
            if ctx.config.get("auto_delete_replies",True):
                d=int(ctx.config.get("delete_delay_seconds",30)or 30)
                await asyncio.sleep(d); await m.delete()
        except Exception as e: ctx.log.debug(f"[电子宠物] 自动删除消息失败: {e!r}")

    @ctx.on_message(ctx.filters.outgoing&ctx.filters.text,group=-12)
    async def pet_commands(c,m):
        t=m.text or ""; ab=_b(ctx.config.get("adopt_command","/adopt"),"adopt")
        async def do_adopt():
            uid=m.from_user.id
            if get_and_update_pet(uid):return await _edit(m,"你已经有一只宠物了！使用 /status 查看它吧。")
            parts=t.split(maxsplit=1); name=parts[1].strip() if len(parts)>1 and parts[1].strip() else"小可爱"; sp=random.choice(["电子狗 🐕","像素猫 🐈","机械龙 🐉"]); p=Pet(user_id=uid,name=name,species=sp); save_pet(uid,p); add_pet_owner(uid)
            await _edit(m,f"🎉 恭喜！你领养了一只叫做 **{p.name}** 的{p.species}！\n快来和它互动吧：\n/status - 查看状态\n/feed - 喂食\n/play - 玩耍\n/clean - 清洁")
        async def do_status():
            uid=m.from_user.id; p=get_and_update_pet(uid)
            if not p:return await _edit(m,"你还没有领养宠物呢！快使用 /adopt [名字] 来领养一只吧。")
            save_pet(uid,p); me="😊";
            if p.happiness<30 or p.hunger>70:me="😟"
            if p.happiness<10 or p.hunger>90:me="😭"
            st=(f"**宠物状态** {me}\n\n名字: **{p.name}**\n物种: {p.species}\n等级: **{p.level}** (XP: {int(p.xp)}/{p.level*100})\n-------------------\n❤️ 快乐度: {'🟩'*int(p.happiness/10)}{'🟥'*(10-int(p.happiness/10))} [{int(p.happiness)}%]\n🍖 饥饿度: {'🟥'*int(p.hunger/10)}{'🟩'*(10-int(p.hunger/10))} [{int(p.hunger)}%]\n🧼 清洁度: {'🟥'*int(p.cleanliness/10)}{'🟩'*(10-int(p.cleanliness/10))} [{int(p.cleanliness)}%]")
            await _edit(m,st)
        async def do_interact(a):
            uid=m.from_user.id;p=get_and_update_pet(uid)
            if not p:return await _edit(m,"你要和谁互动呀？先用 /adopt 领养一只宠物吧。")
            rt,xg="",0
            if a=="feed":c=random.randint(25,40); p.hunger=max(0,p.hunger-c); p.happiness=min(100,p.happiness+5); xg,rt=10,f"你喂了 {p.name} 一些好吃的，它满足地打了个嗝。"
            elif a=="play":
                if p.hunger>80:return await _edit(m,f"{p.name} 饿得没力气玩了，先喂喂它吧！")
                c=random.randint(20,35); p.happiness=min(100,p.happiness+c); p.hunger=min(100,p.hunger+10); xg,rt=15,f"你和 {p.name} 玩了一会儿球，它看起来开心极了！"
            elif a=="clean":c=random.randint(30,50); p.cleanliness=max(0,p.cleanliness-c); p.happiness=min(100,p.happiness+10); xg,rt=5,f"你给 {p.name} 洗了个澡，它现在香喷喷的！"
            p.xp+=xg; await m.edit(f"{rt} (XP +{xg})")
            if p.xp>=p.level*100:p.level+=1;p.xp=0;p.happiness=min(100,p.happiness+20);await asyncio.sleep(1);await _edit(m,f"🎉 **升级了！** 你的 {p.name} 升到了 **{p.level}** 级！")
            save_pet(uid, p)
        if _m(t,ab):return await do_adopt()
        if _m(t,"status"):return await do_status()
        if _m(t,"feed"):return await do_interact("feed")
        if _m(t,"play"):return await do_interact("play")
        if _m(t,"clean"):return await do_interact("clean")

    async def pet_heartbeat():
        if not ctx.config.get("auto_reminder_enabled",True):return
        owners=get_pet_owners(); dead=[]
        for uid in owners:
            await asyncio.sleep(0.1); p=get_and_update_pet(uid)
            if not p:continue
            if p.happiness<=0 and p.hunger>=100:
                dead.append(uid);ctx.kv.delete(f"pet_{uid}")
                try:await ctx.bot.send_message(uid,f"💔 你的宠物 **{p.name}** 因为长期得不到照顾，已经离家出走了...")
                except Exception as e:ctx.log.warning(f"无法向用户 {uid} 发送离家出走通知: {e}")
                continue
            if 80<p.hunger<95 and random.random()<0.5:
                try:await ctx.bot.send_message(uid,f"🥺 你的宠物 **{p.name}** 非常饿了，快给它喂点东西吧！ (/feed)")
                except Exception as e:ctx.log.warning(f"无法向用户 {uid} 发送饥饿提醒: {e}")
            save_pet(uid,p)
        if dead:o=get_pet_owners();u=[i for i in o if i not in dead];ctx.kv.set("pet_owners_list",json.dumps(u))
    try:i=int(ctx.config.get("heartbeat_interval_min",60)or 60)
    except(ValueError,TypeError):i=60
    i=max(10,min(i,360))
    if i<60:ctx.schedule(pet_heartbeat,"cron",minute=f"*/{i}",id="电子宠物心跳")
    elif i==60:ctx.schedule(pet_heartbeat,"cron",minute="0",id="电子宠物心跳")
    else:h=max(1,i//60);ctx.schedule(pet_heartbeat,"cron",hour=f"*/{h}",minute="0",id="电子宠物心跳")
async def teardown(ctx):ctx.log.info("电子宠物插件正在卸载...")
