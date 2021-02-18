from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import TypeVar, Union, Optional, Literal

from aiogram import types, Dispatcher, Bot
from aiogram.contrib.questions import ConvState, ConvStatesGroup
from aiogram.contrib.questions import Quest, QuestText, QuestFunc
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.middlewares import BaseMiddleware

# выход после обработки, выход без обработки, выход с исключением


__all__ = ['UserDataUpdater', 'SwitchConvState', 'get_current_state', 'HandleException', 'NewData']

T = TypeVar('T')
StorageData = Union[str, int, list, None]


def to_list(obj) -> list:
    if not isinstance(obj, list):
        obj = [obj]
    return obj


def search_in_results(obj_type: type[T], container: list) -> Optional[T]:
    """Recursive search for instance of obj_type in lists/tuples."""
    if isinstance(container, (list, tuple)):
        for item in container:
            obj = search_in_results(obj_type, item)
            if obj is not None:  # object found
                return obj
    else:
        if isinstance(container, obj_type):
            return container


async def ask_question(question: Union[Quest, list[Quest]]):
    """Send message for each Quest in question [current Chat]."""
    chat = types.Chat.get_current()
    bot = Bot.get_current()

    async def ask_quest(quest: Quest):
        if isinstance(quest, str):
            await bot.send_message(chat.id, quest)
        elif isinstance(quest, QuestText):
            await bot.send_message(chat.id, quest.text, reply_markup=quest.keyboard)
        elif isinstance(quest, QuestFunc):
            await quest.async_func()

    for q in to_list(question):
        await ask_quest(q)


@dataclass
class HandleException:
    on_exception: Quest = None


@dataclass
class NewData:
    set_items: dict[str, StorageData] = field(default_factory=dict)
    extend_items: dict[str, StorageData] = field(default_factory=dict)
    del_keys: Union[str, list] = field(default_factory=list)

    async def update_proxy(self, state_ctx: FSMContext):
        """Set, extend or delete items with state_ctx.proxy()."""
        async with state_ctx.proxy() as udata:
            udata.update(self.set_items)

            for key, value in self.extend_items.items():
                udata.setdefault(key, [])
                udata[key].extend(to_list(value))

            for key in to_list(self.del_keys):
                del udata[key]


@dataclass
class NewState:
    conv_state: Union[ConvState, type[ConvStatesGroup]] = 'previous'
    on_conv_exit: Quest = None

    async def set_state(self) -> ConvState:
        if isinstance(self.conv_state, ConvState):
            state = self.conv_state
        elif isinstance(self.conv_state, type(ConvStatesGroup)):
            self.conv_state: type[ConvStatesGroup]
            state = self.conv_state.states[0]
        elif self.conv_state == 'previous':
            state = await ConvStatesGroup.get_previous_state()
        else:
            state = None

        if state:
            await state.set()

        return state


class PostMiddleware(BaseMiddleware, ABC):
    """Abstract Middleware for post processing Message and CallbackQuery."""

    @classmethod
    @abstractmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, state_dict: dict):
        """Works after processing any message by handler."""

    @classmethod
    async def on_post_process_callback_query(cls, query: types.CallbackQuery, results: list, state_dict: dict):
        """Answer query [empty text] and call on_post_process_message(query.message)."""
        await query.answer()
        await cls.on_post_process_message(query.message, results, state_dict)


class UserDataUpdater(PostMiddleware):
    """Search for NewData(...) in handle results. Update storage for current User+Chat with new data."""

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        state_ctx = Dispatcher.get_current().current_state()
        new_data = search_in_results(NewData, results)
        if new_data:
            await new_data.update_proxy(state_ctx)


class SwitchConvState(PostMiddleware):
    """Switch state for current User+Chat [if user is in conversation].

    # If HandleException in handle results - process exception;
    # Else if ConvStateGroup in handle results - set first state in group;
    # Else if user is in conversation - set next state in group;
    """

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        exception = search_in_results(HandleException, results)
        new_state = search_in_results(NewState, results)

        if exception:
            await ask_question(exception.on_exception)

        elif new_state:
            next_state = await new_state.set_state()
            if next_state:
                await ask_question(next_state.question)
            else:
                await ask_question(new_state.on_conv_exit)

        else:
            next_state: ConvState = await ConvStatesGroup.get_next_state()
            if next_state:
                await next_state.set()
                await ask_question(next_state.question)
            else:
                state_ctx = Dispatcher.get_current().current_state()
                await state_ctx.finish()
