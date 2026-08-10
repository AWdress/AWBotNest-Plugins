# 标准库
import time as time_module
from datetime import time as time_class
from datetime import datetime
import json, asyncio, random

# 第三方库
import aiomqtt
from aiomqtt import MqttError, Message


# 自定义
from libs.game import do_game, game_state, get_joinable_games_by_amount, join_game, join_random_game_by_amount, get_page_state, has_waiting_game
from libs.mqtt import Client
from libs.log import logger, play_logger
from libs.toml import read


HELP_TOPIC = "blackjack/help"
GAME_TOPIC = "blackjack/games"
STATE_TOPIC = "blackjack/states"
ALERT_TOPIC = "blackjack/alerts"

import os
config_path = "config/config.toml"
temp_dir = "temp_file"
state_file_path = os.path.join(temp_dir, "runtime_state.json")
if not os.path.exists(config_path):
    logger.error(f"配置文件不存在: {config_path}")
    logger.error("请确保已挂载配置文件到容器中")
    # 使用默认值避免崩溃
    config = {"BASIC": {}, "GAME": {}, "MQTT": {}}
else:
    config = read(config_path)

if "GAME" not in config or not isinstance(config.get("GAME"), dict):
    logger.warning("未找到 [GAME] 配置，使用默认配置继续运行")
    config["GAME"] = {}

if "BASIC" not in config or not isinstance(config.get("BASIC"), dict):
    logger.warning("未找到 [BASIC] 配置，使用默认配置继续运行")
    config["BASIC"] = {}

if "MQTT" not in config or not isinstance(config.get("MQTT"), dict):
    logger.warning("未找到 [MQTT] 配置，使用默认配置继续运行")
    config["MQTT"] = {}


def get_game_config_value(old_key, default=None, section=None, nested_key=None):
    game_config = config.get("GAME", {})
    if old_key in game_config:
        return game_config.get(old_key, default)

    if section and isinstance(game_config.get(section), dict):
        section_config = game_config.get(section, {})
        if nested_key and nested_key in section_config:
            return section_config.get(nested_key, default)

    return default

MYID = int(config.get("BASIC", {}).get(
    "MYID",
    config.get("GAME", {}).get("MYID", 0),
))
MYNAME = config.get("BASIC", {}).get("NICKNAME", f"队友{MYID}" if MYID else "队友")
# MQTT 配置应该从 [MQTT] 段读取
MQTT_HOST = config.get("MQTT", {}).get("HOST", "")
MQTT_USER = config.get("MQTT", {}).get("USER", "")
MQTT_PASSWORD = config.get("MQTT", {}).get("PASSWORD", "")


if MYID == 0:
    logger.error("未获取到用户编号，不自动开局")

lock = asyncio.Lock()
g = {}
friends = ()  # 队友由 MQTT 在线状态动态发现，不再使用原项目硬编码白名单。
active_friend_gameids = set()  # 存储由MQTT通知的队友开局gameid
_gameid_added_at: dict[int, float] = {}  # gameid -> 加入时间戳，用于TTL清理
_friend_gameid_amounts: dict[int, int] = {}  # gameid -> 金额，用于同金额段匹配
_gameid_to_sender: dict[int, int] = {}  # gameid -> sender_id，用于按发送者精确清理
_friend_21_blocked: dict[int, int] = {}  # sender_id -> amount，天胩21点封山该金额段，直到重新开局才释放
_own_waiting_gameid: int | None = None  # 自己当前等待中的局编号
_own_waiting_amount: int | None = None  # 自己当前等待中的局金额
_pre_game_responses: dict[int, dict] = {}  # sender_id -> 响应，开局前询问收到的回应
_pre_game_query_id: str | None = None  # 当前开局前询问 ID，用于匹配响应
_pre_game_commit_event: asyncio.Event = asyncio.Event()  # 收到帮手承诺时设置
_pre_game_committed_helper_id: int | None = None  # 已承诺帮助的帮手 ID
_pre_game_committed_helper_name: str | None = None  # 已承诺帮助的帮手名字
_committed_to_sender: int | None = None  # 本机已承诺要帮助的对象 sender_id（防止重复承诺）
_committed_to_sender_set_at: float | None = None  # 承诺设置时间戳，用于 TTL 超时清理
_mqtt_client_ref = None  # 全局持有当前 MQTT client，供非协程上下文使用
_last_personal_stats_at = 0.0  # 上次上报个人战绩的时间戳
friend_states = {}


def _remove_friend_gameids(sender_id: int):
    # 优先：按 sender_id 清理所有已追踪的 gameid（不依赖 friend_states，cover friend_started_game 场景）
    sender_gids = [gid for gid, sid in list(_gameid_to_sender.items()) if sid == sender_id]
    for gid in sender_gids:
        _discard_friend_gameid(gid)

    # 兜底：清理 friend_states 里记录的 gameid（重启后 _gameid_to_sender 为空时生效）
    state = friend_states.get(sender_id)
    if not isinstance(state, dict):
        return

    active_gameids = state.get("active_gameids")
    if isinstance(active_gameids, list):
        for gameid in active_gameids:
            try:
                _discard_friend_gameid(int(gameid))
            except (ValueError, TypeError):
                continue

    gameid = state.get("gameid")
    if gameid:
        try:
            _discard_friend_gameid(int(gameid))
        except (ValueError, TypeError):
            pass


def _add_friend_gameid(gid: int, amount: int | None = None, sender_id: int | None = None) -> None:
    active_friend_gameids.add(gid)
    _gameid_added_at[gid] = time_module.time()
    if amount is not None:
        _friend_gameid_amounts[gid] = amount
    if sender_id is not None:
        _gameid_to_sender[gid] = sender_id


def _discard_friend_gameid(gid: int) -> None:
    active_friend_gameids.discard(gid)
    _gameid_added_at.pop(gid, None)
    _friend_gameid_amounts.pop(gid, None)
    _gameid_to_sender.pop(gid, None)


def _purge_stale_friend_gameids(max_age: float = 300.0) -> None:
    now = time_module.time()
    stale = [gid for gid, ts in list(_gameid_added_at.items()) if now - ts > max_age]
    for gid in stale:
        _discard_friend_gameid(gid)
    if stale:
        logger.debug(f"清理过期队友对局编号 {len(stale)} 个")


def _ensure_temp_dir():
    os.makedirs(temp_dir, exist_ok=True)


def save_runtime_state():
    try:
        _ensure_temp_dir()
        payload = {
            "my_id": MYID,
            "friends": list(friends),
            "friend_states": friend_states,
            "active_friend_gameids": sorted(active_friend_gameids),
            "active_gameid_amounts": {str(k): v for k, v in _friend_gameid_amounts.items()},
            "gameid_to_sender": {str(k): v for k, v in _gameid_to_sender.items()},
            "friend_21_blocked": {str(k): v for k, v in _friend_21_blocked.items()},
            "own_waiting_gameid": _own_waiting_gameid,
            "own_waiting_amount": _own_waiting_amount,
            "updated_at": int(time_module.time()),
        }
        with open(state_file_path, "w", encoding="utf-8") as state_file:
            json.dump(payload, state_file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"保存本地临时状态失败: {e}")


def load_runtime_state():
    global _own_waiting_gameid, _own_waiting_amount
    if not os.path.exists(state_file_path):
        return

    try:
        with open(state_file_path, "r", encoding="utf-8") as state_file:
            payload = json.load(state_file)

        persisted_my_id = payload.get("my_id")
        if persisted_my_id and persisted_my_id != MYID:
            logger.warning(
                f"本地临时状态中的 my_id={persisted_my_id} 与当前配置 MYID={MYID} 不一致，按当前配置继续"
            )

        persisted_friend_states = payload.get("friend_states", {})
        persisted_gameids = payload.get("active_friend_gameids", [])

        friend_states.clear()
        for sender_id, state in persisted_friend_states.items():
            try:
                normalized_sender_id = int(sender_id)
            except (TypeError, ValueError):
                continue
            if normalized_sender_id == MYID:
                continue
            if isinstance(state, dict):
                friend_states[normalized_sender_id] = state

        persisted_amounts = payload.get("active_gameid_amounts", {})
        persisted_sender_map = payload.get("gameid_to_sender", {})
        persisted_21_blocked = payload.get("friend_21_blocked", {})

        active_friend_gameids.clear()
        _gameid_added_at.clear()
        _friend_gameid_amounts.clear()
        _gameid_to_sender.clear()
        _friend_21_blocked.clear()
        for _sid_str, _blk_amt in persisted_21_blocked.items():
            try:
                _friend_21_blocked[int(_sid_str)] = int(_blk_amt)
            except (TypeError, ValueError):
                pass
        for gameid in persisted_gameids:
            try:
                _gid = int(gameid)
                _amt = persisted_amounts.get(str(_gid))
                _sid = persisted_sender_map.get(str(_gid))
                _add_friend_gameid(
                    _gid,
                    int(_amt) if _amt is not None else None,
                    sender_id=int(_sid) if _sid is not None else None,
                )
            except (TypeError, ValueError):
                continue

        logger.info(
            f"已加载本地状态：队友={len(friend_states)} 活跃对局={len(active_friend_gameids)}"
        )

        # 恢复自己的等待局信息
        _own_gid = payload.get("own_waiting_gameid")
        _own_amt = payload.get("own_waiting_amount")
        if _own_gid is not None:
            try:
                _own_waiting_gameid = int(_own_gid)
                _own_waiting_amount = int(_own_amt) if _own_amt is not None else None
                logger.info(f"已恢复本机等待局：局#{_own_waiting_gameid} 金额={_own_waiting_amount}")
            except (TypeError, ValueError):
                pass
    except Exception as e:
        logger.warning(f"加载本地临时状态失败: {e}")


