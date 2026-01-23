import json
from constants import BASE_STATS
from utils import calc_modifier, calculate_ac
from vk_utils import send_message
from data_storage import get_player_data, delete_player_data
from .character_creation import create_character
from .character_image_generator import generate_character_image
import os
import requests # Import requests library

def reset_character(vk_api_instance, uid, peer_id):
    p = get_player_data(uid)
    if not p:
        send_message(vk_api_instance, peer_id, "У вас нет персонажа для сброса.")
        return

    delete_player_data(uid)
    send_message(vk_api_instance, peer_id, "Ваш персонаж был сброшен.")
    create_character(vk_api_instance, uid, peer_id)

def show_profile(vk_api_instance, uid, peer_id):
    p = get_player_data(uid)
    if not p or not p.get("is_setup_complete"):
        send_message(vk_api_instance, peer_id, "Сначала настройте персонажа. Командой - создать")
        return

    equip = p.get("equipment", {})
    weapon = equip.get("weapon", "нет")
    offhand = equip.get("offhand", "нет")
    armor = equip.get("armor", "нет")

    hands = weapon if offhand in (None, "нет") else f"{weapon} и {offhand}"

    ac = calculate_ac(p)
    p["ac"] = ac # Add AC to player data for image generation
    p["intelligence"] = p.get("intelligence", 8) # Ensure intelligence is present

    # Generate the character image
    output_image_name = f"profile_{uid}.png"
    output_image_full_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "img", output_image_name)

    print(f"[DEBUG profile_view] AC calculated: {ac}") # Debug print for AC
    p["ac"] = ac # Ensure AC is explicitly set in player_data before passing

    # Check if the image already exists
    if not os.path.exists(output_image_full_path):
        # If not, generate it
        print(f"[DEBUG profile_view] Generating new profile image for {uid}")
        generate_character_image(uid, p, output_image_name)
    else:
        print(f"[DEBUG profile_view] Using existing profile image for {uid}")

    # Send the generated image
    try:
        # 1. Get upload server URL
        upload_server = vk_api_instance.photos.getMessagesUploadServer(peer_id=peer_id)
        upload_url = upload_server["upload_url"]

        # 2. Upload the image file
        with open(output_image_full_path, "rb") as photo_file:
            response = requests.post(upload_url, files={"photo": photo_file})
            response.raise_for_status()
            photo_data = response.json()

        # 3. Save the photo to VK
        saved_photo = vk_api_instance.photos.saveMessagesPhoto(
            photo=photo_data["photo"],
            server=photo_data["server"],
            hash=photo_data["hash"]
        )[0] # It returns a list, we need the first element

        # 4. Construct attachment string
        attachment_string = f"photo{saved_photo['owner_id']}_{saved_photo['id']}"

        send_message(vk_api_instance, peer_id, "Ваш профиль:", attachment=attachment_string, keyboard=main_keyboard())
    except Exception as e:
        print(f"Error uploading profile image to VK: {e}")
        send_message(vk_api_instance, peer_id, "Не удалось загрузить изображение профиля. Попробуйте позже.", keyboard=main_keyboard())
    # No finally block to remove the image, as it should persist

def show_effects(vk_api_instance, uid, peer_id):
    p = get_player_data(uid)
    eff = p.get("status_effects", {}) if p else {}
    if not eff:
        send_message(vk_api_instance, peer_id, "На вас нет активных эффектов.")
    else:
        txt = "Ваши эффекты:\n"
        for name, e in eff.items():
            mods = ", ".join(f"{k}: {v}" for k, v in e.items() if k != "duration")
            txt += f"🔸 {name} — {mods} (ещё {e['duration']})\n"
        send_message(vk_api_instance, peer_id, txt)

def main_keyboard():
    return json.dumps({
        "one_time": False,
        "buttons": [
            [
                {"action": {"type": "text", "label": "Профиль"}, "color": "primary"},
                {"action": {"type": "text", "label": "Сбросить персонажа"}, "color": "negative"}
            ],
            [
                {"action": {"type": "text", "label": "Загрузить фото"}, "color": "secondary"}
            ]
        ]
    })
