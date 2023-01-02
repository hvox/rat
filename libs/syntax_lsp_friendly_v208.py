from dataclasses import dataclass
from functools import cached_property
from itertools import chain
from typing import Callable, NamedTuple, Self, no_type_check
from libs.sequential_sets_v169 import DynSet as Set
from .token_parsers import get_keyword_parser, TOKEN_PARSERS


def split_str(string: str, sep: str, maxsplit: int = -1) -> list[str]:
    result: list[str] = []
    # for is_space, word in groupby(string.split(sep, maxsplit), lambda w: w == ""):
    for word in string.split(sep, maxsplit):
        if word == "" and result and (not result[-1] or result[-1].startswith(sep)):
            word = result.pop() + sep
        result.append(word)
    return result


class Rule(NamedTuple):
    head: str
    body: tuple[str, ...]


def exclude_nones(iterable):
    for element in iterable:
        if element is None:
            continue
        yield element


class LR1Item(NamedTuple):
    dot: int
    rule: Rule
    follower: str | None

    def __str__(self):
        head, body = self.rule
        right = list(body)
        if self.dot == len(right):
            right[-1] += "•"
        else:
            right[self.dot] = "•" + right[self.dot]
        return f"{head} ⟶  " + " ".join(right)

    def next(self):
        return self.rule.body[self.dot] if self.dot < len(self.rule.body) else None

    def tail(self):
        return self.rule.body[self.dot + 1:]


class Node(NamedTuple):
    name: str
    span: tuple[int, int]
    value: str | list[Self]

    def as_tree(self) -> str:
        head = f"{self.span[0]}..{self.span[1]-1} {self.name}"
        if isinstance(self.value, str):
            return head + f" ─ {self.value!r}"
        children = [child.as_tree() for child in self.value]
        for i, child in enumerate(children[:-1]):
            children[i] = "├── " + ("\n│   ").join(child.split("\n"))
        children[-1] = "└── " + ("\n    ").join(children[-1].split("\n"))
        return f"{head}\n" + "\n".join(children)


@dataclass
class Syntax:
    rule_list: list[Rule]
    token_parsers: dict[str, Callable[[str, int], int]]

    @classmethod
    def from_description(
        cls,
        rules: list[str | Rule],
        extra_parsers: dict[str, Callable[[str, int], int]] | None = None,
    ) -> Self:
        real_rules: list[Rule] = []
        for rule in rules:
            if isinstance(rule, str):
                head, *body = split_str(rule, " ")
                rule = Rule(head, tuple(body))
            real_rules.append(rule)
        return cls.from_rules(real_rules, extra_parsers)

    @classmethod
    def from_rules(
        cls, rules: list[Rule], extra_parsers: dict[str, Callable[[str, int], int]] | None = None
    ) -> Self:
        if extra_parsers is None:
            extra_parsers = {}
        token_parsers = {}
        nodes = {head for head, _ in rules}
        tokens = Set(t for _, ts in rules for t in ts if t not in nodes)
        for token in tokens:
            if token in extra_parsers:
                token_parsers[token] = extra_parsers[token]
            elif token in TOKEN_PARSERS:
                token_parsers[token] = TOKEN_PARSERS[token]
            else:
                token_parsers[token] = get_keyword_parser(token)
        return cls(rules, token_parsers)

    @cached_property
    def nodes(self) -> Set[str]:
        return Set(head for head, _ in self.rule_list)

    @cached_property
    def symbols(self) -> Set[str]:
        # TODO: implement operator OR for DynSet for that method
        symbols = Set(t for _, ts in self.rule_list for t in ts)
        symbols.update(self.nodes)
        return symbols

    @cached_property
    def tokens(self) -> Set[str]:
        # TODO: implement operator SUB for DynSet for that method
        return Set(symbol for symbol in self.symbols if symbol not in self.nodes)

    @cached_property
    def rules(self) -> dict[str, Set[Rule]]:
        rules: dict[str, Set[Rule]] = {node: Set() for node in self.nodes}
        for rule in self.rule_list:
            rules[rule.head].add(rule)
        return rules

    @cached_property
    def prefixes(self) -> dict[str, Set[str | None]]:
        prefixes: dict[str, Set[str | None]]
        prefixes = {node: Set() for node in self.nodes}
        prefixes |= {token: Set([token]) for token in self.tokens}
        done = False
        while not done:
            # TODO: check how slow is this thing with "done"
            done = True
            for node, body in self.rule_list:
                while body and body[0] is not None:
                    for first in exclude_nones(prefixes[body[0]]):
                        if first not in prefixes[node]:
                            done = False
                            prefixes[node].add(first)
                    if None not in prefixes[body[0]]:
                        break
                    body = body[1:]
                else:
                    if None not in prefixes[node]:
                        done = False
                        prefixes[node].add(None)
        return prefixes

    def get_sequence_prefixes(self, sequence: tuple[str, ...]) -> Set[str | None]:
        prefixes: Set[str | None]
        i, prefixes = 0, Set([None])
        while None in prefixes and i < len(sequence) and sequence[i] is not None:
            prefixes.remove(None)
            prefixes.update(self.prefixes[sequence[i]])  # I am here
            i += 1
        return prefixes

    def lr1_closure(self, core_items: Set[LR1Item]) -> Set[LR1Item]:
        for item in (item_set := Set(core_items)):
            followers = self.get_sequence_prefixes(item.tail() + (item.follower,))
            for rule in self.rules.get(item.next(), ()):
                for follower in followers:
                    new_item = LR1Item(0, rule, follower)
                    item_set.add(new_item)
        return item_set

    def get_parser_for(self, node: str) -> "LR1Parser":
        return LR1Parser(self, node)

    def scan_token(self, source: str, i: int = 0) -> tuple[str | None, tuple[int, int]]:
        if i >= len(source):
            return (None, (i, i))
        max_len, recognised_token = -1, "???"
        print("scan:", source[i:i+5])
        for token, scanner in self.token_parsers.items():
            try:
                length = scanner(source, i)
                print(token, "->", length)
                if length > max_len:
                    max_len, recognised_token = length, token
            except ValueError:
                pass
        if max_len == -1:
            raise ValueError(f"Unrecognized token at position {i}")
        return (recognised_token, (i, i + max_len))


