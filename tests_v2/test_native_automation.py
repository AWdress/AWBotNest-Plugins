from __future__ import annotations
import unittest
from types import SimpleNamespace
from plugins_v2.custom_auto_reply import core

class Log:
    def __getattr__(self,name):return lambda *a,**k:None
class Client:
    def __init__(self):self.sent=[]
    async def get_entity(self,target):return SimpleNamespace(title=f"群{target}",username=None)
    async def get_me(self):return SimpleNamespace(id=1,first_name="账号",username="user")
    async def send_message(self,target,text):self.sent.append((target,text));return SimpleNamespace(id=9)
class Context:
    def __init__(self):
        self.config={"target_chat_id":[{"chat":"-1001","time":"15m","content":"间隔"},{"chat":"@daily","time":"09:30","content":"每天"},{"chat":"-1002","time":"0 9 * * 1-5","content":"工作日"}],"notify_owner":False};self.users=[Client()];self.log=Log();self.intervals=[];self.crons=[];self.updated={}
    def update_config(self,value):self.updated.update(value)
    def schedule_interval(self,name,callback,*,seconds):self.intervals.append((name,callback,seconds))
    def schedule_cron(self,name,callback,**fields):self.crons.append((name,callback,fields))

class NativeAutomationTests(unittest.IsolatedAsyncioTestCase):
    async def test_custom_auto_reply_native_schedules_and_action(self):
        ctx=Context();await core.setup(ctx)
        self.assertEqual(ctx.intervals[0][2],900)
        self.assertEqual(ctx.crons[0][2],{"hour":9,"minute":30})
        self.assertEqual(ctx.crons[1][2],{"minute":"0","hour":"9","day":"*","month":"*","day_of_week":"1-5"})
        await ctx.intervals[0][1]();self.assertEqual(ctx.users[0].sent,[(-1001,"间隔")])
        self.assertIn("群-1001",ctx.updated.get("resolved_chat_names",""))

if __name__=="__main__":unittest.main()
