# vk_init.py
import vk_api
from constants import VK_TOKEN, GROUP_ID
from vk_api.bot_longpoll import VkBotLongPoll

# Инициализация VK API
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkBotLongPoll(vk_session, GROUP_ID)

# Можно также создать функцию для удобства, если нужно передавать vk в другие функции
def get_vk_api():
    return vk

def get_vk_longpoll():
    return longpoll