class LR1Parser:
    syntax: Syntax
    root_node: str

    def __init__(self, syntax: Syntax, root_node: str):
        self.syntax = syntax
        self.root_node = root_node

    @cached_property
    def item_sets_and_gotos(
        self,
    ) -> tuple[Set[Set[LR1Item]], dict[tuple[int, str], int]]:
        root_item = LR1Item(0, Rule(None, (self.root_node,)), None)  # type: ignore
        item_sets, gotos = Set([Set([root_item])]), {}
        for i, item_set in enumerate(map(self.syntax.lr1_closure, item_sets)):
            # TODO: use more efficient way to find next set
            for next_symbol in chain(self.syntax.symbols):
                if next_set := Set(
                    LR1Item(i + 1, rule, follower)
                    for i, rule, follower in item_set
                    if i < len(rule.body) and rule.body[i] == next_symbol
                ):
                    gotos[i, next_symbol] = item_sets.push(next_set)
        return item_sets, gotos

    @cached_property
    def item_sets(self) -> Set[Set[LR1Item]]:
        return self.item_sets_and_gotos[0]

    @cached_property
    def gotos(self) -> dict[tuple[int, str], int]:
        return self.item_sets_and_gotos[1]

    @cached_property
    def actions(self) -> dict[tuple[int, str | None], tuple]:
        actions: dict[tuple[int, str | None], tuple] = {}
        for i, item_set in enumerate(map(self.syntax.lr1_closure, self.item_sets)):
            for terminal, j in (
                (t, j) for t in self.syntax.tokens if (j := self.gotos.get((i, t)))
            ):
                assert (i, terminal) not in actions, "Conflict!"
                actions[i, terminal] = ("shift", j)
            for item in filter(lambda item: item.dot == len(item.rule.body), item_set):
                if item.rule.head is not None:
                    assert (i, item.follower) not in actions, "Conflict!"
                    actions[i, item.follower] = ("reduce", item.rule)
                elif item.follower is None:
                    assert (i, None) not in actions, "Conflict!"
                    actions[i, None] = ("accept",)
        return actions

    @no_type_check  # This does not remove signature, right?
    def parse(self, source: str, offset: int = 0) -> Node:
        stack = [0]
        token, (i, j) = self.syntax.scan_token(source, offset)
        while True:
            match self.actions.get((stack[-1], token)):
                case None:
                    expected = {tok for i, tok in self.actions if i == stack[-1]}
                    raise ValueError(
                        f"Unexpected token at [{i}..{j-1}]: {token!r}\n"
                        f"Expected one of these things: {expected}")
                case ("shift", state):
                    stack.append(Node(token, (i, j), source[i:j]))
                    stack.append(state)
                    token, (i, j) = self.syntax.scan_token(source, j)
                case ("reduce", rule):
                    stack, body = (
                        stack[: -len(rule.body) * 2],
                        stack[-len(rule.body) * 2:: 2],
                    )
                    state = self.gotos[stack[-1], rule.head]
                    span = (body[0].span[0], body[-1].span[-1])
                    stack.extend([Node(rule.head, span, body), state])
                case ("accept",):
                    return stack[1]
