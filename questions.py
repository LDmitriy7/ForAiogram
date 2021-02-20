"""Classes for creating Questions, States with Questions and Conversation States Groups."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union, Callable, Awaitable, Optional

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
Quests = Union[Quest, list[Quest]]


class ConvState(State):
    """State with question attribute. It should be used to ask next question in conversation."""

    def __init__(self, question: Quests):
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

    @property
    def state_ctx(cls):
        return Dispatcher.get_current().current_state()

    @property
    def all_child_states(cls) -> list[ConvState]:
        """Search for all ConvState(...) in all ConvStatesGroup sublasses."""
        all_states = []
        for conv_group in ConvStatesGroup.__subclasses__():
            all_states.extend(conv_group.all_states)
        return all_states

    def get_state_by_name(cls, state_name: str) -> Optional[ConvState]:
        """Search for ConvState with state_name in all ConvStatesGroups."""
        for state in cls.all_child_states:
            if state.state == state_name:
                return state

    async def get_current_state(cls) -> Optional[ConvState]:
        """Search current ConvState(...) in all ConvStatesGroups."""
        try:
            state_name = await cls.state_ctx.get_state()
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

        next_step = group_states.index(state) + 1
        return cls.get_state_by_index(group_states, next_step)

    async def get_previous_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
        except AttributeError:
            return None

        previous_step = group_states.index(state) - 1
        return cls.get_state_by_index(group_states, previous_step)

    async def __get_first_group_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
            return group_states[0]
        except AttributeError:
            return None

    async def __get_last_group_state(cls) -> Optional[ConvState]:
        state = await cls.get_current_state()

        try:
            group_states: tuple[ConvState] = state.group.states
            return group_states[-1]
        except AttributeError:
            return None

    @staticmethod
    def get_state_by_index(group_states: tuple[ConvState], index: int) -> Optional[ConvState]:
        """Return state with passed index or None. Exception safety."""
        if 0 <= index < len(group_states):
            return group_states[index]


class ConvStatesGroup(StatesGroup, metaclass=ConvStatesGroupMeta):
    """StatesGroup with only ConvState(...) attributes (not State)."""


class SingleConvStatesGroup(ConvStatesGroup):
    """ConvStatesGroup with single states (no switching)."""

    @classmethod
    async def get_next_state(cls) -> None:
        return None

    @classmethod
    async def get_previous_state(cls) -> None:
        return None
