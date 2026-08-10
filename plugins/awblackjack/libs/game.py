from __future__ import annotations
import asyncio
import random
import re
import aiohttp
from bs4 import BeautifulSoup
from libs.log import logger, play_logger
from libs.toml import read
amount = 0
config = read('config/config.toml') or read('config/config_example.toml') or {}
basic_config = config.get('BASIC', {})
language = basic_config.get('LANGUAGE', 'zh-CN,zh')
cookie = basic_config.get('COOKIE', '')
sec_ch_ua = basic_config.get(
    'SEC_CH_UA', '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
)
sec_fetch_dest = basic_config.get('SEC_FETCH_DEST', 'document')
sec_fetch_mode = basic_config.get('SEC_FETCH_MODE', 'cors')
user_agent = basic_config.get(
    'USER_AGENT',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
)
url = 'https://springsunday.net/blackjack.php'
headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': language,
    'Cookie': cookie,
    'Priority': 'u=0, i',
    'Refer': 'https://springsunday.net/blackjack.php',
    'Sec-Ch-Ua': sec_ch_ua,
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': sec_fetch_dest,
    'Sec-Fetch-Mode': sec_fetch_mode,
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'upgrade-insecure-requests': '1',
    'User-Agent': user_agent,
}

def extract_form_params(soup: BeautifulSoup) -> dict[str, dict[str, str]]:
    result = {}
    for form in soup.find_all('form'):
        submit_button = form.find('input', {'type': 'submit'})
        submit_text = submit_button.get('value', '').strip() if submit_button else 'No Submit Button'
        params = {}
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            value = input_tag.get('value')
            if name and value:
                params[name] = value
        if params:
            result[submit_text] = params
    return result

def extract_forms_with_submit(soup: BeautifulSoup) -> list[tuple[str, dict[str, str]]]:
    result = []
    for form in soup.find_all('form'):
        submit_button = form.find('input', {'type': 'submit'})
        submit_text = submit_button.get('value', '').strip() if submit_button else 'No Submit Button'
        params = {}
        for input_tag in form.find_all('input'):
            name = input_tag.get('name')
            value = input_tag.get('value')
            if name and value:
                params[name] = value
        if params:
            result.append((submit_text, params))
    return result

def extract_end_button_gameid(soup: BeautifulSoup) -> str | None:
    end_button_labels = {'不再抓了，结束', '结束'}
    for form in soup.find_all('form'):
        submit_button = form.find('input', {'type': 'submit'})
        submit_text = submit_button.get('value', '').strip() if submit_button else ''
        if submit_text not in end_button_labels:
            continue
        gameid_input = form.find('input', {'name': 'gameid'})
        if gameid_input:
            gameid_value = gameid_input.get('value')
            if gameid_value:
                return gameid_value
    return None

def _normalize_amount_value(amount_value) -> str | None:
    if amount_value in (None, ''):
        return None
    amount_text = ''.join(str(amount_value).split(','))
    amount_text = amount_text.strip()
    if not amount_text:
        return None
    try:
        amount_number = float(amount_text)
    except (TypeError, ValueError):
        return None
    if amount_number.is_integer():
        return str(int(amount_number))
    return f'{amount_number:.1f}'

def _extract_amount_from_row(row) -> str | None:
    cells = row.find_all('td')
    if not cells:
        return None
    for cell in cells:
        text = ''.join(cell.get_text(' ', strip=True).split(','))
        if not text:
            continue
        try:
            amount_number = float(text)
        except ValueError:
            continue
        if amount_number.is_integer():
            return str(int(amount_number))
        return f'{amount_number:.1f}'
    return None

def extract_joinable_games_by_amount(
    soup: BeautifulSoup,
    allowed_amounts: set[str] | None = None,
) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    allowed_amounts = allowed_amounts or set()

    extracted_forms = extract_forms_with_submit(soup)
    for submit_text, params in extracted_forms:
        if submit_text != '加入':
            continue
        normalized_amount = _normalize_amount_value(params.get('amount'))
        if not normalized_amount:
            continue
        if allowed_amounts and normalized_amount not in allowed_amounts:
            continue
        normalized_params = dict(params)
        normalized_params['amount'] = normalized_amount
        result.setdefault(normalized_amount, []).append(normalized_params)

    return result
