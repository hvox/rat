from collections.abc import Hashable, MutableSequence, MutableSet, Sequence, Set
from typing import Any, Iterable, Iterator, Self, TypeVar, overload

T = TypeVar("T")


class SequentialSet(Sequence[T], Set[T]):
    __slots__ = "indexes", "values"

    def __init__(self, iterable: Iterable[T] = ()):
        self.values: list[T] = list(dict.fromkeys(iterable))
        self.indexes: dict[T, int] = {v: i for i, v in enumerate(self.values)}

    def __contains__(self, element: Any) -> bool:
        return element in self.indexes

    def __iter__(self) -> Iterator[T]:
        return iter(self.values)

    def __len__(self) -> int:
        return len(self.values)

    def __repr__(self) -> str:
        return f"{self.__class__.__qualname__}({self.values})"

    def __str__(self) -> str:
        return "{" + ", ".join(map(repr, self.values)) + "}"

    @overload
    def __getitem__(self, i: int) -> T:
        ...

    @overload
    def __getitem__(self, i: slice) -> Self:
        ...

    def __getitem__(self, i: int | slice) -> T | Self:
        if isinstance(i, int):
            return self.values[i]
        return self.__class__(self.values[i])

    def index(self, value: T, start: int = 0, stop: int | None = None) -> int:
        real_stop = stop if stop is not None else 2**30
        i = self.indexes.get(value, -1)
        return i if i != -1 and start <= i < real_stop else -1

    def freeze(self) -> "HashableSequentialSet[T]":
        if isinstance(self, HashableSequentialSet):
            return self
        return HashableSequentialSet(self.values)


class HashableSequentialSet(SequentialSet[T], Hashable):
    __slots__ = ["hash"]
    hash: int | None

    def __init__(self, iterable: Iterable[T] = ()):
        super().__init__(iterable)
        self.hash = None

    def __hash__(self) -> int:
        if self.hash is None:
            self.hash = sum(map(hash, self.values))
        return self.hash


class MutableSequentialSet(SequentialSet[T], MutableSequence[T], MutableSet[T]):
    __slots__ = ()

    def __delitem__(self, i: int | slice) -> None:
        if not isinstance(i, int):
            raise TypeError("Why would you want to delete slice of a set?")
        value = self.values.pop(i)
        del self.indexes[value]
        for index, value in enumerate(self.values[i:], i):
            self.indexes[value] = index

    @overload
    def __setitem__(self, i: int, value: T) -> None:
        ...

    @overload
    def __setitem__(self, i: slice, iterable: Iterable[T]) -> None:
        ...

    def __setitem__(self, i: int | slice, new_value: Any) -> None:
        if not isinstance(i, int):
            raise TypeError("Why would you want to set slice of a set?")
        old_value = self.values[i]
        if new_value == old_value:
            return
        if new_value in self.indexes:
            raise ValueError(
                f"{new_value!r} is already in the set at a different index"
            )
        del self.indexes[old_value]
        self.values[i] = new_value
        self.indexes[new_value] = i

    def insert(self, index: int, value: T) -> None:
        if value in self.indexes:
            raise ValueError(f"{value!r} is already in the set")
        self.values.insert(index, value)
        for i, element in enumerate(self.values[index:], index):
            self.indexes[element] = i

    def add(self, value: T) -> None:
        if value not in self.indexes:
            self.indexes[value] = len(self.values)
            self.values.append(value)

    def push(self, element: T) -> int:
        i = self.indexes.get(element, len(self.indexes))
        if i == len(self.values):
            self.indexes[element] = i
            self.values.append(element)
        return i

    def update(self, elements: Iterable[T]) -> None:
        for value in elements:
            self.add(value)

    def discard(self, value: T) -> None:
        if value in self.indexes:
            self.remove(value)

    def remove(self, value: T) -> None:
        i = self.indexes.pop(value)
        filler = self.values.pop()
        if i < len(self.indexes):
            self.values[i] = filler
            self.indexes[filler] = i


class MutableOrHashableSequentialSet(
    SequentialSet[T], MutableSequence[T], MutableSet[T], Hashable
):
    __slots__ = ["hash"]

    def __init__(self, iterable: Iterable[T] = ()):
        super().__init__(iterable)
        self.hash = None

    def __hash__(self):
        if self.hash is None:
            self.hash = sum(map(hash, self.values))
        return self.hash

    def __delitem__(self, index: int | slice) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        if not isinstance(index, int):
            raise TypeError("Why would you want to delete slice of a set?")
        value = self.values.pop(index)
        del self.indexes[value]
        for i, value in enumerate(self.values[index:], index):
            self.indexes[value] = i

    @overload
    def __setitem__(self, i: int, value: T) -> None:
        ...

    @overload
    def __setitem__(self, i: slice, iterable: Iterable[T]) -> None:
        ...

    def __setitem__(self, i: int | slice, new_value: Any) -> None:
        if not isinstance(i, int):
            raise TypeError("Why would you want to set slice of a set?")
        old_value = self.values[i]
        if new_value == old_value:
            return
        if new_value in self.indexes:
            raise ValueError(
                f"{new_value!r} is already in the set at a different index"
            )
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        del self.indexes[old_value]
        self.values[i] = new_value
        self.indexes[new_value] = i

    def insert(self, index: int, value: T) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        if value in self.indexes:
            raise ValueError(f"{value!r} is already in the set")
        self.values.insert(index, value)
        for i, element in enumerate(self.values[index:], index):
            self.indexes[element] = i

    def add(self, value: T) -> None:
        if value not in self.indexes:
            if self.hash is not None:
                raise ValueError("It is prohibited to modify hashable set")
            self.indexes[value] = len(self.values)
            self.values.append(value)

    def push(self, element: T) -> int:
        i = self.indexes.get(element, len(self.indexes))
        if i == len(self.values):
            if self.hash is not None:
                raise ValueError("It is prohibited to modify hashable set")
            self.indexes[element] = i
            self.values.append(element)
        return i

    def update(self, elements: Iterable[T]) -> None:
        for value in elements:
            self.add(value)

    def discard(self, value: T) -> None:
        if value in self.indexes:
            self.remove(value)

    def remove(self, value: T) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        i = self.indexes.pop(value)
        filler = self.values.pop()
        if i < len(self.indexes):
            self.values[i] = filler
            self.indexes[filler] = i


# It should be called
# MutableSequentialSetAutomaticallyTransitioningIntoUnsoundlyTypedHashableSe...
class DynSet(MutableSequentialSet[T], HashableSequentialSet[T]):
    __slots__ = ()

    def __delitem__(self, index: int | slice) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        super().__delitem__(index)

    def __setitem__(self, i: int | slice, new_value: Any) -> None:
        if not isinstance(i, int):
            raise TypeError("Why would you want to set slice of a set?")
        super().__setitem__(i, new_value)

    def insert(self, index: int, value: T) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        super().insert(index, value)

    def add(self, value: T) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        super().add(value)

    def push(self, element: T) -> int:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        return super().push(element)

    def remove(self, value: T) -> None:
        if self.hash is not None:
            raise ValueError("It is prohibited to modify hashable set")
        super().remove(value)
