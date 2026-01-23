from data_storage import (
    get_player_stats as _db_get_player_stats,
    save_player_stats as _db_save_player_stats,
    get_top_stats as _db_get_top_stats,
)

def update_stats_for_player(player_id, first_name, last_name, win=False):
    stats = _db_get_player_stats(player_id) or {
        "first_name": first_name,
        "last_name": last_name,
        "wins": 0,
        "losses": 0,
    }
    if win:
        stats["wins"] += 1
    else:
        stats["losses"] += 1
    _db_save_player_stats(player_id, stats)

def get_player_stats(player_id):
    return _db_get_player_stats(player_id)

def get_top_stats(limit=10):
    return _db_get_top_stats(limit)

def format_stats_message(player_stats):
    if not player_stats:
        return "Статистика не найдена."
    return f"{player_stats['first_name']} {player_stats['last_name']}: Победы - {player_stats['wins']}, Поражения - {player_stats['losses']}"

def format_top_stats_message(top_list):
    if not top_list:
        return "Статистика пока пуста."
    message = "🏆 Топ игроков:\n"
    for i, (player_id, stats) in enumerate(top_list, 1):
        message += f"{i}. {stats['first_name']} {stats['last_name']} - Победы:{stats['wins']}, Поражения:{stats['losses']}\n"
    return message


