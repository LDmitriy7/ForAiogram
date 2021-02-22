from __future__ import annotations

import functools
from typing import Awaitable, Callable
from typing import Optional

from aiogram import types, Dispatcher, Bot
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.mixins import ContextInstanceMixin

AsyncFunction = Callable[..., Awaitable]


def _get_state_by_name(state_name: str) -> Optional[State]:
    """Search for State with state_name in all StatesGroups."""
    for state_group in StatesGroup.__subclasses__():
        for state in state_group.all_states:
            if state.state == state_name:
                return state


async def get_current_state() -> Optional[State]:
    """Search current State(...) in all StatesGroups."""
    try:
        state_ctx = Dispatcher.get_current().current_state()
        state_name = await state_ctx.get_state()
        state = _get_state_by_name(state_name)
        return state
    except AttributeError:
        return None


def make_type_decorator(_type: type[ContextInstanceMixin], key_name: str) \
        -> Callable[[AsyncFunction], AsyncFunction]:
    def decorator(async_func) -> AsyncFunction:
        @functools.wraps(async_func)
        async def wrapper(*args, **kwargs):
            param_value = kwargs.get(key_name)

            if param_value is None:
                param_value = _type.get_current()

            kwargs[key_name] = param_value
            return await async_func(*args, **kwargs)

        return wrapper

    return decorator


class SetCurrent:
    """Contains decorators(...) -> AsyncFunction

    For function(*, {deco_name}=None):
    if {deco_name} is None, set {deco_name} = current aiogram.types.{deco_name} instance
    [or instance derivatives]
    """

    user = make_type_decorator(types.User, 'user')
    chat = make_type_decorator(types.Chat, 'chat')
    query = make_type_decorator(types.CallbackQuery, 'query')
    inline_query = make_type_decorator(types.InlineQuery, 'query')
    msg = make_type_decorator(types.Message, 'msg')
    dp = make_type_decorator(Dispatcher, 'dp')
    bot = make_type_decorator(Bot, 'bot')

    @staticmethod
    def udata(func) -> AsyncFunction:
        """For function(*, udata=None): set udata = storage data for current User+Chat."""

        @functools.wraps(func)
        async def wrapper(*args, udata=None, **kwargs):
            if udata is None:
                try:
                    udata = await Dispatcher.get_current().current_state().get_data()
                except AttributeError:
                    udata = {}
            return await func(*args, **kwargs, udata=udata)

        return wrapper

    @staticmethod
    def raw_state(func) -> AsyncFunction:

        @functools.wraps(func)
        async def wrapper(*args, state=None, **kwargs):
            if state is None:
                try:
                    state = await Dispatcher.get_current().current_state().get_state()
                except AttributeError:
                    state = None
            return await func(*args, **kwargs, state=state)

        return wrapper

    @staticmethod
    def state(func) -> AsyncFunction:

        @functools.wraps(func)
        async def wrapper(*args, state=None, **kwargs):
            if state is None:
                state = await get_current_state()
            return await func(*args, **kwargs, state=state)

        return wrapper


if __name__ == '__main__':
    from asyncio import run
    from pprint import pp

    types.User.set_current(types.User(id=123))


    @SetCurrent.user
    @SetCurrent.dp
    @SetCurrent.msg
    @SetCurrent.chat
    @SetCurrent.query
    @SetCurrent.inline_query
    @SetCurrent.bot
    @SetCurrent.udata
    @SetCurrent.raw_state
    @SetCurrent.state
    async def test(**kwargs):
        pp(kwargs)


    run(test(dp=2, chat=3, state='ask_price'))
