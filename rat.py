from fractions import Fraction
from re import MULTILINE
from re import compile as regex
from typing import NamedTuple, Self
from libs.syntax_lsp_friendly_v208 import Syntax


class Node(NamedTuple):
    head: object
    children: list[Self]


TOKENS = {
    "number": regex(r"\d+(\.\d+)?"),
    "operator": regex(r"[+\-*/]"),
    "variable": regex(r"\w+"),
    "comment": regex(r"#.*$", MULTILINE),
}


def parse_source(source: str) -> Node:
    tokens, i = [], 0
    while i < len(source):
        if source[i].isspace():
            print(f"{source[i]!r} is a space!")
            if source[i] == "\n":
                tokens.append(("newline", "\n"))
            i += 1
            continue
        print(f"{source[i]!r} is not a space!")
        for token, re in TOKENS.items():
            if match := re.match(source, i):
                _, j = match.span()
                tokens.append((token, source[i:j]))
                i = j
                break
        else:
            raise Exception(f"{source[i]!r} is unexpected here!")
    return tokens


def parse_identifier(source: str, offset: int) -> int:
    if not source[offset].isalpha():
        raise ValueError()
    i, j = offset, offset + 1
    if j < len(source) and (source[j].isalnum() or source[j] == "_"):
        j += 1
    return j - i


rules = ["stmts identifier  =  expr", "expr identifier"]
token_parsers = {"identifier": parse_identifier}
syntax = Syntax.from_description(rules, token_parsers)
parser = syntax.get_parser_for("stmts")
for item_set in parser.item_sets:
    print("{" + ", ".join(map(str, item_set)) + "}")
print(parser.parse("x=fuy").as_tree())
# print(parse_source("123-x # aboba\n1"))
