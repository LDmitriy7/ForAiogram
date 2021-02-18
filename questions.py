"""Classes for creating Questions, States with Questions and Conversation States Groups."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Union, Callable, Awaitable, Any

from aiogram import types, Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroupMeta, StatesGroup

KeyboardMarkup = Union[types.ReplyKeyboardMarkup, types.InlineKeyboardMarkup]
AsyncFunction = Callable[[], Awaitable]


@dataclass
class QuestText:
    """Text and keyboard for an ordinary question."""
    text: str
    keyboard: KeyboardMarkup


@dataclass
class QuestFunc:
    """Async function for an extraordinary question. Will be called without args."""
    async_func: AsyncFunction


Quest = Union[str, QuestText, QuestFunc, None]


class ConvState(State):
    """State with question attribute. It should be used to ask next question in conversation."""

    def __init__(self, question: Union[Quest, list[Quest]]):
        self.question = question
        super().__init__()


class ConvStatesGroupMeta(StatesGroupMeta):
    """Check if StatesGroup have only ConvState(...) attributes (not State)."""

    def __new__(mcs, class_name, bases, namespace, **kwargs):
        for prop in namespace.values():
            if isinstance(prop, State) and not isinstance(prop, ConvState):
                err_text = f'{class_name} attrs must be instance of {ConvState.__name__}, not {State.__name__}'
                raise TypeError(err_text)

        return super().__new__(mcs, class_name, bases, namespace)

    def all_conv_states(cls) -> list[ConvState]:
        """Search for all ConvState(...) in all sublasses."""
        all_states = []
        for conv_group in cls.__subclasses__():
            all_states.extend(conv_group.all_states)
        return all_states

    def get_state_by_name(cls, state_name: str) -> Optional[ConvState]:
        """Search for State with state_name in subclasses."""
        for state in cls.all_conv_states():
            if state.state == state_name:
                return state

    async def get_current_state(cls) -> Optional[ConvState]:
        try:
            state_ctx = Dispatcher.get_current().current_state()
            state_name = await state_ctx.get_state()
            state = cls.get_state_by_name(state_name)
            return state
        except AttributeError:
            return None

    async def get_next_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
        except AttributeError:
            return None

        try:
            next_step = group_states.index(state) + 1
        except ValueError:
            next_step = 0

        try:
            next_state = group_states[next_step]
        except IndexError:
            next_state = None

        return next_state

    async def get_previous_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()
        group_states: tuple[ConvState] = state.group.states

        try:
            group_states: tuple[ConvState] = state.group.states
        except AttributeError:
            return None

        try:
            previous_step = group_states.index(state) - 1
        except ValueError:
            previous_step = 0

        if previous_step < 0:
            previous_state = None
        else:
            previous_state = group_states[previous_step]

        return previous_state

    async def get_first_group_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
            return group_states[0]
        except AttributeError:
            return None

    async def get_last_group_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
            return group_states[-1]
        except AttributeError:
            return None


class ConvStatesGroup(StatesGroup, metaclass=ConvStatesGroupMeta):
    """StatesGroup with only ConvState(...) attributes (not State)."""
