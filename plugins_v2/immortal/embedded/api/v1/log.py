"""Bounded plugin-local logs, without reading platform files."""
from fastapi import APIRouter, Depends
from ..deps import get_current_user
from ...schemas.response import success
from ...utils.log import recent_lines, total_lines

router = APIRouter()


@router.get('/')
def get_logs(page_size: int = 100, before_line_no: int | None = None,
             after_line_no: int | None = None, user=Depends(get_current_user)):
    page_size = max(1, min(page_size, 500))
    rows = recent_lines()
    selected = [row for row in rows if (before_line_no is None or row['line_no'] < before_line_no)
                and (after_line_no is None or row['line_no'] > after_line_no)]
    items = selected[-page_size:]
    return success({'items': items, 'total_lines': total_lines(), 'page_size': page_size,
                    'before_line_no': before_line_no, 'after_line_no': after_line_no,
                    'oldest_line_no': items[0]['line_no'] if items else None,
                    'latest_line_no': items[-1]['line_no'] if items else None,
                    'has_more_before': len(selected) > len(items), 'has_more_after': False})
