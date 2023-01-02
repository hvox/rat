from typing import Callable


def get_keyword_parser(keyword: str) -> Callable[[str, int], int]:
    def f(source: str, offset: int):
        if source[offset: offset + len(keyword)] != keyword:
            raise ValueError("There is no {keyword!r} here")
        return len(keyword)

    return f


def ignore_spaces(source: str, offset: int) -> int:
    spaces = 0
    while offset + spaces < len(source) and source[offset + spaces] in " \t":
        spaces += 1
    return spaces


def ignore_spaces_and_newlines(source: str, offset: int) -> int:
    spaces = 0
    while offset + spaces < len(source) and source[offset + spaces] in " \t\n":
        spaces += 1
    return spaces


TOKEN_PARSERS = {
    "": ignore_spaces,
    " ": ignore_spaces_and_newlines,
}
