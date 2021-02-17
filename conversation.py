from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import TypeVar, Union, Optional

from aiogram import types, Dispatcher, Bot
from aiogram.contrib.questions import ConvState, ConvStatesGroup, HandleException
from aiogram.contrib.questions import Quest, QuestText, QuestFunc
from aiogram.dispatcher.middlewares import BaseMiddleware

__all__ = ['UserDataUpdater', 'SwitchConvState', 'AskQuestion']

T = TypeVar('T')


def recursive_search_obj(obj_type: type[T], container: Union[list, tuple]) -> T:
    """Recursive search for instance of obj_type in lists/tuples."""
    if isinstance(container, (list, tuple)):
        for item in container:
            obj = recursive_search_obj(obj_type, item)
            if obj is not None:  # object found
                return obj
    else:
        if isinstance(container, obj_type):
            return container


async def update_user_data(new_data: dict):
    """Set, delete or extend values in storage for current User+Chat."""
    state_ctx = Dispatcher.get_current().current_state()

    async with state_ctx.proxy() as udata:
        for key, value in new_data.items():

            # extend value with list
            if isinstance(value, list):
                udata.setdefault(key, [])
                udata[key].extend(value)

            # delete key
            elif isinstance(value, tuple) and not value:
                del udata[key]

            else:  # just set value
                udata[key] = value


def get_state_by_name(state_name: str,
                      base_states_group: type[ConvStatesGroup] = ConvStatesGroup) -> Optional[ConvState]:
    """Search for State with state_name in subclasses of base_states_group."""
    for state in base_states_group.all_conv_states:
        if state.state == state_name:
            return state


async def process_exception(exception: HandleException):
    """Send message with exception text [current Chat] or await Awaitable."""
    chat = types.Chat.get_current()
    bot = Bot.get_current()
    e_body = exception.on_exception

    if isinstance(e_body, str):
        await bot.send_message(chat.id, e_body)
    elif isinstance(e_body, Awaitable):
        await e_body


async def ask_question(question: list[Quest]):
    """Send QuestText to current Chat or await QuestFunc."""
    for item in question:
        if isinstance(item, QuestText):
            chat = types.Chat.get_current()
            bot = Bot.get_current()
            await bot.send_message(chat.id, item.text, reply_markup=item.keyboard)
        elif isinstance(item, QuestFunc):
            await item.func


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
    """Search for dict in results. Update storage for current User+Chat with dict data.

    For each item in dict:
    1) Extend value in storage if list passed
    2) Delete key in storage if empty tuple passed
    3) Just set value otherwise
    """

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        new_data = recursive_search_obj(dict, results)
        if new_data:
            await update_user_data(new_data)


class SwitchConvState(PostMiddleware):
    """Switch state for current User+Chat [if user is in conversation].

    If HandleException in handle results - process exception;
    Else if ConvStateGroup in handle results - set first state in group;
    Else if user is in conversation - set next state in group;
    """

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        state_ctx = Dispatcher.get_current().current_state()
        state_name = await state_ctx.get_state()
        conv_state = get_state_by_name(state_name, ConvStatesGroup)
        new_conv_group = recursive_search_obj(ConvStatesGroup.__class__, results)
        exception = recursive_search_obj(HandleException, results)

        if exception:
            await process_exception(exception)
        elif new_conv_group:
            await new_conv_group.first()
        elif conv_state:
            await conv_state.group.next()


class AskQuestion(PostMiddleware):
    """Ask question for ConvState(...) or clear storage for current User+Chat."""

    @classmethod
    async def on_post_process_message(cls, msg: types.Message, results: list, *args):
        state_ctx = Dispatcher.get_current().current_state()
        state_name = await state_ctx.get_state()
        conv_state = get_state_by_name(state_name, ConvStatesGroup)

        if conv_state:
            await ask_question(conv_state.question)
        else:
            await state_ctx.finish()