load_runtime_state()
bonus = get_game_config_value("bonus", 100, "AFK", "BONUS")
if bonus not in [100, 1000, 10000, 100000]:
    logger.warning("挂机魔力设置不在列表内，自动设置为100")
    bonus = 100
# 读取保留点数，默认值18
remain_point = get_game_config_value("remain_point", 18, "AFK", "REMAIN_POINT")
auto_time = get_game_config_value("auto_time", [], "AFK", "TIME")
sleep = get_game_config_value("sleep", 60, "GLOBAL", "SLEEP")
max_help_bonus = get_game_config_value("max_help_bonus", 100, "GLOBAL", "MAX_HELP_BONUS")
friends_count = get_game_config_value("friends_count", 2, "GLOBAL", "FRIENDS_COUNT")
multi_bonus_enabled = get_game_config_value("multi_bonus_enabled", False, "AFK", "MULTI_BONUS_ENABLED")
_raw_multi_bonus = get_game_config_value("multi_bonus_list", [], "AFK", "MULTI_BONUS")
_valid_bonus_values = {100, 1000, 10000, 100000}
multi_bonus_list = [b for b in (_raw_multi_bonus or []) if b in _valid_bonus_values]
_raw_multi_remain = get_game_config_value("multi_bonus_remain_point", [], "AFK", "MULTI_BONUS_REMAIN_POINT")
# 构建 金额 -> 保留点数 映射，缺少的条目回退到全局 remain_point
multi_bonus_remain_map: dict[int, int] = {}
for _i, _amt in enumerate(multi_bonus_list):
    try:
        _rp = int(_raw_multi_remain[_i]) if _i < len(_raw_multi_remain or []) else remain_point
    except (TypeError, ValueError):
        _rp = remain_point
    multi_bonus_remain_map[_amt] = _rp
if multi_bonus_enabled and not multi_bonus_list:
    logger.warning("多金额开关(MULTI_BONUS_ENABLED)已开启，但 MULTI_BONUS 无有效金额，已禁用多金额自动选择")
    multi_bonus_enabled = False
if multi_bonus_enabled:
    logger.info(f"多金额自动选择已开启，监控金额：{multi_bonus_list}")

win_rate_min = get_game_config_value("win_rate_min", 0.0, "ACTIVE", "WIN_RATE_MIN")
if win_rate_min < 0 or win_rate_min > 1:
    logger.warning("胜率足额配置 WIN_RATE_MIN 应在 0.0~1.0 之间，已禁用")
    win_rate_min = 0.0
win_rate_apply_in_time = get_game_config_value("win_rate_apply_in_time", False, "ACTIVE", "WIN_RATE_APPLY_IN_TIME")
# 对战模式独立金额列表：[[金额, 保留点数], ...]
_raw_battle_amounts = get_game_config_value("battle_amounts", [], "ACTIVE", "BATTLE_AMOUNTS")
battle_bonus_list: list[int] = []
battle_remain_map: dict[int, int] = {}
for _entry in (_raw_battle_amounts or []):
    if isinstance(_entry, (list, tuple)) and len(_entry) >= 2:
        _b_amt, _b_rp = _entry[0], _entry[1]
        if _b_amt in _valid_bonus_values:
            battle_bonus_list.append(int(_b_amt))
            battle_remain_map[int(_b_amt)] = int(_b_rp)
if win_rate_min > 0:
    logger.info(f"胜率足额对局已开启：胜率≥{win_rate_min:.0%} 时非时间段也允许自动开局")
    if battle_bonus_list:
        logger.info(f"对战模式金额列表：{battle_bonus_list}，保留点数：{battle_remain_map}")
    else:
        logger.info(f"对战模式未配置独立金额，沿用挂机多金额列表")
    if win_rate_apply_in_time:
        logger.info(f"时间段内对战模式已开启：胜率≥{win_rate_min:.0%} 启用对战（加入等待局），胜率不达标降级为挂机（开新局）")

active_enabled = get_game_config_value("active_enabled", False, "ACTIVE", "ENABLED")
active_sleep = get_game_config_value("active_sleep", 30, "ACTIVE", "SLEEP")
active_max_games = get_game_config_value("active_max_games", 0, "ACTIVE", "MAX_GAMES")
if active_enabled:
    logger.info(f"对战功能已开启：每局等待={active_sleep}s 每天上限={active_max_games or '不限'}")


async def _is_gameid_still_active(target_gameid) -> bool:
    if not target_gameid:
        return False
    public_gameids, _, _r = await game_state()
    try:
        return int(target_gameid) in set(public_gameids)
    except (TypeError, ValueError):
        return False


def _get_friend_name(sender_id: int) -> str:
    """从 friend_states 对应明称，找不到则返回'队友{id}'。"""
    name = friend_states.get(sender_id, {}).get("friend_name") or ""
    return name if name else f"队友{sender_id}"


async def _publish_alert(client, alert_type: str, data: dict) -> None:
    """向 ALERT_TOPIC 推送告警消息。"""
    if client is None:
        return
    try:
        payload = {"type": alert_type, "sender_id": MYID, "friend_name": MYNAME, **data}
        await client.publish(ALERT_TOPIC, payload=json.dumps(payload))
    except Exception as _e:
        logger.debug(f"告警推送失败: {_e}")


async def _push_state_now(
    client,
    waiting: bool,
    gameid: int | None = None,
    amount: int | None = None,
) -> None:
    """立即向队友推送当前状态，不等心跳定时器。"""
    if client is None or MYID == 0:
        return
    try:
        payload = {
            "type": "friend_state",
            "sender_id": MYID,
            "friend_name": MYNAME,
            "waiting": waiting,
            "gameid": gameid,
            "amount": amount,
        }
        friend_states[MYID] = {
            "waiting": waiting,
            "gameid": gameid,
            "updated_at": time_module.time(),
        }
        await client.publish(STATE_TOPIC, payload=json.dumps(payload))
    except Exception as e:
        logger.debug(f"即时状态推送失败: {e}")


def _select_available_friend(amount: int | None = None) -> int | None:
    """从在线队友中选择帮手。
    优先选同金额段正在等待的伙伴（精准加入互相平局）。
    找不到则所有在线队友（无论是否等待中）均可帮助，接收端会自行过滤不降级。
    找不到则返回 None（回退为广播）。
    """
    now = time_module.time()
    same_tier_candidates = []
    online_candidates = []
    for sender_id, state in friend_states.items():
        if sender_id == MYID:
            continue
        updated_at = state.get("updated_at", 0)
        if not updated_at or now - updated_at > max(30, sleep * 3):
            continue  # 从未收到心跳或状态已过期，视为离线
        is_waiting = state.get("waiting", False)
        gameid = state.get("gameid")
        if is_waiting and amount is not None and gameid:
            # 该队友正在等待且是同金额段的伙伴，优先互相平局
            try:
                gid_int = int(gameid)
                if gid_int in active_friend_gameids and _friend_gameid_amounts.get(gid_int) == amount:
                    same_tier_candidates.append(sender_id)
                    continue
            except (ValueError, TypeError):
                pass
        # 在线即可作为备选（等待中的队友也可以加入别人的局）
        online_candidates.append(sender_id)
    if same_tier_candidates:
        return random.choice(same_tier_candidates)
    if online_candidates:
        return random.choice(online_candidates)
    return None


