"""Pure identifier parsing from the supplied source; no AI or bot execution."""
import re

FC2_PATTERN = re.compile(r'(?<![A-Za-z0-9])(FC2)(?:[-_\s]*(PPV))?[-_\s]*(\d{3,8})(?![A-Za-z0-9])', re.I)
GENERAL_PATTERN = re.compile(r'(?<![A-Za-z0-9])(?:\d{2,6})?([A-Za-z]{1,10})[-_\s]?(\d{2,6})(?:[A-Za-z]{1,5})?(?![A-Za-z0-9])', re.I)
SEPARATOR_PATTERN = re.compile(r'[\u3000\u3001\u3002\uff0c\uff1b,;\n\r\t\s]+')


def normalize_movie_number_text(text):
    if not text:
        return ''
    normalized = FC2_PATTERN.sub(lambda match: f'FC2-{match.group(3)}', text)
    def replace(match):
        return match.group(0) if match.group(1).lower() == 'ppv' else f'{match.group(1).upper()}-{match.group(2)}'
    return GENERAL_PATTERN.sub(replace, normalized)


def extract_movie_numbers(text):
    normalized = normalize_movie_number_text(text)
    values = [f'FC2-{digits}' for _, _, digits in FC2_PATTERN.findall(normalized)]
    values.extend(f'{prefix.upper()}-{suffix}' for prefix, suffix in GENERAL_PATTERN.findall(normalized) if prefix.lower() != 'ppv')
    return list(dict.fromkeys(values))


def extract_primary_movie_number(*texts):
    for text in texts:
        values = extract_movie_numbers(text or '')
        if values:
            return values[0]
    return None


def looks_like_movie_number_list(text):
    values = extract_movie_numbers(text)
    if not values:
        return False
    cleaned = normalize_movie_number_text(text)
    for value in values:
        for candidate in (value, value.replace('-', ''), value.replace('-', ' ')):
            cleaned = cleaned.replace(candidate, ' ')
    return len(values) >= 2 or len(SEPARATOR_PATTERN.sub('', cleaned)) <= 12
