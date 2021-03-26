import io
from typing import Optional

from PIL.Image import Image
from requests import get
from requests.exceptions import MissingSchema


class ColumnError(Exception):
    pass


def flat(some_list: list[list]) -> list:
    return [item for sublist in some_list for item in sublist]


def get_image_height_in_pixels(url: str) -> Optional[int]:
    try:
        img_data = get(url).content
    except MissingSchema:
        return None
    im = Image.open(io.BytesIO(img_data))
    return im.size[1]
