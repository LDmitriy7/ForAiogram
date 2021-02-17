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


__all__ = ['UserDataUpdater', 'SwitchConvState', 'get_current_state']

T = TypeVar('T')
StorageData = Union[str, int, list, None]


def to_list(obj) -> list:
    if not isinstance(obj, list):
        obj = [obj]
    return obj


def get_state_by_name(
        state_name: str, base_states_group: type[ConvStatesGroup] = ConvStatesGroup
) -> Optional[ConvState]:
    """Search for State with state_name in subclasses of base_states_group."""
    for state in base_states_group.all_conv_states:
        if state.state == state_name:
            return state


async def get_current_state() -> Optional[ConvState]:
    state_ctx = Dispatcher.get_current().current_state()
    state_name = await state_ctx.get_state()
    return get_state_by_name(state_name)


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
    new_state: Union[Literal['previous'], type[ConvStatesGroup], ConvState] = None
    on_conv_exit: Quest = None

    async def set_new_state(self):
        if isinstance(self.new_state, ConvState):
            await self.new_state.set()
        elif isinstance(self.new_state, type[ConvStatesGroup]):
            await self.new_state.first()
        elif self.new_state == 'previous':
            conv_state: ConvState = await get_current_state()
            if conv_state and conv_state.group:
                new_state = conv_state.group.previous()
                if new_state is None and self.on_conv_exit:
                    await ask_question(self.on_conv_exit)


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
        await new_data.update_proxy(state_ctx)


class SwitchConvState(PostMiddleware):
    """Switch state for current User+Chat [if user is in conversation].

    # If HandleException in handle results - process exception;
    # Else if ConvStateGroup in handle results - set first state in group;
    # Else if user is in conversation - set next state in group;
    """

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        conv_state: ConvState = get_current_state()
        exception = search_in_results(HandleException, results)

        if exception:
            await ask_question(exception.on_exception)
            await exception.set_new_state()
        elif conv_state and conv_state.group:
            await conv_state.group.next()
            await ask_question(conv_state.question)
        else:
            state_ctx = Dispatcher.get_current().current_state()
            await state_ctx.finish()
