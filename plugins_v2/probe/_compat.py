"""AWBotNest 1 plugin API -> AWBotNest 2 Telethon bridge.

This file is copied into every generated V2 package so marketplace installs remain
self-contained.  It deliberately translates registration/lifecycle primitives;
plugins continue to own their business logic and data namespace.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


class ParseMode:
    HTML = 'html'
    MARKDOWN = 'markdown'


class InlineKeyboardButton:
    def __init__(self, text, callback_data=None, url=None):
        self.text, self.callback_data, self.url = text, callback_data, url


class InlineKeyboardMarkup:
    def __init__(self, rows):
        try:
            from telethon import Button
            self.rows = [[Button.url(x.text, x.url) if x.url else Button.inline(
                x.text, str(x.callback_data or '').encode()) for x in row] for row in rows]
        except Exception:
            self.rows = rows


class ReplyParameters:
    def __init__(self, message_id, chat_id=None):
        self.message_id, self.chat_id = message_id, chat_id


try:
    from telethon import functions as _tl_functions
    raw = SimpleNamespace(functions=SimpleNamespace(
        messages=SimpleNamespace(
            GetForumTopics=_tl_functions.channels.GetForumTopicsRequest,
            GetForumTopicsByID=_tl_functions.channels.GetForumTopicsByIDRequest,
            ForwardMessages=_tl_functions.messages.ForwardMessagesRequest,
        )
    ))
except Exception:
    raw = SimpleNamespace(functions=SimpleNamespace(messages=SimpleNamespace()))


class Filter:
    def __init__(self, check: Callable[[Any, Any], bool]):
        self.check = check

    def __and__(self, other):
        return Filter(lambda e, m: self.check(e, m) and other.check(e, m))

    def __or__(self, other):
        return Filter(lambda e, m: self.check(e, m) or other.check(e, m))

    def __invert__(self):
        return Filter(lambda e, m: not self.check(e, m))


class Filters:
    text = Filter(lambda e, m: bool(m.text))
    caption = Filter(lambda e, m: bool(m.caption))
    photo = Filter(lambda e, m: bool(m.photo))
    document = Filter(lambda e, m: bool(m.document))
    audio = Filter(lambda e, m: bool(m.audio))
    video = Filter(lambda e, m: bool(m.video))
    voice = Filter(lambda e, m: bool(m.voice))
    sticker = Filter(lambda e, m: bool(m.sticker))
    outgoing = Filter(lambda e, m: bool(m.outgoing))
    incoming = Filter(lambda e, m: not bool(m.outgoing))
    group = Filter(lambda e, m: str(m.chat.type) in {'group', 'supergroup'})
    private = Filter(lambda e, m: str(m.chat.type) == 'private')
    channel = Filter(lambda e, m: str(m.chat.type) == 'channel')
    reply = Filter(lambda e, m: bool(m.reply_to_message_id))
    forward = Filter(lambda e, m: bool(getattr(e.message, 'fwd_from', None)))
    via_bot = Filter(lambda e, m: bool(getattr(e.message, 'via_bot_id', None)))
    bot = Filter(lambda e, m: bool(getattr(m.from_user, 'is_bot', False)))
    me = Filter(lambda e, m: bool(m.outgoing))

    @staticmethod
    def regex(pattern):
        compiled = re.compile(pattern)
        return Filter(lambda e, m: bool(compiled.search(m.text or m.caption or '')))

    @staticmethod
    def command(name):
        return Filters.regex(r'^[/\.]' + re.escape(str(name)) + r'(?:@\w+)?(?:\s|$)')

    @staticmethod
    def chat(value):
        values = {int(x) for x in (value if isinstance(value, (list, tuple, set)) else [value])}
        return Filter(lambda e, m: int(m.chat.id or 0) in values)

    @staticmethod
    def user(value):
        values = {int(x) for x in (value if isinstance(value, (list, tuple, set)) else [value])}
        return Filter(lambda e, m: int(getattr(m.from_user, 'id', 0) or 0) in values)


class Entity:
    def __init__(self, raw=None):
        self._raw = raw
        self.id = int(getattr(raw, 'id', 0) or 0)
        self.first_name = getattr(raw, 'first_name', None)
        self.last_name = getattr(raw, 'last_name', None)
        self.username = getattr(raw, 'username', None)
        self.title = getattr(raw, 'title', None)
        self.is_bot = bool(getattr(raw, 'bot', False))


class Chat(Entity):
    def __init__(self, raw=None):
        super().__init__(raw)
        name = raw.__class__.__name__.lower() if raw is not None else ''
        if 'channel' in name and bool(getattr(raw, 'megagroup', False)):
            self.type = 'supergroup'
        elif 'channel' in name:
            self.type = 'channel'
        elif 'chat' in name:
            self.type = 'group'
        else:
            self.type = 'private'


class Message:
    def __init__(self, event, sender=None, chat=None, reply=None):
        raw = event.message
        self._event, self._raw = event, raw
        self.id = int(getattr(raw, 'id', 0) or 0)
        self.text = getattr(raw, 'message', None) or ''
        self.caption = self.text if getattr(raw, 'media', None) is not None else None
        self.outgoing = bool(getattr(raw, 'out', False))
        self.date = getattr(raw, 'date', None)
        self.edit_date = getattr(raw, 'edit_date', None)
        self.views = getattr(raw, 'views', None)
        self.author_signature = getattr(raw, 'post_author', None)
        self.chat = Chat(chat)
        self.from_user = Entity(sender) if sender is not None else None
        self.sender_chat = None
        self.reply_to_message_id = getattr(raw, 'reply_to_msg_id', None)
        self.reply_to_message = reply
        self.media = getattr(raw, 'media', None)
        self.photo = getattr(raw, 'photo', None)
        self.document = getattr(raw, 'document', None)
        self.audio = self.video = self.voice = self.sticker = self.video_note = None
        document = self.document
        for attr in getattr(document, 'attributes', []) or []:
            kind = attr.__class__.__name__.lower()
            if 'audio' in kind:
                self.voice = document if getattr(attr, 'voice', False) else None
                self.audio = document if not self.voice else None
            if 'video' in kind:
                self.video_note = document if getattr(attr, 'round_message', False) else None
                self.video = document if not self.video_note else None
            if 'sticker' in kind:
                self.sticker = document
        self.entities = getattr(raw, 'entities', None) or []
        self.caption_entities = self.entities
        self.link = None
        self.service = getattr(raw, 'action', None)
        self.via_bot = getattr(raw, 'via_bot_id', None)
        self.media_group_id = getattr(raw, 'grouped_id', None)
        self.message_thread_id = getattr(raw, 'reply_to_top_id', None)

    async def reply(self, text, **kwargs):
        return await self._event.reply(text, **_message_kwargs(kwargs))

    async def edit(self, text, **kwargs):
        return await self._event.edit(text, **_message_kwargs(kwargs))

    edit_text = edit

    async def delete(self, *args, **kwargs):
        return await self._event.delete()

    async def reply_photo(self, photo, caption=None, **kwargs):
        return await self._event.client.send_file(
            self.chat.id, photo, caption=caption, reply_to=self.id, **_message_kwargs(kwargs)
        )

    async def reply_video(self, video, caption=None, **kwargs):
        return await self.reply_photo(video, caption=caption, **kwargs)

    async def click(self, *args, **kwargs):
        return await self._event.click(*args, **kwargs)

    async def copy(self, chat_id, **kwargs):
        if self.media:
            return await self._event.client.send_file(
                chat_id, self.media, caption=self.caption, **_message_kwargs(kwargs)
            )
        return await self._event.client.send_message(chat_id, self.text, **_message_kwargs(kwargs))


class CallbackQuery:
    def __init__(self, event, message, sender=None):
        self._event = event
        self.id = getattr(event, 'query', None).query_id if getattr(event, 'query', None) else 0
        self.data = getattr(event, 'data', b'')
        self.message = message
        self.from_user = Entity(sender) if sender is not None else None

    async def answer(self, text='', show_alert=False, **kwargs):
        return await self._event.answer(text, alert=show_alert)

    async def edit_message_text(self, text, **kwargs):
        return await self._event.edit(text, **_message_kwargs(kwargs))


def _message_kwargs(values):
    out = dict(values)
    aliases = {
        'reply_to_message_id': 'reply_to', 'disable_web_page_preview': 'link_preview',
        'reply_markup': 'buttons',
    }
    for old, new in aliases.items():
        if old in out:
            out[new] = out.pop(old)
    if isinstance(out.get('buttons'), InlineKeyboardMarkup):
        out['buttons'] = out['buttons'].rows
    parameters = out.pop('reply_parameters', None)
    if parameters is not None:
        out['reply_to'] = parameters.message_id
    out.pop('parse_mode', None)
    return out


class Client:
    def __init__(self, raw):
        self.raw = raw
        self.connected = raw is not None
        self.me = None

    async def load_me(self):
        if self.raw is not None and self.me is None:
            self.me = Entity(await self.raw.get_me())
        return self

    def __getattr__(self, name):
        return getattr(self.raw, name)

    async def send_message(self, chat_id, text, **kwargs):
        return await self.raw.send_message(chat_id, text, **_message_kwargs(kwargs))

    async def invoke(self, request):
        return await self.raw(request)

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        return await self.raw.send_file(chat_id, photo, caption=caption, **_message_kwargs(kwargs))

    send_document = send_photo
    send_video = send_photo
    send_audio = send_photo
    send_voice = send_photo
    send_sticker = send_photo

    async def delete_messages(self, chat_id, ids, **kwargs):
        return await self.raw.delete_messages(chat_id, ids)

    async def get_me(self):
        return Entity(await self.raw.get_me())

    async def get_users(self, value):
        return Entity(await self.raw.get_entity(value))

    async def get_chat(self, value):
        return Chat(await self.raw.get_entity(value))

    async def get_chat_member(self, chat_id, user_id):
        participant = await self.raw.get_permissions(chat_id, user_id)
        return SimpleNamespace(
            status='administrator' if getattr(participant, 'is_admin', False) else 'member',
            privileges=participant,
        )

    async def join_chat(self, value):
        from telethon.tl.functions.channels import JoinChannelRequest
        return await self.raw(JoinChannelRequest(value))

    async def resolve_peer(self, value):
        return await self.raw.get_input_entity(value)

    async def edit_message_text(self, chat_id, message_id, text, **kwargs):
        return await self.raw.edit_message(chat_id, message_id, text, **_message_kwargs(kwargs))

    async def get_messages(self, chat_id, message_ids):
        return await self.raw.get_messages(chat_id, ids=message_ids)

    async def get_chat_history(self, chat_id, limit=0, **kwargs):
        async for item in self.raw.iter_messages(chat_id, limit=limit or None, **kwargs):
            yield _plain_message(item, self.raw)

    async def get_dialogs(self, limit=0, **kwargs):
        async for item in self.raw.iter_dialogs(limit=limit or None, **kwargs):
            yield SimpleNamespace(chat=Chat(item.entity), name=item.name)

    async def get_chat_photos(self, chat_id, limit=0, **kwargs):
        async for item in self.raw.iter_profile_photos(chat_id, limit=limit or None, **kwargs):
            yield SimpleNamespace(file_id=item, photo=item)

    async def set_profile_photo(self, photo):
        from telethon.tl.functions.photos import UploadProfilePhotoRequest
        uploaded = await self.raw.upload_file(photo)
        return await self.raw(UploadProfilePhotoRequest(uploaded))

    async def delete_profile_photos(self, photo):
        from telethon.tl.functions.photos import DeletePhotosRequest
        return await self.raw(DeletePhotosRequest([photo]))

    async def forward_messages(self, chat_id, from_chat_id, message_ids, **kwargs):
        return await self.raw.forward_messages(chat_id, message_ids, from_peer=from_chat_id)

    async def copy_message(self, chat_id, from_chat_id, message_id, **kwargs):
        source = await self.raw.get_messages(from_chat_id, ids=message_id)
        if getattr(source, 'media', None):
            return await self.raw.send_file(chat_id, source.media, caption=source.message,
                                            **_message_kwargs(kwargs))
        return await self.raw.send_message(chat_id, source.message or '', **_message_kwargs(kwargs))

    async def get_media_group(self, chat_id, message_id):
        source = await self.raw.get_messages(chat_id, ids=message_id)
        grouped_id = getattr(source, 'grouped_id', None)
        if grouped_id is None:
            return [_plain_message(source, self.raw)]
        nearby = await self.raw.get_messages(chat_id, limit=20, min_id=max(0, message_id - 10),
                                             max_id=message_id + 10)
        return [_plain_message(item, self.raw) for item in nearby
                if getattr(item, 'grouped_id', None) == grouped_id]

    async def copy_media_group(self, chat_id, from_chat_id, message_id, **kwargs):
        items = await self.get_media_group(from_chat_id, message_id)
        files = [item.media for item in items if item.media]
        return await self.raw.send_file(chat_id, files, **_message_kwargs(kwargs))

    send_video_note = send_photo

    async def download_media(self, message, file_name=None, **kwargs):
        raw = getattr(message, '_raw', message)
        return await self.raw.download_media(raw, file=file_name)


def _plain_message(raw, client):
    """Wrap a fetched Telethon Message with the subset used by legacy plugins."""
    event = SimpleNamespace(
        message=raw, client=client, chat_id=getattr(raw, 'chat_id', None),
        sender_id=getattr(raw, 'sender_id', None), raw_text=getattr(raw, 'raw_text', ''),
        reply=lambda *a, **k: client.send_message(getattr(raw, 'chat_id', None), *a, **k),
        edit=lambda *a, **k: client.edit_message(getattr(raw, 'chat_id', None), raw.id, *a, **k),
        delete=lambda: client.delete_messages(getattr(raw, 'chat_id', None), [raw.id]),
    )
    return Message(event)


class SenderProxy(Client):
    async def send(self, chat_id, text, **kwargs):
        return await self.send_message(chat_id, text, **kwargs)


class KVProxy:
    def __init__(self, raw):
        self.raw = raw

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def keys(self):
        return [key for key, _value in self.raw.items()]

    async def supports_native_rich(self):
        return False

    async def send_rich(self, chat_id, content, **kwargs):
        text = re.sub(r'<[^>]+>', '', str(content))
        return await self.send_message(chat_id, text, **kwargs)


class CompatContext:
    def __init__(self, ctx, defaults=None):
        self._ctx = ctx
        self._defaults = defaults or {}
        self.filters = Filters()
        self._cleanups = []

    def __getattr__(self, name):
        return getattr(self._ctx, name)

    @property
    def config(self):
        values = dict(self._ctx.config or {})
        for key, default in self._defaults.items():
            if isinstance(default, list) and isinstance(values.get(key), str):
                values[key] = [x.strip() for x in values[key].splitlines() if x.strip()]
            elif isinstance(default, dict) and isinstance(values.get(key), str):
                try:
                    import json
                    values[key] = json.loads(values[key])
                except Exception:
                    values[key] = default
        return values

    @property
    def kv(self):
        return KVProxy(self._ctx.kv)

    @property
    def user_apps(self):
        return [Client(x) for x in self._ctx.users]

    @property
    def user(self):
        return SenderProxy(self._ctx.users[0]) if self._ctx.users else None

    @property
    def bot(self):
        return SenderProxy(self._ctx.bot) if self._ctx.bot is not None else SenderProxy(None)

    @property
    def owner_id(self):
        return int(self.config.get('owner_id', 0) or 0)

    def add_cleanup(self, callback):
        self._cleanups.append(callback)

    def create_task(self, awaitable, *, name=None, operation=None):
        return self._ctx.create_task(awaitable, name=name)

    async def notify(self, text, entity=None, *, channel='', level='info', category='', account=None):
        return await self._ctx.notify(text, entity=entity, channel=channel, level=level, category=category)

    async def notify_table(self, headers, rows, *, caption='', align=None, **kwargs):
        lines = [str(caption or '').strip()]
        lines.append(' | '.join(map(str, headers)))
        lines.extend(' | '.join(map(str, row)) for row in rows)
        return await self.notify('\n'.join(line for line in lines if line), **kwargs)

    async def close(self):
        for callback in reversed(self._cleanups):
            try:
                value = callback()
                if inspect.isawaitable(value):
                    await value
            except Exception:
                self.log.exception('V2 兼容清理失败')

    async def _message(self, event):
        sender = await event.get_sender()
        chat = await event.get_chat()
        reply_raw = await event.get_reply_message() if event.is_reply else None
        reply = None
        if reply_raw is not None:
            fake = SimpleNamespace(message=reply_raw, client=event.client)
            reply = Message(fake, None, chat)
        return Message(event, sender, chat, reply)

    def on_message(self, value=None, *, group=0, target='auto', pattern=None,
                   chats=None, incoming=True, outgoing=False):
        selected = value if isinstance(value, Filter) else None
        if selected is not None:
            incoming = outgoing = None
        decorator = self._ctx.on_message(pattern=pattern, chats=chats,
                                         incoming=incoming, outgoing=outgoing)
        def register(callback):
            @decorator
            async def wrapped(event):
                message = await self._message(event)
                if selected is not None and not selected.check(event, message):
                    return None
                params = len(inspect.signature(callback).parameters)
                client = await Client(event.client).load_me()
                return await callback(client, message) if params >= 2 else await callback(message)
            return callback
        return register

    def on_edited_message(self, value=None, *, group=0, target='auto', pattern=None, chats=None):
        selected = value if isinstance(value, Filter) else None
        decorator = self._ctx.on_edited_message(pattern=pattern, chats=chats)
        def register(callback):
            @decorator
            async def wrapped(event):
                message = await self._message(event)
                if selected is not None and not selected.check(event, message):
                    return None
                params = len(inspect.signature(callback).parameters)
                client = await Client(event.client).load_me()
                return await callback(client, message) if params >= 2 else await callback(message)
            return callback
        return register

    def on_callback(self, value=None, *, group=0, target='auto', pattern=None):
        selected = value if isinstance(value, Filter) else None
        decorator = self._ctx.on_callback(pattern=pattern)
        def register(callback):
            @decorator
            async def wrapped(event):
                message = await self._message(event)
                if selected is not None and not selected.check(event, message):
                    return None
                sender = await event.get_sender()
                query = CallbackQuery(event, message, sender)
                params = len(inspect.signature(callback).parameters)
                client = await Client(event.client).load_me()
                return await callback(client, query) if params >= 2 else await callback(query)
            return callback
        return register

    def schedule(self, callback, trigger, id=None, **fields):
        name = str(id or getattr(callback, '__name__', 'task'))
        if trigger == 'interval':
            seconds = int(fields.pop('seconds', 0) or 0)
            seconds += int(fields.pop('minutes', 0) or 0) * 60
            seconds += int(fields.pop('hours', 0) or 0) * 3600
            return self._ctx.schedule_interval(name, callback, seconds=max(1, seconds))
        trigger_name = type(trigger).__name__.lower()
        if 'interval' in trigger_name:
            interval = getattr(trigger, 'interval', None)
            seconds = int(interval.total_seconds()) if interval is not None else 0
            return self._ctx.schedule_interval(name, callback, seconds=max(1, seconds))
        if 'cron' in trigger_name:
            # APScheduler CronTrigger stores normalized field objects.  V2 owns its
            # scheduler, so transfer the expressions instead of registering the
            # foreign trigger object itself.
            fields = {
                item.name: str(item)
                for item in getattr(trigger, 'fields', ())
                if str(item) != '*'
            }
            timezone = getattr(trigger, 'timezone', None)
            if timezone is not None:
                fields['timezone'] = timezone
        return self._ctx.schedule_cron(name, callback, **fields)

    def action(self, name):
        def register(callback):
            async def wrapped(payload=None):
                args = len(inspect.signature(callback).parameters)
                value = callback(payload or {}) if args else callback()
                return await value if inspect.isawaitable(value) else value
            self._ctx.action(name, wrapped)
            return callback
        return register

    def on_api(self, path, methods=None):
        # V2 原生管理员 API：路径统一为无首尾斜杠，由平台挂载到 /api/plugins/<id>/api/。
        normalized = str(path or '').strip('/')
        def register(callback):
            self._ctx.on_api(normalized, callback)
            return callback
        return register

    def on_webhook(self, value=None):
        if callable(value):
            self._ctx.on_webhook('receive', value)
            return value
        path = str(value or 'receive').strip('/')
        def register(callback):
            self._ctx.on_webhook(path, callback)
            return callback
        return register


def adapt(ctx, defaults=None):
    return CompatContext(ctx, defaults=defaults)