async def game(data):
    err = 0
    while err < 3:
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(10)) as session:
                async with session.post(url, headers=headers, data=data) as response:
                    if response.status != 200:
                        raise Exception(response.status)
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    _opp_match = re.search(r'你的对手是\s*(.+?)，', soup.get_text(' '))
                    opponent_name = _opp_match.group(1).strip() if _opp_match else None
                    forms = extract_form_params(soup)
                    end_button_gameid = extract_end_button_gameid(soup)
                    if end_button_gameid:
                        forms.setdefault('结束', {}).setdefault('gameid', end_button_gameid)
                        forms.setdefault('不再抓了，结束', {}).setdefault('gameid', end_button_gameid)
                    element = soup.select_one('#details b')
                    if element:
                        text = element.get_text(strip=True)
                        try:
                            point_str = text.split('=')[-1].strip()
                            if point_str == '21或更多':
                                logger.info('可能超过21点，按22点计算')
                                point = 22
                            elif point_str:
                                point = int(point_str)
                            else:
                                raise ValueError('点数字段为空')
                            form = soup.find('form')
                            if form:
                                parent_td = form.find_parent('td')
                                text_before_form = ''
                                if parent_td:
                                    text_before_form = ''.join(parent_td.find_all(string=True, recursive=False)).strip()
                                if text_before_form:
                                    play_logger.info(f'你有{point}点，{text_before_form}')
                        except Exception as e:
                            logger.error(f'{e}', exc_info=True)
                            logger.error('未能获取到页面点数，返回22')
                            point = 22
                        return point, forms, opponent_name
                    fallback = soup.select_one('#outer table td') or soup.select_one('form strong')
                    if fallback:
                        logger.warning(fallback.text.strip())
                    logger.error('未能获取到页面点数，返回空值')
                    return None, forms, opponent_name
        except asyncio.TimeoutError as e:
            logger.error(f'请求超时{err + 1}次：{e}', exc_info=(err >= 2))
            err += 1
            await asyncio.sleep(2 ** err)
        except Exception as e:
            logger.error(f'请求未知错误{err + 1}次：{e}', exc_info=(err >= 2))
            err += 1
            _code = e.args[0] if e.args else None
            _delay = 10 if _code == 503 else (2 ** err)
            await asyncio.sleep(_delay)
    return None, {}, None

async def join_game(data: dict) -> tuple[int | None, str | None, dict[str, dict[str, str]], str | None]:
    point, forms, opponent_name = await game(data)
    if '继续旧游戏' in forms:
        await asyncio.sleep(1)
        point, forms, opp_new = await game(forms['继续旧游戏'])
        opponent_name = opponent_name or opp_new
    if point is None and '再抓一张' in forms:
        await asyncio.sleep(1)
        point, forms, opp_new = await game(forms['再抓一张'])
        opponent_name = opponent_name or opp_new
    gameid = _extract_gameid_from_forms(forms) or data.get('gameid')
    return point, gameid, forms, opponent_name

def _extract_gameid_from_forms(forms):
    if not isinstance(forms, dict):
        return None
    for key in ('结束', '再抓一张', '不再抓了，结束', '继续旧游戏'):
        params = forms.get(key)
        if isinstance(params, dict) and params.get('gameid'):
            return params.get('gameid')
    for params in forms.values():
        if isinstance(params, dict) and params.get('gameid'):
            return params.get('gameid')
    return None

def _has_resumable_game(forms) -> bool:
    if not isinstance(forms, dict):
        return False
    if _extract_gameid_from_forms(forms):
        return True
    resumable_actions = {'玩这一局', '再抓一张', '不再抓了，结束', '继续旧游戏', '刷新'}
    return any(action in forms for action in resumable_actions)
