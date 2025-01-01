import re


def remove_niqqud(text):
    return re.sub(r'[\u0591-\u05C7]', '', text)