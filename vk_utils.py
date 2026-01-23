import random

def send_message(vk_api_instance, peer_id, text, keyboard=None, attachment=None):
    params = {
        "peer_id": peer_id,
        "message": text,
        "random_id": random.randint(1, 1_000_000),
        "keyboard": keyboard,
    }
    if attachment:
        params["attachment"] = attachment
    vk_api_instance.messages.send(**params)

def get_user_name(vk_api_instance, uid):
    try:
        user = vk_api_instance.users.get(user_ids=uid)[0]
        return f"{user['first_name']} {user['last_name']}"
    except Exception:
        return f"id{uid}"
