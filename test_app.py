"""HTTP contract tests for Flask routes and JSON response shapes."""

import unittest

from app import app


class FlaskApiTests(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()
        self.client.post("/api/new", json={
            "player_class": "Swordsman",
            "enemy_class": "Assassin",
        })

    def test_page_and_static_files_are_served_by_flask(self):
        with self.client.get("/") as page_response:
            self.assertEqual(page_response.status_code, 200)
        with self.client.get("/static/styles.css") as css_response:
            self.assertEqual(css_response.status_code, 200)
        with self.client.get("/static/app.js") as javascript_response:
            self.assertEqual(javascript_response.status_code, 200)

    def test_difficulty_menu_is_ordered_dummy_easy_normal_hard(self):
        page = self.client.get("/").get_data(as_text=True)
        positions = [page.index(f'value="{difficulty}"') for difficulty in (
            "dummy", "easy", "normal", "hard",
        )]
        self.assertEqual(positions, sorted(positions))

    def test_new_game_returns_python_state(self):
        response = self.client.post("/api/new", json={
            "player_class": "Sorcerer",
            "enemy_class": "Juggernaut",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["player"]["max_mana"], 180)
        self.assertEqual(response.json["enemy"]["max_health"], 170)
        self.assertEqual(response.json["player"]["weapon"]["range"], 4)

    def test_class_api_includes_weapon_combat_stats(self):
        response = self.client.get("/api/classes")
        self.assertEqual(response.status_code, 200)
        weapons = {entry["weapon"]["name"]: entry["weapon"] for entry in response.json["classes"]}
        self.assertEqual(weapons["Claymore"], {
            "name": "Claymore", "range": 4, "damage": 35, "stamina_cost": 25,
            "bonus_stat": "health", "bonus_amount": 20, "bonus": "+20 health",
        })

    def test_class_api_includes_exact_scavenge_loot_probabilities(self):
        response = self.client.get("/api/classes")
        loot = response.json["scavenge_loot"]
        self.assertEqual(sum(entry["chance"] for entry in loot), 100)
        chances = {entry["result"]: entry["chance"] for entry in loot}
        self.assertEqual(chances["Nothing"], 30)
        self.assertEqual(chances["Apple"], 12.5)
        self.assertEqual(chances["Claymore"], 5)

    def test_class_api_keeps_weapon_bonuses_out_of_base_stats(self):
        response = self.client.get("/api/classes")
        classes = {entry["name"]: entry for entry in response.json["classes"]}
        self.assertEqual(classes["Sorcerer"]["mana"], 160)
        self.assertEqual(classes["Juggernaut"]["health"], 150)
        self.assertEqual(classes["Swordsman"]["stamina"], 120)
        self.assertEqual(classes["Assassin"]["speed"], 4)
        self.assertEqual(classes["Swordsman"]["weapon"]["name"], "Sword")
        self.assertFalse(classes["Swordsman"]["ability"]["active"])
        self.assertEqual(classes["Juggernaut"]["ability"]["name"], "Super-charge")

    def test_active_class_abilities_have_class_specific_buttons(self):
        sorcerer = self.client.post("/api/new", json={
            "player_class": "Sorcerer", "enemy_class": "Assassin",
        }).json
        sorcerer_actions = {action["id"]: action for action in sorcerer["actions"]["actions"]}
        self.assertIn("resistance", sorcerer_actions)
        self.assertIn("(ability)", sorcerer_actions["resistance"]["name"])
        self.assertNotIn("super_charge", sorcerer_actions)

        juggernaut = self.client.post("/api/new", json={
            "player_class": "Juggernaut", "enemy_class": "Assassin",
        }).json
        juggernaut_actions = {
            action["id"]: action for action in juggernaut["actions"]["actions"]
        }
        self.assertIn("super_charge", juggernaut_actions)
        self.assertIn("(ability)", juggernaut_actions["super_charge"]["name"])
        self.assertNotIn("resistance", juggernaut_actions)

    def test_action_is_processed_by_python(self):
        response = self.client.post("/api/action", json={"action": "charge"})
        self.assertEqual(response.status_code, 200)
        self.assertLess(response.json["distance"], 15)
        self.assertTrue(response.json["log"])

    def test_bot_turn_can_be_deferred_until_player_animations_finish(self):
        response = self.client.post("/api/action", json={
            "action": "approach", "defer_bot": True,
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["pending_bot_turn"])
        bot_response = self.client.post("/api/bot")
        self.assertEqual(bot_response.status_code, 200)
        self.assertFalse(bot_response.json["pending_bot_turn"])

    def test_invalid_action_returns_json_error(self):
        response = self.client.post("/api/action", json={"action": "dance"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["error"], "Unknown action.")

    def test_two_player_mode_is_selected_through_flask(self):
        response = self.client.post("/api/new", json={
            "mode": "two_player",
            "player_class": "Sorcerer",
            "enemy_class": "Swordsman",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["mode"], "two_player")
        self.assertEqual(response.json["active_label"], "Player 1")


if __name__ == "__main__":
    unittest.main()