async def _process_help_request(
    client: Client,
    sender_id,
    requester_name,
    requester_gameid,
    amount,
    start_attempt: int = 0,
):
    max_help_attempts = 2
    help_attempts = start_attempt
    while help_attempts < max_help_attempts:
        help_attempts += 1
        # 优先尝试精准加入请求者特定的 gameid
        point, gameid, joined_forms, opponent_name = None, None, {}, None
        try:
            joinable = await get_joinable_games_by_amount([amount])
            amount_key = str(int(amount)) if isinstance(amount, (int, float)) else str(amount)
            candidates = joinable.get(amount_key, [])
            target_candidate = next(
                (c for c in candidates if str(c.get('gameid', '')) == str(requester_gameid)),
                None
            )
            if target_candidate:
                join_payload = {k: v for k, v in target_candidate.items() if v not in (None, '')}
                point, gameid, joined_forms, opponent_name = await join_game(join_payload)
                play_logger.info(f"[平局] 精准加入目标局 对局编号={requester_gameid}")
            else:
                play_logger.debug(f"[平局] 目标局 {requester_gameid} 不在列表，改步随机加入")
                point, gameid, _, joined_forms, opponent_name = await join_random_game_by_amount(amount)
        except Exception as _je:
            logger.warning(f"[平局] 加局失败：{_je}")
            point, gameid, joined_forms, opponent_name = None, None, {}, None

        if gameid is not None:
            join_data = {
                "game": "hit",
                "gameid": gameid,
            }
            matched_target_game = str(gameid) == str(requester_gameid)
            matched_by_name = bool(opponent_name and opponent_name == requester_name)
            game_finished = (
                point is not None
                and '再抓一张' not in joined_forms
                and '不再抓了，结束' not in joined_forms
            )
            is_target = matched_target_game or matched_by_name

            if is_target:
                if matched_by_name and not matched_target_game:
                    play_logger.info(
                        f"[平局] 对局编号未直接匹配但昵称一致，认定为目标局：对手={opponent_name} 对局编号={gameid}"
                    )
                if not game_finished:
                    point, gameid = await do_game(join_data, 21, "平局")
                # game_finished=True 时 point 已是最终结果，直接进入验证
            else:
                if not game_finished:
                    point, gameid = await do_game(join_data, 17, "帮助误入普通局")
                play_logger.warning(
                    f"[平局] 加入到非目标局：目标局={requester_gameid} 实际局={gameid} 对手={opponent_name} 点数={point} 尝试={help_attempts}，按普通策略结束后重试"
                )
                await asyncio.sleep(1)
                continue

        if point:
            verify_request = {
                "type": "friend_help_verify_request",
                "sender_id": MYID,
                "friend_name": MYNAME,
                "target_sender_id": sender_id,
                "target_gameid": requester_gameid,
                "helper_gameid": gameid,
                "amount": amount,
                "point": point,
                "attempt": help_attempts,
                "requester_name": requester_name,
            }
            await client.publish(
                GAME_TOPIC,
                payload=json.dumps(verify_request),
            )
            logger.info(
                f"已发平局验证：目标局={requester_gameid} 点数={point}"
            )
            play_logger.info(
                f"[平局] 已发送验证请求：目标局={requester_gameid} 点数={point} 实际局={gameid}"
            )
            return

        play_logger.warning(
            f"[平局] 第{help_attempts}次尝试未找到局或未拿到点数：目标局={requester_gameid} 实际局={gameid}"
        )
        await asyncio.sleep(1)

    play_logger.warning(
        f"[平局] 帮助失败：{requester_name}的目标局{requester_gameid} 金额{amount} 尝试{help_attempts}次"
    )
    await _publish_alert(client, "help_failed", {
        "requester_name": requester_name,
        "requester_gameid": requester_gameid,
        "amount": amount,
        "attempts": help_attempts,
        "message": f"平局帮助失败：{requester_name} 目标局={requester_gameid} 金额={amount} 尝试{help_attempts}次",
    })


async def help(client: Client, message):
    """处理 HELP_TOPIC 平局求助消息。"""
    async with lock:
        payload = message.payload.decode() if isinstance(message.payload, (bytes, bytearray)) else str(message.payload)
        logger.debug(f"收到求助主题原始消息: {payload}")
        data = json.loads(payload)
        if data.get("type") != "friend_help_request":
            logger.debug("非平局请求消息，忽略")
            return

        sender_id = data.get("sender_id")
        if sender_id == MYID:
            logger.debug("自己的求助消息，忽略")
            return

        target_helper_id = data.get("target_helper_id")
        if target_helper_id is not None:
            try:
                if int(target_helper_id) != MYID:
                    logger.debug(f"平局求助指定给 {target_helper_id}，非本账号（{MYID}），忽略")
                    return
            except (ValueError, TypeError):
                logger.debug(f"指定帮手编号格式异常（{target_helper_id}），按广播处理")

        requester_gameid = data.get("gameid")
        requester_name = data.get("friend_name", "队友")
        if not requester_gameid:
            logger.warning("缺少对局编号，无法帮助队友")
            return

        amount = data.get("amount", 0)
        if amount > max_help_bonus:
            logger.warning(f"{requester_name}需要帮助，但所需魔力大于挂机魔力，自动取消")
            return
        # 不能降级：只帮助本机配置金额段内的对局
        _my_amounts = multi_bonus_list if multi_bonus_enabled else [bonus]
        if amount not in _my_amounts:
            logger.debug(f"平局求助金额 {amount} 不在本机金额列表 {_my_amounts}，跳过（不降级）")
            return

        play_logger.info(
            f"[平局] 收到求助：{requester_name}[对局编号={requester_gameid}] 金额={amount}"
        )

        await _process_help_request(client, sender_id, requester_name, requester_gameid, amount)

        # B 帮助完毕，清除对 A 的承诺（爆点路径不发 pre_game_release，在此清除）
        global _committed_to_sender, _committed_to_sender_set_at
        if _committed_to_sender == sender_id:
            _committed_to_sender = None
            _committed_to_sender_set_at = None
            play_logger.info(f"[开局协调] 帮助完成，解除对 {requester_name} 的承诺")


async def handle_help_verify_request(client: Client, data: dict):
    sender_id = data.get("sender_id")
    target_sender_id = data.get("target_sender_id")
    if target_sender_id != MYID or sender_id == MYID:
        return

    target_gameid = data.get("target_gameid")
    target_still_exists = await _is_gameid_still_active(target_gameid)
    verify_result = {
        "type": "friend_help_verify_result",
        "sender_id": MYID,
        "friend_name": MYNAME,
        "target_sender_id": sender_id,
        "target_gameid": target_gameid,
        "helper_gameid": data.get("helper_gameid"),
        "amount": data.get("amount"),
        "point": data.get("point"),
        "attempt": data.get("attempt"),
        "requester_name": data.get("requester_name"),
        "target_still_exists": target_still_exists,
    }
    await client.publish(GAME_TOPIC, payload=json.dumps(verify_result))
    logger.info(
        f"已回复平局验证：目标局={target_gameid} 是否仍在={target_still_exists}"
    )
    play_logger.debug(
        f"[平局] 已回复验证，消息体={verify_result}"
    )


async def handle_help_verify_result(client: Client, data: dict):
    target_sender_id = data.get("target_sender_id")
    if target_sender_id != MYID:
        return

    target_gameid = data.get("target_gameid")
    target_still_exists = bool(data.get("target_still_exists"))
    point = data.get("point")
    helper_gameid = data.get("helper_gameid")
    amount = data.get("amount", 0)
    attempt = data.get("attempt")

    if not target_still_exists:
        matched_target_game = str(helper_gameid) == str(target_gameid)
        if not matched_target_game:
            play_logger.warning(
                f"[平局] 验证通过但实际局非目标局：目标局={target_gameid} 实际局={helper_gameid}，补试1次"
            )
            await asyncio.sleep(1)
            async with lock:
                await _process_help_request(
                    client,
                    data.get("sender_id"),  # 原始求助者ID，非自身
                    data.get("requester_name", "队友"),
                    target_gameid,
                    amount,
                    start_attempt=int(attempt or 0),
                )
            return

        completion_msg = {
            "type": "friend_helped",
            "sender_id": MYID,
            "friend_name": MYNAME,
            "target_gameid": target_gameid,
            "gameid": helper_gameid,
            "amount": amount,
            "point": point,
        }
        await client.publish(
            GAME_TOPIC,
            payload=json.dumps(completion_msg),
        )
        logger.info(
            f"已发平局完成：目标局={target_gameid} 点数={point}"
        )
        play_logger.info(
            f"[平局] 验证通过，命中目标局：目标局={target_gameid} 点数={point}"
        )
        play_logger.debug(
            f"[平局] 完成通知 payload={completion_msg}"
        )
        return

    play_logger.warning(
        f"[平局] 验证发现目标局仍在：目标局={target_gameid}，补试1次"
    )
    await asyncio.sleep(1)
    async with lock:
        await _process_help_request(
            client,
            data.get("sender_id"),  # 原始求助者ID，非自身
            data.get("requester_name", "队友"),
            target_gameid,
            amount,
            start_attempt=int(attempt or 0),
        )


