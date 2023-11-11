import json
from time import sleep
from typing import List, Dict
from enum import Enum
from colorama import Fore, Style
from glob import glob
from pathlib import Path

DIALOGUE_FILE = "data/dialogue.json"

enable_text_delay = True


class Language(Enum):
    ENGLISH = "en"


class LogLevel(Enum):
    VERBOSE = 1
    INFO = 2
    ERROR = 3
    NONE = 100


log_colours = {
    LogLevel.VERBOSE: Fore.GREEN,
    LogLevel.INFO: Fore.BLUE,
    LogLevel.ERROR: Fore.RED,
}


def load_dialogue(language: Language) -> Dict[str, str]:
    with open(DIALOGUE_FILE, "r") as file:
        return json.loads(file.read())[language.value]


def disable_text_delay():
    global enable_text_delay
    enable_text_delay = False


class Logger:
    def __init__(self, level=LogLevel.NONE, save_path=None):
        self.level: LogLevel = level
        self.save_path: str = save_path
        if save_path is not None:
            Path(save_path).mkdir(exist_ok=True)
        self.run_index: int = (
            sorted(
                [int(Path(path).stem) for path in glob(f"./{save_path}/*.txt")],
                reverse=True,
            )[0]
            + 1
            if len(glob(f"./{save_path}/*.txt")) > 0
            else 0
        )

    def log(self, text: str, level: LogLevel = LogLevel.INFO):
        if level.value >= self.level.value:
            print(f"{log_colours[level]}<{level.name}> {text}{Fore.RESET}")
        if self.save_path is not None:
            with open(f"{self.save_path}/{self.run_index}.txt", "a") as log_file:
                log_file.write(f"<{level.name}> {text}\n")


def cprint(
    text: str,
    character_delay: float = 0.04,
    short_delay: float = 0.2,
    long_delay: float = 0.4,
    colour: chr = "",
    end: str = f"\n",
):
    """Prints text one character at a time.

    Args:
        text (str): Text to print.
        character_delay (float, optional): The delay between printing characters. Defaults to .02.
        short_delay (float, optional): The delay after printing a comma. Defaults to .2.
        long_delay (float, optional): The delay after printing a full stop or semicolon. Defaults to .4.
        end (str, optional): Character to append to the end of the text. Defaults to "\n".
    """
    print(colour, end="", flush=True)
    if enable_text_delay:
        for char in str(text):
            print(char, end="", flush=True)
            if char in {".", ";", ":", "?", "!"}:
                sleep(long_delay)
            elif char == ",":
                sleep(short_delay)
            else:
                sleep(character_delay)
        print(end, end=Style.RESET_ALL)
    else:
        print(text, end=end + Style.RESET_ALL)


def sent_concat(words: List[str]) -> str:
    """Concatenates a list of words into a sentence with commas and 'and'.

    Args:
        words (list): list of words to convert.

    Returns:
        str: Words concatenated into a sentence.
    """
    length: int = len(words)
    if length > 1:
        words[length - 1] = "and " + words[length - 1]
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


def unique_name(object: object) -> str:
    """Returns a unique name for an object using its type and ID."""
    return type(object).__name__ + str(id(object))[9:]
