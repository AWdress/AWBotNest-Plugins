from __future__ import annotations
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace

import plugins_v2.id as id_plugin
import plugins_v2.auto_avatar as auto_avatar
import plugins_v2.msg_forward as msg_forward
import plugins_v2.self_delete as self_delete
import plugins_v2.zf as zf
import plugins_v2.xjj as xjj
import plugins_v2.zpr as zpr
import plugins_v2.trans115search as trans115search
import plugins_v2.hdhive_lottery as hdhive_lottery

class Log:
    def __getattr__(self,name):return lambda *a,**k:None

class Context:
    def __init__(self,config=None):self.config=config or {};self.handlers=[];self.log=Log();self.tasks=[]
    def on_message(self,**kwargs):
        def register(callback):self.handlers.append(callback);return callback
        return register
    def create_task(self,value,**kwargs):self.tasks.append(value);value.close()

class Message:
    def __init__(self,mid=1,text="",sender_id=7):self.id=mid;self.raw_text=text;self.sender_id=sender_id;self.media=None;self.reply_to_msg_id=None;self.deleted=False
    async def get_sender(self):return SimpleNamespace(id=self.sender_id,username="tester",first_name="测试")
    async def delete(self):self.deleted=True

class Event(Message):
    def __init__(self,text,client,reply=None):super().__init__(99,text);self.client=client;self.chat_id=-1001;self._reply=reply;self.edits=[];self.replies=[]
    async def get_reply_message(self):return self._reply
    async def reply(self,text):result=Message(100,text);self.replies.append(text);return result
    async def edit(self,text):self.edits.append(text)

class Client:
    def __init__(self):self.deleted=[];self.forwarded=[];self.sent=[]
    async def get_me(self):return SimpleNamespace(id=7)
    async def iter_messages(self,*args,**kwargs):
        for item in (Message(99,sender_id=7),Message(3,sender_id=7),Message(2,sender_id=8),Message(1,sender_id=7)):yield item
    async def delete_messages(self,chat,ids):self.deleted.extend(ids)
    async def forward_messages(self,chat,message):self.forwarded.append((chat,message.id))
    async def send_message(self,chat,text,reply_to=None):self.sent.append((chat,text,reply_to))

class NativeMessageToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_auto_avatar_uploads_and_checkpoints_photo(self):
        class Storage:
            def __init__(self):self.values={}
            async def get(self,key,default=None):return self.values.get(key,default)
            async def set(self,key,value):self.values[key]=value
        class AvatarClient:
            async def get_me(self):return SimpleNamespace(id=7,username="tester")
            async def get_profile_photos(self,*args,**kwargs):return []
            async def upload_file(self,path):return "uploaded"
            async def __call__(self,request):return SimpleNamespace(photo=SimpleNamespace(id=123))
        with tempfile.TemporaryDirectory() as folder:
            context=SimpleNamespace(data_dir=Path(folder),storage=Storage(),config={"delete_old":True},log=Log())
            pool=auto_avatar._pool(context,"tester");(pool/"a.jpg").write_bytes(b"image")
            self.assertTrue(await auto_avatar._change(context,AvatarClient()))
            self.assertEqual(context.storage.values["last_photo:tester"],"123")

    async def test_id_reply_uses_native_sender(self):
        ctx=Context({"auto_delete":0,"delete_command":True});await id_plugin.setup(ctx)
        event=Event(".id",Client(),Message(8,sender_id=42));await ctx.handlers[0](event)
        self.assertIn("用户ID: `42`",event.replies[0]);self.assertTrue(event.deleted)

    async def test_self_delete_filters_current_account(self):
        ctx=Context({"tip_seconds":0});await self_delete.setup(ctx);client=Client();event=Event(".dme 2",client)
        await ctx.handlers[0](event);self.assertEqual(client.deleted,[3,1]);self.assertTrue(event.deleted)

    async def test_forward_repeat_count(self):
        ctx=Context({"interval":0,"max_times":5});await zf.setup(ctx);client=Client();event=Event(".zf 3",client,Message(4,"hello"))
        await ctx.handlers[0](event);self.assertEqual(len(client.forwarded),3);self.assertTrue(event.deleted)

    async def test_message_forward_native_filters(self):
        sender=SimpleNamespace(id=42,username="relaybot",bot=True)
        message=SimpleNamespace(raw_text="资源 https://example.org",media=None,photo=None,video=None,gif=None,document=None,audio=None,voice=None)
        rule={"types":["link"],"kw":"资源","nkw":"广告","sender":"bot,@other"}
        self.assertTrue(msg_forward._passes(rule,[message],message.raw_text,sender))
        self.assertFalse(msg_forward._passes({**rule,"nkw":"资源"},[message],message.raw_text,sender))
        self.assertEqual(msg_forward._peer("-100123"),-100123)
        self.assertEqual(msg_forward._peer("@channel"),"@channel")

    async def test_message_forward_media_download_none_falls_back_to_forward(self):
        class CopyClient:
            def __init__(self): self.forwarded=[]; self.files=[]
            async def download_media(self,*args,**kwargs): return None
            async def forward_messages(self,target,messages): self.forwarded.append((target,messages))
            async def send_file(self,*args,**kwargs): self.files.append((args,kwargs))
        client=CopyClient(); message=SimpleNamespace(raw_text="图片说明",media=object())
        await msg_forward._copy(client,-1002,[message])
        self.assertEqual(len(client.forwarded),1)
        self.assertFalse(client.files)

    async def test_xjj_extracts_nested_video_url(self):
        class Response:
            def raise_for_status(self):pass
            def json(self):return {"data":{"url":"//cdn.example/video.mp4"}}
        class Http:
            async def get(self,*args,**kwargs):return Response()
        self.assertEqual(await xjj._url(SimpleNamespace(http=Http()),"https://api.example","url",10),"https://cdn.example/video.mp4")

    async def test_media_command_parsers(self):
        self.assertFalse(zpr._command("/zpr 风景 2 0"))
        self.assertTrue(zpr._command(".zp 风景 2 0"))
        self.assertEqual(zpr._args("/zpr 风景 2 1"),("风景",2,1))
        self.assertEqual(trans115search._peer("-1002466900287"),-1002466900287)
        lottery=hdhive_lottery._parse("发起了一个抽奖\n🏆 奖励：100魔力\n🔑 参与口令：\n好运来\n⏰ 结束")
        self.assertEqual(lottery,{"prize":"100魔力","keyword":"好运来"})

if __name__=="__main__":unittest.main()
