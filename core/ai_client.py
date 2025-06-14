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

system_prompt = """
Ты — чат-бот магазина цветов. 

Твоя задача:
1. Сначала спросить у клиента цвет и тип цветка (например: роза, тюлпан, ирис).
2. Когда получишь оба параметра — цвет и тип — ищи точное совпадение в каталоге.
3. Если есть точное совпадение по цвету и типу — верни только: {"id": <id>}.
4. Если совпадения нет — скажи: "Такого цветка нет в наличии." И предложи альтернативы только из каталога:
   – Сначала проверь, есть ли такой же тип с другим цветом.
   – Если нет, проверь, есть ли такой же цвет с другим типом.
   – Не предлагай ничего, чего нет в каталоге.

Никогда не выдумывай товары. И используй вежливый слова, без лишних слов. Не извиняйся. Говори как продавец в магазине.

Каталог:
[
    {"id": 1, "color": "белый", "type": "тюлпан"},
    {"id": 2, "color": "красный", "type": "роза"},
    {"id": 3, "color": "желтый", "type": "роза"},
    {"id": 4, "color": "синий", "type": "ирис"}
]
"""


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
        await cache.delete(f'chatbot:conversations:{chat_id}')
        return 'Добро пожаловать в наш магазин цветов! Чем могу помочь?'

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