async def do_game(data: dict, remain_point=18, log_type='开局', resume_attempts=0):
    point, forms, _ = await game(data)
    if '继续旧游戏' in forms:
        if resume_attempts >= 3:
            resumed_gameid = _extract_gameid_from_forms(forms) or data.get('gameid')
            logger.warning(f'[{log_type}] 继续旧游戏次数过多，停止恢复 (对局编号={resumed_gameid})')
            return None, resumed_gameid
        await asyncio.sleep(1)
        old_point, old_gameid = await do_game(forms['继续旧游戏'], 17, '未知', resume_attempts + 1)
        logger.info(f'[{log_type}] 旧游戏已清理 对局编号={old_gameid} 点数={old_point}')
        await asyncio.sleep(2)
        return await do_game(data, remain_point, log_type, resume_attempts + 1)
    if not point:
        if _has_resumable_game(forms):
            resumed_gameid = _extract_gameid_from_forms(forms) or data.get('gameid')
            if resume_attempts >= 5:
                logger.warning(f'[{log_type}] 页面重试次数过多，放弃 (对局编号={resumed_gameid})')
                return None, resumed_gameid
            logger.warning(f'[{log_type}] 页面暂未返回点数，保留当前局继续处理 (对局编号={resumed_gameid})')
            await asyncio.sleep(1)
            resumed_data = dict(data)
            if resumed_gameid:
                resumed_data['gameid'] = resumed_gameid
            resumed_data.pop('start', None)
            return await do_game(resumed_data, remain_point, log_type, resume_attempts + 1)
        if forms:
            logger.error(f'[{log_type}] 未识别页面表单: {forms}')
        return None, None
    current_gameid = _extract_gameid_from_forms(forms) or data.get('gameid')
    while point < remain_point:
        logger.info(f'[{log_type}]当前点数{point}，继续抓牌 (对局编号={current_gameid})')
        if '再抓一张' not in forms:
            break
        await asyncio.sleep(random.randint(1, 5))
        point, forms, _ = await game(forms['再抓一张'])
        current_gameid = _extract_gameid_from_forms(forms) or current_gameid
    logger.info(f'[{log_type}]当前点数{point}，结束 (对局编号={current_gameid})')
    if '不再抓了，结束' in forms:
        point, forms, _ = await game(forms['不再抓了，结束'])
        current_gameid = _extract_gameid_from_forms(forms) or current_gameid
    return point, current_gameid
async def game_state():
    error = 0
    state = []
    while error < 3:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f'网络状态错误 {response.status}')
                        raise Exception(response.status)
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    game_table = soup.find('table', {'id': 'game_available'})
                    if game_table:
                        rows = game_table.find_all('tr')[1:]
                        for row in rows:
                            form = row.find('form')
                            if not form:
                                continue
                            gameid_input = form.find('input', {'name': 'gameid'})
                            if not gameid_input:
                                logger.debug('页面未暴露对局编号，跳过该表单')
                                continue
                            try:
                                gameid = int(gameid_input.get('value', 0))
                            except (ValueError, TypeError):
                                continue
                            if gameid > 0:
                                state.append(gameid)
                                logger.debug(f'发现游戏 对局编号={gameid}')
                    win_rate = soup.select_one('table:nth-of-type(2) tr:nth-of-type(5) td:nth-of-type(2)')
                    win_rate_num = 0.5
                    if win_rate:
                        try:
                            win_rate_num = float(win_rate.text.strip('%')) / 100
                        except (ValueError, AttributeError):
                            pass
                    # 解析个人记录：胜局/输局/游戏次数/+/-
                    personal_record = {}
                    try:
                        stats_table = soup.select('table')[1]
                        rows = stats_table.find_all('tr')
                        def _parse_int(text):
                            return int(text.strip().replace(',', ''))
                        if len(rows) >= 2:
                            personal_record['wins'] = _parse_int(rows[1].find_all('td')[1].text)
                        if len(rows) >= 3:
                            personal_record['losses'] = _parse_int(rows[2].find_all('td')[1].text)
                        if len(rows) >= 4:
                            personal_record['total'] = _parse_int(rows[3].find_all('td')[1].text)
                        if len(rows) >= 6:
                            personal_record['balance'] = _parse_int(rows[5].find_all('td')[1].text)
                        personal_record['win_rate'] = win_rate_num
                    except Exception:
                        pass
                    return state, win_rate_num, personal_record
            except Exception as e:
                error += 1
                logger.error(f'请求错误{error}次：{e}', exc_info=(error >= 3))
                _status = getattr(e.args[0], 'status', None) if e.args else None
                _code = e.args[0] if e.args else None
                _delay = 10 if _code == 503 else (2 ** error)
                await asyncio.sleep(_delay)
    return state, 0.5, {}
