"""Flask adapter: validates browser JSON, calls GameState, and serves the UI."""

from flask import Flask, jsonify, render_template, request

from game_engine import GameState, class_cards, scavenge_loot_table


app = Flask(__name__)
game = GameState()


@app.get("/")
def index():
    """Serve the single-page game interface."""
    return render_template("index.html")


@app.get("/api/classes")
def get_classes():
    """Expose class and weapon data for setup and tutorial screens."""
    return jsonify({
        "classes": class_cards(),
        "scavenge_loot": scavenge_loot_table(),
    })


@app.get("/api/state")
def get_state():
    """Read the current match without changing it."""
    return jsonify(game.to_dict())


@app.post("/api/new")
def new_game():
    """Validate setup options and replace the current match."""
    data = request.get_json(silent=True) or {}
    try:
        state = game.new_game(
            player_class=data.get("player_class", "Swordsman"),
            enemy_class=data.get("enemy_class", "random"),
            mode=data.get("mode", "singleplayer"),
            bot_difficulty=data.get("bot_difficulty", "normal"),
            player_hair=data.get("player_hair"),
            enemy_hair=data.get("enemy_hair"),
        )
        return jsonify(state)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@app.post("/api/action")
def perform_action():
    """Execute one player command and serialize the resulting state."""
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    if not isinstance(action, str):
        return jsonify({"error": "An action name is required."}), 400
    try:
        return jsonify(game.perform_player_action(
            action.lower(), defer_bot=bool(data.get("defer_bot", False))
        ))
    except ValueError as error:
        return jsonify({"error": str(error), "state": game.to_dict()}), 400


@app.post("/api/weapon")
def resolve_weapon():
    """Finish the choice created by scavenging a weapon."""
    data = request.get_json(silent=True) or {}
    equip = data.get("equip")
    if not isinstance(equip, bool):
        return jsonify({"error": "The equip choice must be true or false."}), 400
    try:
        return jsonify(game.resolve_weapon(
            equip, defer_bot=bool(data.get("defer_bot", False))
        ))
    except ValueError as error:
        return jsonify({"error": str(error), "state": game.to_dict()}), 400


@app.post("/api/bot")
def perform_bot_turn():
    """Resolve a bot phase deferred until browser animations have finished."""
    try:
        return jsonify(game.perform_pending_bot_turn())
    except ValueError as error:
        return jsonify({"error": str(error), "state": game.to_dict()}), 400


if __name__ == "__main__":
    app.run(port=5050, debug=True)
