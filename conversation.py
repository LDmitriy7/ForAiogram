from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from dataclasses import field
from typing import TypeVar, Union, Optional, cast

from aiogram import types, Dispatcher, Bot
from aiogram.contrib.questions import ConvState, ConvStatesGroup
from aiogram.contrib.questions import Quest, Quests, QuestText, QuestFunc
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.middlewares import BaseMiddleware

# выход после обработки, выход без обработки, выход с исключением


__all__ = ['UserDataUpdater', 'SwitchConvState', 'HandleException', 'NewData', 'NewState']

T = TypeVar('T')
_StorageData = Union[str, int, tuple, dict, None]
StorageData = Union[_StorageData, list[_StorageData]]


def to_list(obj) -> list:
    """Cast obj to list if it's not yet."""
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
    elif isinstance(container, obj_type):
        return container


async def ask_question(question: Quests):
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
    on_exception: Quests = None


@dataclass
class NewData:
    set: dict[str, StorageData] = field(default_factory=dict)
    extend: dict[str, StorageData] = field(default_factory=dict)
    delete: Union[str, list] = field(default_factory=list)

    async def update_proxy(self, state_ctx: FSMContext):
        """Set, extend or delete items in storage for current User+Chat."""
        async with state_ctx.proxy() as udata:
            udata.update(self.set)

            for key, value in self.extend.items():
                udata.setdefault(key, [])
                udata[key].extend(to_list(value))

            for key in to_list(self.delete):
                udata.pop(key, None)


@dataclass
class NewState:
    """Should be used to set specific state, previous state or first state in group."""
    conv_state: Union[ConvState, type[ConvStatesGroup]] = 'previous'
    on_conv_exit: Quests = None

    async def get_next_state(self) -> Optional[ConvState]:
        """Return ConvState(...) to be set next."""
        next_state = None

        if isinstance(self.conv_state, ConvState):
            next_state = self.conv_state
        elif isinstance(self.conv_state, type(ConvStatesGroup)):
            self.conv_state: type[ConvStatesGroup]
            next_state = self.conv_state.states[0]
        elif self.conv_state == 'previous':
            next_state = await ConvStatesGroup.get_previous_state()

        return next_state

    # async def set_state(self) -> Optional[ConvState]:
    #     """Set specific state, previous state or first state in group."""
    # 
    #     if next_state:
    #         await next_state.set()
    #     else:
    #         state_ctx = Dispatcher.get_current().current_state()
    #         await state_ctx.finish()
    #     return next_state


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
        new_data = search_in_results(NewData, results)
        if new_data:
            state_ctx = Dispatcher.get_current().current_state()
            await new_data.update_proxy(state_ctx)


class SwitchConvState(PostMiddleware):
    """Switch state context for current User+Chat.

    If HandleException in handle results - process exception;
    Else if NewState in handle results - set new state;
    Else if user is in conversation - set next state in group and ask question;
    """

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        state_ctx = Dispatcher.get_current().current_state()
        exception = search_in_results(HandleException, results)
        new_state = search_in_results(NewState, results)

        if exception:
            await ask_question(exception.on_exception)

        elif new_state:
            next_state: ConvState = await new_state.get_next_state()
            if next_state:
                await next_state.set()
                await ask_question(next_state.question)
            else:
                await state_ctx.finish()
                await ask_question(new_state.on_conv_exit)

        else:
            next_state: ConvState = await ConvStatesGroup.get_next_state()
            if next_state:
                await next_state.set()
                await ask_question(next_state.question)
            else:
                await state_ctx.finish()
