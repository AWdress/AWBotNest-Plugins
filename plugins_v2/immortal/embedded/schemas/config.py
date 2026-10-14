from typing import List, Any, Dict, Union

from pydantic import BaseModel


class JsonPayload(BaseModel):
    key: str
    payload: Union[List[dict], Dict[str, Any]]