async def _join_existing_game(joinable_games: dict, amount: int) -> bool:
    """对战模式：直接加入已有的等待局（不创建新局，排除队友局）。返回是否实际参与了一局。"""
    _amount_key = str(int(amount)) if isinstance(amount, (int, float)) else str(amount)
    all_candidates = joinable_games.get(_amount_key, [])
    _friend_gids_str = {str(gid) for gid in active_friend_gameids}
    candidates = [c for c in all_candidates if str(c.get('gameid', '')) not in _friend_gids_str]
    if not candidates:
        logger.debug(f"[对战] 当前无可加入的非队友 {amount} 金额等待局（总{len(all_candidates)}局，队友{len(all_candidates)-len(candidates)}局），跳过")
        return False
    async with lock:
        candidate = random.choice(candidates)
        join_payload = {k: v for k, v in candidate.items() if v not in (None, '')}
        logger.info(f"[对战] 加入等待局 对局编号={candidate.get('gameid')} 金额={amount}")
        _remain = battle_remain_map.get(amount) or multi_bonus_remain_map.get(amount, remain_point)
        point, gameid, joined_forms, opponent_name = await join_game(join_payload)
        if gameid is not None:
            game_finished = (
                point is not None
                and '再抓一张' not in joined_forms
                and '不再抓了，结束' not in joined_forms
            )
            if not game_finished:
                join_data = {"game": "hit", "gameid": gameid}
                point, gameid = await do_game(join_data, _remain, "对战")
        logger.info(f"[对战] 结束，点数={point} 对局编号={gameid}")
        return gameid is not None


def _select_amount_myid_balanced(eligible, stranger_fn, friend_fn):
    """选择金额，并列时用 MYID 分散，避免多实例同时选择最高金额。"""
    if not eligible:
        return None
    sorted_amts = sorted(eligible, key=lambda a: (stranger_fn(a), -friend_fn(a), a))
    best_primary = (stranger_fn(sorted_amts[0]), -friend_fn(sorted_amts[0]))
    tied = [a for a in sorted_amts if (stranger_fn(a), -friend_fn(a)) == best_primary]
    return tied[MYID % len(tied)] if len(tied) > 1 else tied[0]


