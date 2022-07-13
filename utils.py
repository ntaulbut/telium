from time import sleep
from typing import List
from random import choice
from enum import Enum

enable_text_delay = True


def disable_text_delay():
    global enable_text_delay
    enable_text_delay = False


class Dialogue:
    def __init__(self, *variations):
        self.variations = variations

    def __str__(self):
        return choice(self.variations)

    def format(self, *args, **kwargs):
        return self.__str__().format(*args, **kwargs)


class LogLevel(Enum):
    VERBOSE = 1
    INFO = 2
    ERROR = 3
    NONE = 100


class Logger:
    def __init__(self, level = LogLevel.NONE):
        self.level: LogLevel = level

    def log(self, text: str, level: LogLevel = LogLevel.INFO):
        if level.value >= self.level.value:
            print(f"<{level.name}> {text}")


def cprint(text: str, character_delay: float = .02, short_delay: float = .2,
           long_delay: float = .4, end: str = "\n"):
    """Prints text one character at a time.

    Args:
        text (str): Text to print.
        character_delay (float, optional): The delay between printing characters. Defaults to .02.
        short_delay (float, optional): The delay after printing a comma. Defaults to .2.
        long_delay (float, optional): The delay after printing a full stop or semicolon. Defaults to .4.
        end (str, optional): Character to append to the end of the text. Defaults to "\n".
    """
    if enable_text_delay:
        for char in str(text):
            print(char, end="", flush=True)
            if char in {".", ";", ":", "?", "!"}:
                sleep(long_delay)
            elif char == ",":
                sleep(short_delay)
            else:
                sleep(character_delay)
        print(end, end="")
    else:
        print(text, end=end)


def sent_concat(words: List[str]) -> str:
    """Concatenates a list of words into a sentence with commas and 'and'.

    Args:
        words (list): list of words to convert.

    Returns:
        str: Words concatenated into a sentence.
    """
    length: int = len(words)
    if length > 1:
        words[length-1] = "and " + words[length-1]
    return ", ".join(words) if length > 2 else " ".join(words)


def yes_or_no(question, default: bool = False) -> bool:
    """Ask a yes or no question.

    Args:
        question (str): The prompt to use.
        default (bool, optional): The default option. Defaults to False.

    Returns:
        bool: The users's response, True for yes and False for no.
    """
    cprint(f"{question} ({['yes','YES'][default]}/{['NO', 'no'][default]})")
    answer = input(">").lower()
    if answer in {"yes", "y"}:
        return True
    elif answer in {"no", "n"}:
        return False
    else:
        return default


def int_input(prompt) -> int:
    """Prompt the user until they give a valid integer."""
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            cprint("You must enter a whole number.")