async def get_page_state() -> dict:
    error = 0
    while error < 3:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f'网络状态错误 {response.status}')
                        raise Exception(response.status)
                    html = await response.text()
                    soup = BeautifulSoup(html, 'lxml')
                    waiting = bool(soup.select("input[value='刷新']"))
                    forms = extract_form_params(soup)
                    current_gameid = _extract_gameid_from_forms(forms)
                    if not current_gameid:
                        form = soup.find('form')
                        if form:
                            gameid_input = form.find('input', {'name': 'gameid'})
                            if gameid_input:
                                current_gameid = gameid_input.get('value')
                    return {
                        'waiting': waiting,
                        'gameid': int(current_gameid) if current_gameid else None,
                    }
            except Exception as e:
                error += 1
                logger.error(f'页面状态请求错误{error}次：{e}', exc_info=(error >= 3))
                _code = e.args[0] if e.args else None
                _delay = 10 if _code == 503 else (2 ** error)
                await asyncio.sleep(_delay)
    return {'waiting': False, 'gameid': None}

async def get_joinable_games_by_amount(allowed_amounts=None) -> dict[str, list[dict[str, str]]]:
    error = 0
    normalized_amounts = {
        normalized
        for normalized in (_normalize_amount_value(raw_amount) for raw_amount in (allowed_amounts or []))
        if normalized
    }
    while error < 3:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f'网络状态错误 {response.status}')
                        raise Exception(response.status)
                    soup = BeautifulSoup(await response.text(), 'lxml')
                    return extract_joinable_games_by_amount(soup, normalized_amounts)
            except Exception as e:
                error += 1
                logger.error(f'获取可加入对局请求错误{error}次：{e}', exc_info=(error >= 3))
                _code = e.args[0] if e.args else None
                _delay = 10 if _code == 503 else (2 ** error)
                await asyncio.sleep(_delay)
    return {}
async def join_random_game_by_amount(amount) -> tuple[int | None, str | None, dict[str, str] | None, dict, str | None]:
    normalized_amount = _normalize_amount_value(amount)
    if not normalized_amount:
        logger.warning(f'无效的目标金额，无法随机加入: {amount}')
        return None, None, None, {}, None
    joinable_games = await get_joinable_games_by_amount([normalized_amount])
    candidates = joinable_games.get(normalized_amount, [])
    if not candidates:
        logger.debug(f'当前无可加入对局 金额={normalized_amount}')
        return None, None, None, {}, None
    candidate = random.choice(candidates)
    join_payload = {key: value for key, value in dict(candidate).items() if value not in (None, '')}
    point, gameid, forms, opponent_name = await join_game(join_payload)
    return point, gameid, candidate, forms, opponent_name

async def has_waiting_game() -> bool:
    error = 0
    while error < 3:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            try:
                async with session.get(url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f'网络状态错误 {response.status}')
                        raise Exception(response.status)
                    soup = BeautifulSoup(await response.text(), 'lxml')
                    # 等待对手加入（刷新按钮）
                    if soup.select("input[value='刷新']"):
                        return True
                    # 游戏进行中（可以抓牌/停牌/继续旧游戏），同样算有活跃局
                    if soup.select("input[value='再抓一张'], input[value='不再抓了，结束'], input[value='继续旧游戏']"):
                        return True
                    return False
            except Exception as e:
                error += 1
                logger.error(f'检查等待中游戏请求错误{error}次：{e}', exc_info=(error >= 3))
                _code = e.args[0] if e.args else None
                _delay = 10 if _code == 503 else (2 ** error)
                await asyncio.sleep(_delay)
    return False
