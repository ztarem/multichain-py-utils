import random
import string


def rand_string(size: int, is_hex: bool) -> str:
    chars = string.hexdigits if is_hex else string.printable
    return ''.join(random.choices(chars, k=size))
