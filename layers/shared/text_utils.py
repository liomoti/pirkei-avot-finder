import re


# Remove Hebrew niqqud (cantillation marks and vowel points) in the U+0591–U+05C7 range
def remove_niqqud(text):
    return re.sub(r'[\u0591-\u05C7]', '', text)
