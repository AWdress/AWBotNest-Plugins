"""Lightweight helpers for reading the Discuz sign-in control."""

import re


_CHECKIN_CONTROL_RE = re.compile(
    r'<(?:a|button)\b[^>]*(?:ddpc_sign_btn|class=["\'][^"\']*sign[^"\']*btn)[^>]*>'
    r'(?P<text>.*?)</(?:a|button)>',
    re.IGNORECASE | re.DOTALL,
)


def checkin_state(content):
    """Return ``signed``, ``unsigned`` or ``unknown`` from the sign control."""
    controls = []
    for match in _CHECKIN_CONTROL_RE.finditer(str(content or '')):
        controls.append(re.sub(r'<[^>]+>', '', match.group('text')).strip())
    if any('未签到' in text or '点击签到' in text for text in controls):
        return 'unsigned'
    if any('今日已签到' in text or '已签到' == text for text in controls):
        return 'signed'
    return 'unknown'
