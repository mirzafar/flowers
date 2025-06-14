import logging
from datetime import timedelta

import ujson
from openai import AsyncOpenAI

from core.cache import cache
from settings import settings

client = AsyncOpenAI(
    api_key=settings['ai_api_key']
)

logger = logging.getLogger(__name__)

system_message = '''
Ты — чат-бот магазина цветов. Твоя задача — помочь клиенту выбрать цветы из каталога. Сначала выясни у клиента, какого цвета и какого типа цветы он хочет (например: роза, тюльпан, ирис и т.д.).

Когда у тебя есть и цвет, и тип цветка, проверь наличие в каталоге. Если такой товар есть, ответь строго в формате: {"id": <id>}.

Если товара нет, скажи: "Такого цветка нет в наличии."

Если клиент просто интересуется ассортиментом, перечисли все доступные цветы из каталога.

Каталог:
[
    {"id": 1, "color": "белый", "type": "тюлпан"},
    {"id": 2, "color": "красный", "type": "роза"},
    {"id": 3, "color": "желтый", "type": "роза"},
    {"id": 4, "color": "синий", "type": "ирис"}
]

Говори просто, как консультант в магазине. Не извиняйся, не объясняй правила, не пиши ничего лишнего. Только нужную информацию.
'''


def clean_text(text: str) -> str:
    return text.strip().encode('utf-8', 'replace').decode('utf-8')


def close_chat(bot_response) -> bool:
    txt = bot_response.strip().replace('*', '')
    if 'id' in txt or 'ID' in txt:
        print()
        print('close_chat')
        print(txt)
        return True

    return False


async def http_client(conversations: list) -> str:
    response = await client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=conversations,
        temperature=0.7,
    )

    return response.choices[0].message.content


async def on_messages(input_text: str, chat_id: str) -> str:
    input_text = clean_text(input_text)
    if input_text.lower() in ['/start', 'stoop']:
        return await cache.delete(f'chatbot:conversations:{chat_id}')

    conversations = await cache.get(f'chatbot:conversations:{chat_id}')
    if conversations:
        conversations = ujson.loads(conversations)
    else:
        conversations = [
            {'role': 'system', 'content': system_message}
        ]

    conversations.append({'role': 'user', 'content': input_text})
    response_text = await http_client(conversations)

    result = close_chat(response_text)
    if result:
        await cache.delete(f'chatbot:conversations:{chat_id}')
        return 'В ближайшее время оператор свяжется с вами.'

    else:
        conversations.append({'role': 'assistant', 'content': response_text})
        await cache.set(f'chatbot:conversations:{chat_id}', ujson.dumps(conversations), ex=timedelta(hours=1))

    return response_text
