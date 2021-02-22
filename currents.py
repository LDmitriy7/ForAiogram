from __future__ import annotations

import functools
from typing import Awaitable, Callable, Optional

from aiogram import types, Dispatcher, Bot as _Bot
from aiogram.dispatcher.filters.state import State as _State, StatesGroup
from aiogram.utils.mixins import ContextInstanceMixin

AsyncFunction = Callable[..., Awaitable]


def get_state_by_name(state_name: str) -> Optional[_State]:
    """Search for State with state_name in all StatesGroups."""
    for state_group in StatesGroup.__subclasses__():
        for state in state_group.all_states:
            if state.state == state_name:
                return state


class ContextType:
    """Decorator[AsyncFunction] -> AsyncFunction

    For function(*, {key}=None):
    if {key} is None, set {key} = current ctx_type instance or derivatives
    """

    ctx_type: type[ContextInstanceMixin] = ...
    key: str = ...
    default = None

    @staticmethod
    async def get_target(obj: ctx_type) -> ctx_type:
        """You can get derivatives of current object instead of object itself."""
        return obj

    @classmethod
    def decorator(cls, async_func=None, ctx_type=None, key=None, default=None):
        @functools.wraps(async_func)
        async def wrapper(*args, **kwargs):
            key_value = kwargs.get(key)

            if key_value is None:
                key_value = await cls.get_target(ctx_type.get_current())
                if key_value is None:
                    key_value = default

            kwargs[key] = key_value
            return await async_func(*args, **kwargs)

        return wrapper

    def __new__(cls, async_func=None, ctx_type=None, key=None, default=None):
        if async_func is None:
            instance = super().__new__(cls)
            instance.ctx_type = ctx_type or cls.ctx_type
            instance.key = key or cls.key
            instance.default = default
            return instance

        return cls.decorator(async_func, cls.ctx_type, cls.key, cls.default)

    def __call__(self, async_func) -> AsyncFunction:
        return self.decorator(async_func, self.ctx_type, self.key, self.default)


class User(ContextType):
    ctx_type = types.User
    key = 'user'


class Chat(ContextType):
    ctx_type = types.Chat
    key = 'chat'


class Query(ContextType):
    ctx_type = types.CallbackQuery
    key = 'query'


class InlineQuery(ContextType):
    ctx_type = types.InlineQuery
    key = 'query'


class Message(ContextType):
    ctx_type = types.Message
    key = 'msg'


class Dp(ContextType):
    ctx_type = Dispatcher
    key = 'dp'


class Bot(ContextType):
    ctx_type = _Bot
    key = 'bot'


# --- derivatives 1 ---

class UserData(ContextType):
    ctx_type = Dispatcher
    key = 'udata'

    @staticmethod
    async def get_target(obj: ctx_type) -> dict:
        try:
            return await obj.current_state().get_data()
        except AttributeError:
            return {}


class RawState(ContextType):
    ctx_type = Dispatcher
    key = 'state'

    @staticmethod
    async def get_target(obj: ctx_type) -> Optional[str]:
        try:
            return await obj.current_state().get_state()
        except AttributeError:
            return None


class State(ContextType):
    ctx_type = Dispatcher
    key = 'state'

    @staticmethod
    async def get_target(obj: ctx_type) -> Optional[State]:
        try:
            raw_state = await obj.current_state().get_state()
            return get_state_by_name(raw_state)
        except AttributeError:
            return None


# --- derivatives 2 ---

class UserID(User):
    key = 'user_id'

    @staticmethod
    async def get_target(obj: User.ctx_type) -> int:
        return obj.id


class UserName(User):
    key = 'user_name'

    @staticmethod
    async def get_target(obj: User.ctx_type) -> str:
        return obj.full_name


class UserUname(User):
    key = 'username'

    @staticmethod
    async def get_target(obj: User.ctx_type) -> str:
        return obj.username


class ChatID(Chat):
    key = 'chat_id'

    @staticmethod
    async def get_target(obj: Chat.ctx_type) -> int:
        return obj.id


class ChatType(Chat):
    key = 'chat_type'

    @staticmethod
    async def get_target(obj: Chat.ctx_type) -> str:
        return obj.type


# --- derivatives 3 ---


class InlineMessageID(Query):
    key = 'inline_message_id'

    @staticmethod
    async def get_target(obj: Query.ctx_type) -> str:
        return obj.inline_message_id


class QueryMessage(Query):
    key = 'msg'

    @staticmethod
    async def get_target(obj: Query.ctx_type) -> types.Message:
        return obj.message


class MessageText(Message):
    key = 'text'

    @staticmethod
    async def get_target(obj: Message.ctx_type) -> str:
        return obj.text


if __name__ == '__main__':
    from asyncio import get_event_loop

    loop = get_event_loop()

    types.User.set_current(types.User(id=123, username='LDM7'))
    types.Chat.set_current(types.Chat(type='private'))


    @User
    @Dp
    @Message
    @Chat
    @Query
    @InlineQuery
    @Bot
    @UserData
    @RawState(default='null')
    @State
    @UserID
    @UserName
    @UserUname
    @ChatType
    async def test(**kwargs):
        print(kwargs)


    @Chat
    @ContextType(ctx_type=types.InlineQuery, key='iquery', default=0)
    async def test2(**kwargs):
        print(kwargs)


    loop.run_until_complete(test())
    loop.run_until_complete(test2())