async def start_my_game(client: Client = None, games: list[int] | None = None, run_amount: int | None = None):
    # 只统计其他账号的等待中/进行中状态，避免把自己算进“队友挂机数”
    running_friend_games = 0
    stale_sender_ids = []

    for sender_id, state in friend_states.items():
        if sender_id == MYID:
            continue

        waiting = bool(state.get("waiting", False))
        updated_at = state.get("updated_at", 0)

        if not updated_at or time_module.time() - updated_at > max(30, sleep * 3):
            stale_sender_ids.append(sender_id)
            continue

        if waiting:
            running_friend_games += 1

    for sender_id in stale_sender_ids:
        friend_states.pop(sender_id, None)
    if stale_sender_ids:
        save_runtime_state()

    if running_friend_games >= friends_count:
        logger.info(f"已有{friends_count}个队友挂机，取消开局")
        return

    # 多金额模式：开局前重新查实时局数，确认最优金额
    if multi_bonus_enabled and multi_bonus_list:
        try:
            _live_joinable = await get_joinable_games_by_amount(multi_bonus_list)
            _live_friend_str = {str(gid) for gid in active_friend_gameids}
            _live_blocked = set(_friend_21_blocked.values())
            def _lc_friend(a):
                # 页面 join 表单不暴露 gameid，改用 MQTT 跟踪的金额映射统计
                # 排除自己的等待局（可能通过 sync_response 误入 active_friend_gameids）
                return sum(
                    1 for gid in active_friend_gameids
                    if _friend_gameid_amounts.get(gid) == a
                    and (_own_waiting_gameid is None or gid != _own_waiting_gameid)
                )
            def _lc_stranger(a):
                return sum(1 for e in _live_joinable.get(str(int(a)), []) if str(e.get('gameid','')) not in _live_friend_str)
            _live_eligible = [a for a in multi_bonus_list if _lc_friend(a) < 2 and a not in _live_blocked]
            _live_counts = ' | '.join(
                f'{a}魔力:路人{_lc_stranger(a)}/队友{_lc_friend(a)}{"[封山]" if a in _live_blocked else ""}'
                for a in multi_bonus_list
            )
            if _live_eligible:
                _prev_run_amount = run_amount
                run_amount = _select_amount_myid_balanced(_live_eligible, _lc_stranger, _lc_friend)
                # 只在金额发生变化，或外层没有传入金额时才记录（避免与外层监控日志重复）
                if run_amount != _prev_run_amount:
                    play_logger.info(f"开局前实时校验 [{_live_counts}]，金额调整 {_prev_run_amount} → {run_amount}")
                else:
                    logger.debug(f"开局前实时校验 [{_live_counts}]，确认金额 {run_amount}（无变化）")
            else:
                play_logger.info(f"开局前实时校验 [{_live_counts}]，所有金额队友已满，取消本次开局")
                return
        except Exception as _lv_e:
            logger.debug(f"开局前实时校验失败，沿用传入金额: {_lv_e}")

    # 开局前协调：询问队友是否能帮平局，必须收到承诺后才开局
    _pre_game_committed_helper: int | None = None
    _pre_game_committed_helper_disp: str | None = None  # 承诺帮手的显示名（用于日志）
    # 用页面实时状态判断是否已有等待中游戏，避免用 MQTT 缓存状态导致误判
    _already_waiting = await has_waiting_game()
    if client and MYID > 0 and not _already_waiting:
        global _pre_game_responses, _pre_game_query_id
        global _pre_game_commit_event, _pre_game_committed_helper_id, _pre_game_committed_helper_name
        _effective_q_amount = run_amount if run_amount is not None else bonus
        _query_round = 0
        _max_query_rounds = 10  # 最多重试10次（每轮等5秒，共约50秒）
        while _query_round < _max_query_rounds:
            _query_round += 1
            _pre_game_responses.clear()
            _pre_game_committed_helper_id = None
            _pre_game_committed_helper_name = None
            _pre_game_commit_event.clear()
            _query_id = str(int(time_module.time() * 1000) % 100000)
            _pre_game_query_id = _query_id
            await client.publish(GAME_TOPIC, payload=json.dumps({
                "type": "pre_game_query",
                "sender_id": MYID,
                "friend_name": MYNAME,
                "amount": _effective_q_amount,
                "query_id": _query_id,
            }))
            play_logger.info(f"[开局协调] 第{_query_round}次询问队友，金额={_effective_q_amount}，等待承诺（最多5秒）...")
            try:
                await asyncio.wait_for(_pre_game_commit_event.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            _pre_game_query_id = None
            if _pre_game_committed_helper_id is not None:
                _pre_game_committed_helper = _pre_game_committed_helper_id
                _helper_display = _pre_game_committed_helper_name or _get_friend_name(_pre_game_committed_helper)
                _pre_game_committed_helper_disp = _helper_display
                play_logger.info(f"[开局协调] 收到 {_helper_display} 的承诺，开始开局")
                break
            else:
                play_logger.info(f"[开局协调] 第{_query_round}次无队友承诺，重新询问...")
        else:
            play_logger.info("[开局协调] 多次询问无响应，放弃本次开局")
            return

    async with lock:
        if await has_waiting_game():
            logger.debug("开局前复查：已有等待中游戏，取消本次开局")
            return
        run_amount = run_amount if run_amount is not None else bonus
        run_remain_point = multi_bonus_remain_map.get(run_amount, remain_point)
        start_data = {
            "game": "hit",
            "start": "yes",
            "amount": run_amount,
        }
        # 开始拿牌前立即推送：告知队友我正在游戏中（不在等待）
        await _push_state_now(client, waiting=False, gameid=None, amount=None)
        point, gameid = await do_game(start_data, run_remain_point, "开局")
        play_logger.info(f"开局{run_amount}魔力，点数={point}，对局编号={gameid}")

        # 上报挂机开局事件，供外部项目统计输赢
        if point and gameid and client:
            try:
                await _publish_alert(client, "afk_game_started", {
                    "gameid": gameid,
                    "amount": run_amount,
                    "point": point,
                    "is_bust": point > 21,
                    "timestamp": int(time_module.time()),
                })
            except Exception:
                pass

        if gameid:
            try:
                _discard_friend_gameid(int(gameid))
            except (ValueError, TypeError):
                pass

        # 记录自己的等待中局信息，供 sync_response 使用
        # 21点天胡已必胜，不需要队友帮助，不记录等待局（避免被队友计为已满员）
        global _own_waiting_gameid, _own_waiting_amount
        if gameid and point and point < 21:
            try:
                _own_waiting_gameid = int(gameid)
                _own_waiting_amount = run_amount
            except (ValueError, TypeError):
                _own_waiting_gameid = None
                _own_waiting_amount = None
        elif point == 21 or (point and point > 21):
            _own_waiting_gameid = None
            _own_waiting_amount = None

        # 拿完牌立即推送最终状态
        if point and point < 21:
            # 等待对手加入
            await _push_state_now(client, waiting=True, gameid=_own_waiting_gameid, amount=run_amount)
        else:
            # 爆点或天胡，不在等待
            await _push_state_now(client, waiting=False, gameid=None, amount=None)

        if point and client:
            game_notification = {
                "type": "friend_started_game",
                "sender_id": MYID,
                "friend_name": MYNAME,
                "gameid": gameid,
                "amount": run_amount,
                "point": point,
            }

            try:
                await client.publish(
                    GAME_TOPIC,
                    payload=json.dumps(game_notification)
                )
                logger.info(
                    f"已通知队友开局：金额={run_amount} 点数={point}"
                )
            except Exception as e:
                logger.warning(f"通知队友时出错: {e}")

        if point and point <= 21 and _pre_game_committed_helper is not None and client:
            # 没爆点（包括天胡），通知承诺帮手解除
            try:
                await client.publish(GAME_TOPIC, payload=json.dumps({
                    "type": "pre_game_release",
                    "sender_id": MYID,
                    "friend_name": MYNAME,
                    "target_helper_id": _pre_game_committed_helper,
                    "point": point,
                }))
                play_logger.info(f"[开局协调] 点数={point}≤21，通知 {_pre_game_committed_helper_disp or _get_friend_name(_pre_game_committed_helper)} 解除承诺")
            except Exception as e:
                logger.debug(f"发送解除通知失败: {e}")

        if point and point > 21:
            play_logger.info(
                f"[平局] 自己爆点，发求助 gameid={gameid} amount={run_amount}"
            )
            logger.info("寻求队友平局")
            if client:
                # 优先使用开局前预选的帮手；没有响应或无同金额则 fallback 到实时查找
                if _pre_game_committed_helper is not None:
                    _target_helper = _pre_game_committed_helper
                else:
                    _target_helper = _select_available_friend(amount=run_amount)
                _help_payload = {
                    "type": "friend_help_request",
                    "sender_id": MYID,
                    "friend_name": MYNAME,
                    "gameid": gameid,
                    "amount": run_amount,
                    "point": point,
                }
                if _target_helper is not None:
                    _help_payload["target_helper_id"] = _target_helper
                    logger.info(f"指定队友 {_get_friend_name(_target_helper)} 处理平局")
                else:
                    logger.info("无空闲队友，广播平局求助")
                await client.publish(
                    HELP_TOPIC,
                    payload=json.dumps(_help_payload),
                )
                logger.info(
                    f"已发布平局求助：对局编号={gameid} 金额={run_amount} 点数={point}"
                )
                play_logger.debug(
                    f"[平局] 已发布求助消息 对局编号={gameid} 金额={run_amount} 点数={point}"
                )
            else:
                logger.warning("无法寻求队友平局：MQTT客户端不可用")
                play_logger.warning(
                    f"[平局] MQTT客户端不可用，未能为对局编号={gameid}发布求助消息"
                )


async def listen(client: Client):
    global _own_waiting_gameid, _own_waiting_amount
    global _committed_to_sender, _committed_to_sender_set_at, _pre_game_committed_helper_id, _pre_game_commit_event, _pre_game_committed_helper_name
    while True:
        try:
            async for message in client.messages:
                if message.topic.matches(HELP_TOPIC):
                    await help(client, message)
                elif message.topic.matches(STATE_TOPIC) and MYID > 0:
                    payload = message.payload.decode()
                    logger.debug(f"收到状态主题原始消息: {payload}")
                    try:
                        data = json.loads(payload)
                        if not isinstance(data, dict):
                            continue
                        sender_id = data.get("sender_id")
                        if sender_id == MYID:
                            continue

                        # 处理启动同步请求：回复本机全量活跃局列表（用独立 type 避免被普通心跳覆盖）
                        if data.get("type") == "sync_request" and sender_id:
                            logger.info(
                                f"收到来自 {data.get('friend_name', f'队友{sender_id}')} 的全量同步请求，回复活跃局列表"
                            )
                            try:
                                _page_st = await get_page_state()
                                _is_waiting = _page_st.get("waiting", False)
                                # 优先用本次会话记录的局（含金额），兜底用页面检测到的 gameid（金额未知）
                                if _own_waiting_gameid and _is_waiting:
                                    _sync_gameid = _own_waiting_gameid
                                    _sync_amount = _own_waiting_amount
                                elif _is_waiting and _page_st.get("gameid"):
                                    _sync_gameid = _page_st["gameid"]
                                    _sync_amount = None  # 金额未知，接收方靠页面推断
                                else:
                                    _sync_gameid = None
                                    _sync_amount = None
                                _own_gids = [_sync_gameid] if _sync_gameid else []
                                _own_amounts = (
                                    {str(_sync_gameid): _sync_amount}
                                    if (_sync_gameid and _sync_amount is not None)
                                    else {}
                                )
                                _sync_resp = {
                                    "type": "sync_response",
                                    "sender_id": MYID,
                                    "friend_name": MYNAME,
                                    "waiting": _is_waiting,
                                    "gameid": _page_st.get("gameid"),
                                    "active_gameids": _own_gids,
                                    "gameid_amounts": _own_amounts,
                                }
                                await client.publish(
                                    STATE_TOPIC, payload=json.dumps(_sync_resp)
                                )
                                if _own_gids:
                                    amt_hint = f"金额={_sync_amount}" if _sync_amount is not None else "金额待推断"
                                    logger.info(
                                        f"已回复同步请求：等待局 局#{_sync_gameid}({amt_hint})"
                                    )
                                else:
                                    logger.info("已回复同步请求：当前无等待中的局")
                            except Exception as _se:
                                logger.warning(f"回复同步请求失败: {_se}")
                            continue

                        # 处理同步响应（纯加法，不清除旧记录，不影响 friend_states 心跳逻辑）
                        if data.get("type") == "sync_response" and sender_id:
                            _resp_gameids = data.get("active_gameids", [])
                            _resp_amounts = data.get("gameid_amounts", {})
                            added = 0
                            detail_parts = []
                            for _gid_raw in _resp_gameids:
                                try:
                                    _gid = int(_gid_raw)
                                    _amt_val = _resp_amounts.get(str(_gid))
                                    _amt_int = int(_amt_val) if _amt_val is not None else None
                                    _add_friend_gameid(_gid, _amt_int, sender_id=int(sender_id) if sender_id else None)
                                    added += 1
                                    amt_str = f"{_amt_int}" if _amt_int is not None else "未知金额"
                                    detail_parts.append(f"局#{_gid}({amt_str})")
                                except (ValueError, TypeError):
                                    pass
                            detail_str = "、".join(detail_parts) if detail_parts else "无"
                            logger.info(
                                f"已合并来自 {data.get('friend_name', f'队友{sender_id}')} 的同步响应，"
                                f"新增/刷新 {added} 个活跃局编号：{detail_str}"
                            )
                            save_runtime_state()
                            continue

                        if sender_id:
                            source = data.get("source")
                            _hb_is_waiting = bool(data.get("waiting", False))
                            _hb_gameid = data.get("gameid")
                            _hb_sid_int = int(sender_id) if sender_id else None
                            synced_gameids = []

                            if source == "game_list_sync":
                                # 全量同步：先清旧记录再批量写入
                                _remove_friend_gameids(_hb_sid_int)
                                raw_gameids = data.get("active_gameids", [])
                                if isinstance(raw_gameids, list):
                                    for gameid in raw_gameids:
                                        try:
                                            synced_gameids.append(int(gameid))
                                        except (ValueError, TypeError):
                                            continue

                            friend_states[_hb_sid_int] = {
                                "waiting": _hb_is_waiting,
                                "gameid": _hb_gameid,
                                "friend_name": data.get("friend_name", ""),
                                "active_gameids": synced_gameids,
                                "source": source,
                                "updated_at": time_module.time(),
                            }

                            if source == "game_list_sync":
                                _gameid_amounts_map = data.get("gameid_amounts", {})
                                for _gid in synced_gameids:
                                    try:
                                        _amt_val = _gameid_amounts_map.get(str(_gid))
                                        _add_friend_gameid(_gid, int(_amt_val) if _amt_val is not None else None, sender_id=_hb_sid_int)
                                    except (ValueError, TypeError):
                                        _add_friend_gameid(_gid, sender_id=_hb_sid_int)
                            else:
                                _heartbeat_amount = data.get("amount")
                                if _hb_is_waiting:
                                    if _hb_gameid:
                                        # 有新 gameid：替换旧记录
                                        _remove_friend_gameids(_hb_sid_int)
                                        try:
                                            _add_friend_gameid(
                                                int(_hb_gameid),
                                                int(_heartbeat_amount) if _heartbeat_amount is not None else None,
                                                sender_id=_hb_sid_int,
                                            )
                                        except (ValueError, TypeError):
                                            pass
                                    # else: waiting=True 但无 gameid（心跳短暂没拿到），保留 friend_started_game 写入的已有记录
                                else:
                                    # 游戏结束：立即清除该队友的所有记录
                                    _remove_friend_gameids(_hb_sid_int)
                                    if _hb_sid_int:
                                        _friend_21_blocked.pop(_hb_sid_int, None)
                            save_runtime_state()
                    except json.JSONDecodeError:
                        logger.warning(f"收到非JSON状态消息，已忽略: {payload}")
                elif message.topic.matches(GAME_TOPIC) and MYID > 0:
                    # 处理游戏完成通知或队友加入确认
                    payload = message.payload.decode()
                    logger.debug(f"收到游戏主题原始消息: {payload}")

                    try:
                        data = json.loads(payload)

                        # 检查是否是游戏完成通知
                        if isinstance(data, dict):
                            sender_id = data.get("sender_id")
                            if sender_id == MYID:
                                logger.debug("自己的协同消息，忽略")
                                continue

                            if data.get("type") == "friend_joined":
                                # 队友已加入，可能可释放gameid占用
                                logger.info(
                                    f"队友 {data.get('friend_name', f'队友{sender_id}')} 已加入：对局编号={data.get('gameid')}"
                                )
                                target_gameid = data.get("gameid")
                                if target_gameid:
                                    try:
                                        _discard_friend_gameid(int(target_gameid))
                                        # 队友加入的是自己的局，清除自身等待记录
                                        if _own_waiting_gameid == int(target_gameid):
                                            _own_waiting_gameid = None
                                            _own_waiting_amount = None
                                    except (ValueError, TypeError):
                                        pass
                                save_runtime_state()
                            elif data.get("type") == "friend_started_game":
                                # 其他队友的开局通知（用于检查队友数量）
                                gameid = data.get("gameid")
                                amount_val = data.get("amount")
                                _started_point = data.get("point")
                                logger.info(
                                    f"队友开局：{data.get('friend_name', f'队友{sender_id}')} "
                                    f"金额={amount_val} 点数={_started_point} "
                                    f"对局编号={gameid if gameid else '未知（将按路人处理）'}"
                                )
                                # 新开局时先清除旧的 gameid 和天胡封山记录
                                _sid_int = int(sender_id) if sender_id else None
                                if _sid_int:
                                    _remove_friend_gameids(_sid_int)
                                    _friend_21_blocked.pop(_sid_int, None)
                                if _started_point == 21:
                                    # 天胡21点：封山该金额段，直到该队友重新开局才释放
                                    if _sid_int and amount_val is not None:
                                        try:
                                            _friend_21_blocked[_sid_int] = int(amount_val)
                                            play_logger.info(
                                                f"队友 {data.get('friend_name', f'队友{sender_id}')} 天胡21点，封山 {amount_val} 金额段直到重新开局"
                                            )
                                        except (ValueError, TypeError):
                                            pass
                                elif gameid:
                                    try:
                                        _add_friend_gameid(
                                            int(gameid),
                                            int(amount_val) if amount_val is not None else None,
                                            sender_id=_sid_int,
                                        )
                                        logger.debug(f"记录队友开局编号={gameid} 金额={amount_val}")
                                    except (ValueError, TypeError):
                                        pass
                                save_runtime_state()
                                # 安全网：如果本机已承诺帮助该队友，且点数≤21（对方会发 release，但可能丢包），主动释放承诺
                                if (
                                    _sid_int
                                    and _committed_to_sender == _sid_int
                                    and _started_point is not None
                                    and int(_started_point) <= 21
                                ):
                                    _committed_to_sender = None
                                    _committed_to_sender_set_at = None
                                    play_logger.info(
                                        f"[开局协调] 队友 {data.get('friend_name', f'队友{sender_id}')} 点数={_started_point}≤21，本机主动释放承诺"
                                    )
                            elif data.get("type") == "friend_helped":
                                # 队友已帮助完成平局
                                logger.info(
                                    f"队友 {data.get('friend_name', f'队友{sender_id}')} 已完成平局：目标局={data.get('target_gameid')} 点数={data.get('point')}"
                                )
                                play_logger.debug(f"[平局] 收到队友完成通知，消息体: {data}")
                                done_gameid = data.get("target_gameid") or data.get("gameid")
                                if done_gameid:
                                    try:
                                        _discard_friend_gameid(int(done_gameid))
                                    except (ValueError, TypeError):
                                        pass
                                save_runtime_state()
                            elif data.get("type") == "friend_help_verify_request":
                                await handle_help_verify_request(client, data)
                            elif data.get("type") == "friend_help_verify_result":
                                await handle_help_verify_result(client, data)
                            elif data.get("type") == "pre_game_query":
                                # 队友开局前询问：我能否帮平局？
                                query_amount = data.get("amount")
                                query_id = data.get("query_id")
                                _my_amounts = multi_bonus_list if multi_bonus_enabled else [bonus]
                                if query_amount not in _my_amounts:
                                    logger.debug(f"[开局协调] 询问金额 {query_amount} 不在本机列表，忽略")
                                elif _committed_to_sender is not None and _committed_to_sender != int(sender_id):
                                    logger.debug(f"[开局协调] 已承诺给 {_get_friend_name(_committed_to_sender)}，忽略来自 {_get_friend_name(int(sender_id))} 的询问")
                                elif _committed_to_sender == int(sender_id):
                                    # 同一队友重试询问，重发 commit（携带新 query_id，确保对方能匹配）
                                    _resp_payload = {
                                        "type": "pre_game_commit",
                                        "sender_id": MYID,
                                        "friend_name": MYNAME,
                                        "target_sender_id": sender_id,
                                        "amount": query_amount,
                                        "query_id": query_id,
                                    }
                                    await client.publish(GAME_TOPIC, payload=json.dumps(_resp_payload))
                                    _committed_to_sender_set_at = time_module.time()
                                    logger.debug(f"[开局协调] 已承诺给 {_get_friend_name(int(sender_id))}，重试询问重发 commit(query_id={query_id})")
                                else:
                                    # 在线即可帮忙（等待中/空闲均可加入别人的局）
                                    _resp_payload = {
                                        "type": "pre_game_commit",
                                        "sender_id": MYID,
                                        "friend_name": MYNAME,
                                        "target_sender_id": sender_id,
                                        "amount": query_amount,
                                        "query_id": query_id,
                                    }
                                    await client.publish(GAME_TOPIC, payload=json.dumps(_resp_payload))
                                    _committed_to_sender = int(sender_id)
                                    _committed_to_sender_set_at = time_module.time()
                                    play_logger.info(
                                        f"[开局协调] 已承诺帮助 {data.get('friend_name', f'队友{sender_id}')} 金额={query_amount}"
                                    )
                            elif data.get("type") == "pre_game_commit":
                                # 收到队友对我的承诺
                                target_sid = data.get("target_sender_id")
                                if target_sid == MYID and _pre_game_query_id and data.get("query_id") == _pre_game_query_id:
                                    _committer_name = data.get('friend_name', f'队友{sender_id}')
                                    if _pre_game_commit_event.is_set():
                                        # 已有其他队友承诺，立即释放这个迟到的承诺者
                                        await client.publish(GAME_TOPIC, payload=json.dumps({
                                            "type": "pre_game_release",
                                            "sender_id": MYID,
                                            "friend_name": MYNAME,
                                            "target_helper_id": int(sender_id),
                                            "point": 0,
                                        }))
                                        play_logger.info(
                                            f"[开局协调] {_committer_name} 迟到承诺，已立即释放"
                                        )
                                    else:
                                        _pre_game_committed_helper_id = int(sender_id)
                                        _pre_game_committed_helper_name = _committer_name
                                        _pre_game_commit_event.set()
                                        play_logger.info(
                                            f"[开局协调] {_committer_name} 已承诺帮助"
                                        )
                            elif data.get("type") == "pre_game_release":
                                # 收到解除承诺通知
                                target_helper_id = data.get("target_helper_id")
                                if target_helper_id == MYID and _committed_to_sender == int(sender_id):
                                    _committed_to_sender = None
                                    _committed_to_sender_set_at = None
                                    play_logger.info(
                                        f"[开局协调] {data.get('friend_name', f'队友{sender_id}')} 点数={data.get('point')}≤21，承诺已解除"
                                    )
                            elif data.get("type") == "pre_game_response":
                                pass  # 旧消息类型，忽略
                            else:
                                logger.debug(f"未处理的游戏消息类型: {data.get('type')}")

                    except json.JSONDecodeError:
                        logger.warning(f"收到非JSON协议消息，已忽略: {payload}")
                else:
                    logger.warning(f"未知主题{message.topic}")
        except MqttError as ee:
            logger.error("MQTT异常，准备重连: %s", ee, exc_info=True)
            raise
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            await asyncio.sleep(10)


async def start_game(client: Client = None):
    global _last_personal_stats_at
    sw_flag1 = False
    last_joinable_count = None
    last_joinable_log_at = 0.0
    _last_wr_battle_log_at = 0.0
    _last_wr_afk_log_at = 0.0
    _battle_games_today = 0
    _battle_games_date = datetime.now().date()
    while True:
        g["auto_time"] = is_within_time_ranges(auto_time)
        _purge_stale_friend_gameids()
        is_active = g["auto_time"]
        _cached_public_gameids = []

        # 每日对战计数跨天重置（放最前，保证任何路径都能触发）
        _today = datetime.now().date()
        if _today != _battle_games_date:
            _battle_games_today = 0
            _battle_games_date = _today

        # 非时间段：如果初始胜率足额，也允许对局（需 ENABLED=true）
        win_rate_override = False
        if not is_active and active_enabled and win_rate_min > 0:
            # 每日上限已达：非时间段对战不触发，静默等待次日
            if active_max_games > 0 and _battle_games_today >= active_max_games:
                pass  # win_rate_override 保持 False
            else:
                try:
                    _cached_public_gameids, _wr, _r = await game_state()
                    if _wr >= win_rate_min:
                        win_rate_override = True
                        logger.info(f"当前胜率 {_wr:.1%} ≥ {win_rate_min:.0%}，非时间段激活对局")
                    _now_sp = time_module.time()
                    if _r and client and _now_sp - _last_personal_stats_at >= 300:
                        try:
                            await _publish_alert(client, "personal_stats", {k: _r.get(k) for k in ("wins", "losses", "total", "win_rate", "balance")})
                            _last_personal_stats_at = _now_sp
                        except Exception:
                            pass
                except Exception as _wr_e:
                    logger.debug(f"胜率检查失败: {_wr_e}")

        # 时间段内对战模式：开关开启时，胜率达标则用对战（加入等待局）替代挂机（开新局）（需 ENABLED=true）
        _use_battle_mode = False
        if is_active and active_enabled and win_rate_apply_in_time and win_rate_min > 0:
            try:
                _cached_public_gameids, _wr, _r = await game_state()
                if _wr >= win_rate_min:
                    _use_battle_mode = True
                    _now_ts_wr = time_module.time()
                    if _now_ts_wr - _last_wr_battle_log_at >= 300:
                        play_logger.info(f"时间段内胜率 {_wr:.1%} ≥ {win_rate_min:.0%}，启用对战模式（加入等待局）")
                        _last_wr_battle_log_at = _now_ts_wr
                else:
                    _now_ts_wr = time_module.time()
                    if _now_ts_wr - _last_wr_afk_log_at >= 300:
                        play_logger.info(f"时间段内胜率 {_wr:.1%} < {win_rate_min:.0%}，降级为挂机模式（多金额开新局）")
                        _last_wr_afk_log_at = _now_ts_wr
                _now_sp = time_module.time()
                if _r and client and _now_sp - _last_personal_stats_at >= 300:
                    try:
                        await _publish_alert(client, "personal_stats", {k: _r.get(k) for k in ("wins", "losses", "total", "win_rate", "balance")})
                        _last_personal_stats_at = _now_sp
                    except Exception:
                        pass
            except Exception as _wr_e:
                logger.debug(f"时间段内胜率检查失败: {_wr_e}")

        if is_active or win_rate_override:
            if not sw_flag1:
                sw_flag1 = True
                logger.info("进入挂机时间段，开始自动运行" if is_active else f"胜率足额，开始非时间段对局")

            try:
                # 自己没有开局时才进行监控和开局（胜率模式：等待中也算空闲，可加入别人的局）
                waiting_game_exists = False
                _did_battle = False
                try:
                    waiting_game_exists = await has_waiting_game()
                except Exception as e:
                    logger.warning(f"检查等待中游戏状态失败，按无等待游戏处理: {e}")

                # 先计算 _is_battle（含 MAX_GAMES 降级），再用它决定是否跳过等待中的局
                _is_battle = _use_battle_mode or (win_rate_override and not is_active)
                # 每日上限检查：时间段内对战达到上限时降级为挂机模式
                if _is_battle and active_max_games > 0 and _battle_games_today >= active_max_games:
                    play_logger.info(f"[对战] 今日已完成 {_battle_games_today}/{active_max_games} 局，降级为挂机模式")
                    _is_battle = False
                    _use_battle_mode = False

                if not waiting_game_exists or win_rate_override or _is_battle:
                    if _cached_public_gameids:
                        public_gameids = _cached_public_gameids
                    else:
                        public_gameids, _, _r = await game_state()
                        _now_sp = time_module.time()
                        if _r and client and _now_sp - _last_personal_stats_at >= 300:
                            try:
                                await _publish_alert(client, "personal_stats", {k: _r.get(k) for k in ("wins", "losses", "total", "win_rate", "balance")})
                                _last_personal_stats_at = _now_sp
                            except Exception:
                                pass

                    # 多金额模式：查询所有金额，按策略选最优分段
                    # 对战模式用独立金额列表（battle_bonus_list），挂机模式用 AFK 金额列表
                    if _is_battle and battle_bonus_list:
                        monitor_amounts = battle_bonus_list
                    else:
                        monitor_amounts = multi_bonus_list if (multi_bonus_enabled and multi_bonus_list) else [bonus]
                    joinable_games = await get_joinable_games_by_amount(monitor_amounts)

                    def _amount_key(amt):
                        return str(int(amt)) if isinstance(amt, (int, float)) and float(amt).is_integer() else str(amt)

                    _friend_gameids_str = {str(gid) for gid in active_friend_gameids}

                    def _count_friend(amt):
                        # 页面 join 表单不暴露 gameid，改用 MQTT 跟踪的金额映射统计
                        # 排除自己的等待局（可能通过 sync_response 误入 active_friend_gameids）
                        return sum(
                            1 for gid in active_friend_gameids
                            if _friend_gameid_amounts.get(gid) == amt
                            and (_own_waiting_gameid is None or gid != _own_waiting_gameid)
                        )

                    def _count_stranger(amt):
                        return sum(
                            1 for _entry in joinable_games.get(_amount_key(amt), [])
                            if str(_entry.get('gameid', '')) not in _friend_gameids_str
                        )

                    friend_counts = {amt: _count_friend(amt) for amt in monitor_amounts}
                    stranger_counts = {amt: _count_stranger(amt) for amt in monitor_amounts}

                    # 跳过队友已≥2的分段（满员，不再加入）；对战模式只要有非队友局可加入就合格
                    # 对战/挂机模式均排除队友已 21点封山 的金额段（等那局结束才解放）
                    _battle_blocked_amounts = set(_friend_21_blocked.values())
                    if _is_battle:
                        eligible_amounts = [
                            amt for amt in monitor_amounts
                            if stranger_counts[amt] > 0 and amt not in _battle_blocked_amounts
                        ]
                    else:
                        eligible_amounts = [
                            amt for amt in monitor_amounts
                            if friend_counts[amt] < 2 and amt not in _battle_blocked_amounts
                        ]

                    now_ts = time_module.time()
                    counts_str = ' | '.join(
                        f'{a}魔力:路人{stranger_counts[a]}/队友{friend_counts[a]}{"[封山]" if a in _battle_blocked_amounts else ""}'
                        for a in monitor_amounts
                    )

                    if not eligible_amounts:
                        if counts_str != last_joinable_count:
                            if _is_battle:
                                play_logger.info(f"当前无可加入对局，本轮跳过 [{counts_str}]")
                            elif _battle_blocked_amounts and all(amt in _battle_blocked_amounts for amt in monitor_amounts):
                                play_logger.info(f"所有金额段队友封山等待，本轮跳过 [{counts_str}]")
                            elif _battle_blocked_amounts:
                                play_logger.info(f"可用金额段队友已满或封山，本轮跳过 [{counts_str}]")
                            else:
                                play_logger.info(f"所有金额段队友已满（≥2人），本轮跳过 [{counts_str}]")
                            last_joinable_count = counts_str
                            last_joinable_log_at = now_ts
                        elif now_ts - last_joinable_log_at >= max(300, sleep * 4):
                            logger.debug(f"金额监控无变化：{counts_str}")
                            last_joinable_log_at = now_ts
                    else:
                        # 选段优先级：路人少 > 队友多（优先凑满2人互配） > MYID平衡分配（防止多实例都选最高金额）
                        selected_amount = _select_amount_myid_balanced(
                            eligible_amounts,
                            lambda a: stranger_counts[a],
                            lambda a: friend_counts[a],
                        )
                        sel_friend = friend_counts[selected_amount]
                        sel_stranger = stranger_counts[selected_amount]

                        if counts_str != last_joinable_count:
                            if multi_bonus_enabled and len(monitor_amounts) > 1:
                                logger.info(
                                    f"多金额监控 [{counts_str}]，选择 {selected_amount} 金额"
                                    f"（路人={sel_stranger} 队友={sel_friend}）"
                                )
                            else:
                                logger.info(
                                    f"当前监控 {selected_amount} 金额：路人={sel_stranger} 队友={sel_friend}"
                                )
                            last_joinable_count = counts_str
                            last_joinable_log_at = now_ts
                        elif now_ts - last_joinable_log_at >= max(300, sleep * 4):
                            logger.debug(f"金额监控无变化：{counts_str}")
                            last_joinable_log_at = now_ts

                        if not _is_battle:
                            # 挂机模式：自己开新局（仅在时间段内）
                            if is_active:
                                await start_my_game(client, public_gameids, selected_amount)
                        else:
                            # 对战模式（时间段内胜率达标 或 时间段外胜率足额）：加入别人的等待局
                            _joined = await _join_existing_game(joinable_games, selected_amount)
                            if _joined:
                                _battle_games_today += 1
                                _did_battle = True
                _eff_sleep = active_sleep if _did_battle else sleep
                delta = random.randint(-_eff_sleep // 10, _eff_sleep // 10) if _eff_sleep >= 10 else 0
                await asyncio.sleep(max(1, _eff_sleep + delta))
            except MqttError as ee:
                logger.error("MQTT异常，准备重连: %s", ee, exc_info=True)
                raise
            except aiomqtt.exceptions.MqttCodeError as ee:
                logger.error("MQTT异常，准备重连: %s", ee, exc_info=True)
                raise

            except Exception as e:
                logger.error("任务执行失败：%s", e, exc_info=True)
                await asyncio.sleep(5)
        else:
            if sw_flag1:
                sw_flag1 = False
                logger.info(
                    "当前为休息时间段，暂停自动运行"
                )
            await asyncio.sleep(10)


async def publish_state_loop(client: Client):
    global _own_waiting_gameid, _own_waiting_amount, _mqtt_client_ref
    global _committed_to_sender, _committed_to_sender_set_at
    global _last_personal_stats_at
    _mqtt_client_ref = client
    _COMMIT_TTL = 20  # 承诺超过20秒没被用/释放，自动清除
    interval = max(10, sleep // 2)
    while True:
        try:
            # 超时清理：承诺超过 TTL 未被用到，可能是被选中者非本机，主动释放
            if _committed_to_sender is not None and _committed_to_sender_set_at is not None:
                if time_module.time() - _committed_to_sender_set_at > _COMMIT_TTL:
                    play_logger.info(
                        f"[开局协调] 承诺给 {_get_friend_name(_committed_to_sender)} 已超过{_COMMIT_TTL}秒未用，自动释放"
                    )
                    _committed_to_sender = None
                    _committed_to_sender_set_at = None
            page_state = await get_page_state()
            _page_waiting = page_state.get("waiting", False)
            # B2修复：页面已不在等待时同步清除本机等待局记录，防止 pre_game_response 误报 can_help=False
            if not _page_waiting and _own_waiting_gameid is not None:
                _own_waiting_gameid = None
                _own_waiting_amount = None
            # 页面的 gameid 在"等待对手加入"状态下不暴露，用 _own_waiting_gameid 补全
            _page_gameid = page_state.get("gameid") or (_own_waiting_gameid if _page_waiting else None)
            payload = {
                "type": "friend_state",
                "sender_id": MYID,
                "friend_name": MYNAME,
                "waiting": _page_waiting,
                "gameid": _page_gameid,
                "amount": _own_waiting_amount,  # 带上本机当前等待局的金额，辅助队友多金额识别
            }
            friend_states[MYID] = {
                "waiting": bool(payload["waiting"]),
                "gameid": _page_gameid,
                "updated_at": time_module.time(),
            }
            save_runtime_state()
            await client.publish(STATE_TOPIC, payload=json.dumps(payload))

            # 保底上报：start_game 非活跃时（休息时段），30分钟兜底上报一次
            if time_module.time() - _last_personal_stats_at >= 1800:
                try:
                    _, _, _record = await game_state()
                    if _record:
                        await _publish_alert(client, "personal_stats", {k: _record.get(k) for k in ("wins", "losses", "total", "win_rate", "balance")})
                        _last_personal_stats_at = time_module.time()
                except Exception as _se:
                    logger.debug(f"个人战绩保底上报失败: {_se}")
        except Exception as e:
            logger.warning(f"上报页面状态失败: {e}")

        # 有待对局时加快轮询，尽快心跳游戏结束事件
        _effective_interval = max(5, sleep // 6) if _own_waiting_gameid else interval
        await asyncio.sleep(_effective_interval)


def is_within_time_ranges(time_ranges):
    now = datetime.now().time()
    for start_str, end_str in time_ranges:
        start = time_class.fromisoformat(start_str)
        end = time_class.fromisoformat(end_str)
        if start <= now <= end:
            return True
    return False


async def _validate_friend_gameids_on_startup():
    if not active_friend_gameids:
        return
    try:
        live_gameids, _, _r = await game_state()
        live_set = set(live_gameids)
        stale = [gid for gid in list(active_friend_gameids) if gid not in live_set]
        if stale:
            for gid in stale:
                _discard_friend_gameid(gid)
            logger.info(
                f"启动扫描：清理 {len(stale)} 个已完成的队友局编号，剩余 {len(active_friend_gameids)} 个"
            )
            save_runtime_state()
        else:
            logger.info(
                f"启动扫描：持久化的 {len(active_friend_gameids)} 个队友局编号均仍在线"
            )
    except Exception as e:
        logger.warning(f"启动扫描队友局状态失败，跳过: {e}")


async def main():
    logger.info("主程序启动中")
    logger.info(f"当前账号编号={MYID}，MQTT主机地址={'已配置' if MQTT_HOST else '未配置'}")

    # 启动扫描：清理持久化中已完成的队友局编号
    await _validate_friend_gameids_on_startup()

    # 检查 MQTT 配置
    if not MQTT_HOST:
        logger.warning("MQTT 服务器地址未配置，将仅运行本地游戏功能")
        # 仅运行游戏功能，不连接 MQTT
        try:
            await asyncio.gather(start_game(None))
        except KeyboardInterrupt:
            logger.info("程序被用户中断")
        except Exception as e:
            logger.error(f"游戏运行异常: {e}", exc_info=True)
        return

    # 有 MQTT 配置，尝试连接
    # 解析主机和端口
    if ":" in MQTT_HOST:
        mqtt_hostname, mqtt_port_str = MQTT_HOST.split(":", 1)
        mqtt_port = int(mqtt_port_str)
    else:
        mqtt_hostname = MQTT_HOST
        mqtt_port = 1883

    client = Client(
        hostname=mqtt_hostname,
        port=mqtt_port,
        username=MQTT_USER,
        password=MQTT_PASSWORD,
        identifier=f"{MYID}_{hash(time_module.time())}",
        keepalive=20,
    )
    interval = 5

    while True:
        active_tasks = []
        try:
            async with client:
                await client.subscribe(HELP_TOPIC)
                await client.subscribe(GAME_TOPIC)
                await client.subscribe(STATE_TOPIC)

                # 启动时广播同步请求，让其他在线容器即时回复完整的活跃局列表
                if MYID > 0:
                    try:
                        _sync_req = {
                            "type": "sync_request",
                            "sender_id": MYID,
                            "friend_name": MYNAME,
                        }
                        await client.publish(STATE_TOPIC, payload=json.dumps(_sync_req))
                        logger.info("已广播启动同步请求，等待队友回复")
                    except Exception as _e:
                        logger.warning(f"发送启动同步请求失败: {_e}")

                active_tasks = [
                    asyncio.create_task(listen(client)),
                    asyncio.create_task(start_game(client)),
                    asyncio.create_task(publish_state_loop(client)),
                ]
                done, pending = await asyncio.wait(
                    active_tasks, return_when=asyncio.FIRST_EXCEPTION
                )
                # 取消所有尚未完成的任务
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                # 重新抛出已完成任务中的异常
                for task in done:
                    if not task.cancelled() and task.exception():
                        raise task.exception()
        except MqttError:
            logger.error(f"MQTT连接断开，{interval} 秒后重连...")
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(e, exc_info=True)
        finally:
            # 确保本轮所有任务都已取消
            for task in active_tasks:
                if not task.done():
                    task.cancel()
            if active_tasks:
                await asyncio.gather(*active_tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序运行出错: {e}", exc_info=True)
        # 等待一段时间后退出，让 Supervisor 可以重启
        import time
        time.sleep(5)
