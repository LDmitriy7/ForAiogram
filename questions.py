"""Classes for creating Questions, States with Questions and Conversation States Groups."""
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Union, Callable, Awaitable

from aiogram import types
from aiogram.dispatcher.filters.state import State, StatesGroupMeta, StatesGroup

KeyboardMarkup = Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]
AsyncFunction = Callable[[], Awaitable]
ExceptionBody = Union[str, Awaitable, None]


def to_list(obj: Union[..., Sequence[...]]) -> list[...]:
    if isinstance(obj, Sequence):
        obj = list(obj)
    else:
        obj = [obj]
    return obj


@dataclass
class HandleException:
    """Should be returned from handler to indicate exit with exception."""
    on_exception: ExceptionBody = None


@dataclass
class QuestText:
    """Text and keyboard for an ordinary question."""
    text: str
    keyboard: KeyboardMarkup = None


@dataclass
class QuestFunc:
    """Awaitable for an extraordinary question. AsyncFunction will be called without args."""
    func: Union[AsyncFunction, Awaitable]

    def __post_init__(self):
        if callable(self.func):
            self.func: Awaitable = self.func()


Quest = Union[QuestText, QuestFunc]


class ConvState(State):
    """State with question attribute. It should be used to ask next question in conversation."""

    def __init__(self, question: Union[Quest, list[Quest]]):
        if not isinstance(question, list):
            question = to_list(question)
        self.questions: list[Quest] = question
        super().__init__()


class ConvStatesGroupMeta(StatesGroupMeta):
    """Check if StatesGroup have only ConvState(...) attributes (not State)."""

    def __new__(mcs, class_name, bases, namespace, **kwargs):
        for prop in namespace.values():
            if isinstance(prop, State) and not isinstance(prop, ConvState):
                err_text = f'{class_name} attrs must be instance of {ConvState.__name__}, not {State.__name__}'
                raise TypeError(err_text)

        return super().__new__(mcs, class_name, bases, namespace)


class ConvStatesGroup(StatesGroup, metaclass=ConvStatesGroupMeta):
    """StatesGroup with only ConvState(...) attributes (not State)."""
