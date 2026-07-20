"""Regression tests for combat, turns, probability, bot, and inventory rules."""

import random
import unittest

from game_engine import GameState, HAIR_COLORS, WEAPONS


class GameEngineTests(unittest.TestCase):
    def setUp(self):
        self.game = GameState(random.Random(4))
        self.game.new_game("Swordsman", "Assassin")

    def test_new_game_uses_python_class_stats(self):
        state = self.game.to_dict()
        self.assertEqual(state["player"]["max_health"], 100)
        self.assertEqual(state["player"]["weapon"]["name"], "Sword")
        self.assertEqual(state["player"]["weapon"]["stamina_cost"], 15)
        self.assertEqual(state["enemy"]["max_health"], 80)
        self.assertEqual(state["distance"], 15)
        self.assertIn(state["player"]["hair_color"], HAIR_COLORS)
        self.assertIn(state["enemy"]["hair_color"], HAIR_COLORS)

    def test_updated_weapon_damage_and_spell_costs(self):
        weapons = {weapon.name: weapon for weapon in WEAPONS}
        self.assertEqual(weapons["Daggers"].damage, 15)
        self.assertEqual(weapons["Staff"].damage, 15)
        self.assertEqual(weapons["Staff"].range, 4)
        self.game.player.mana = 10
        self.game.distance = 1
        success, _ = self.game._perform_action(
            self.game.player, self.game.enemy, "push", "player"
        )
        self.assertTrue(success)
        self.assertEqual(self.game.player.mana, 0)

    def test_fire_damage_continues_while_target_is_frozen(self):
        self.game.new_game("Sorcerer", "Assassin")
        self.game.distance = 1
        starting_health = self.game.enemy.health
        self.game._perform_action(
            self.game.player, self.game.enemy, "fireball", "player"
        )
        self.game._perform_action(
            self.game.player, self.game.enemy, "freeze", "player"
        )
        self.assertGreater(self.game.enemy.statuses["fire"], 0)
        self.assertGreater(self.game.enemy.statuses["frozen"], 0)
        self.game._process_statuses(self.game.enemy)
        self.assertEqual(self.game.enemy.health, starting_health - 30)
        self.assertEqual(self.game.enemy.statuses["fire"], 1)

    def test_starting_weapons_apply_each_stat_bonus(self):
        expected = {
            "Swordsman": ("max_stamina", 140),
            "Assassin": ("speed", 5),
            "Juggernaut": ("max_health", 170),
            "Sorcerer": ("max_mana", 180),
        }
        for class_name, (stat, value) in expected.items():
            with self.subTest(class_name=class_name):
                self.game.new_game(class_name, "Assassin")
                self.assertEqual(getattr(self.game.player, stat), value)

    def test_equipping_weapon_replaces_instead_of_stacking_bonus(self):
        player = self.game.player
        self.assertEqual(player.max_stamina, 140)
        player.equip_weapon(WEAPONS[0])
        self.assertEqual(player.max_stamina, 120)
        self.assertEqual(player.max_health, 120)
        player.equip_weapon(WEAPONS[3])
        self.assertEqual(player.max_health, 100)
        self.assertEqual(player.max_mana, 80)

    def test_attack_button_displays_active_weapon_stamina_cost(self):
        state = self.game.to_dict()
        attack = next(action for action in state["actions"]["actions"] if action["id"] == "attack")
        self.assertEqual(attack["cost"], "15 stamina")
        self.game.new_game("Juggernaut", "Assassin", mode="two_player")
        self.game.perform_player_action("approach")
        state = self.game.to_dict()
        attack = next(action for action in state["actions"]["actions"] if action["id"] == "attack")
        self.assertEqual(attack["cost"], "10 stamina")

    def test_charge_moves_using_python_speed(self):
        self.game.perform_player_action("charge")
        self.assertLess(self.game.distance, 15)
        self.assertLess(self.game.player.stamina, self.game.player.max_stamina)

    def test_approach_and_step_back_are_free_opposite_movements(self):
        starting_distance = self.game.distance
        starting_stamina = self.game.player.stamina
        self.game._perform_action(self.game.player, self.game.enemy, "approach", "player")
        approached_distance = self.game.distance
        self.assertLess(approached_distance, starting_distance)
        self.assertEqual(self.game.player.stamina, starting_stamina)
        self.game._perform_action(self.game.player, self.game.enemy, "step_back", "player")
        self.assertEqual(self.game.distance, starting_distance)
        self.assertEqual(self.game.player.stamina, starting_stamina)

    def test_attacks_and_charges_hit_at_exact_weapon_range(self):
        self.game.rng.random = lambda: .99
        self.game.distance = self.game.player.weapon.range
        enemy_health = self.game.enemy.health
        self.game._perform_action(self.game.player, self.game.enemy, "attack", "player")
        self.assertEqual(self.game.enemy.health, enemy_health - self.game.player.weapon.damage)
        self.game.new_game("Swordsman", "Assassin")
        self.game.rng.random = lambda: .99
        self.game.distance = self.game.player.weapon.range + self.game.player.speed
        enemy_health = self.game.enemy.health
        self.game._perform_action(self.game.player, self.game.enemy, "charge", "player")
        self.assertEqual(self.game.distance, self.game.player.weapon.range)
        self.assertEqual(self.game.enemy.health, enemy_health - self.game.player.weapon.damage)

    def test_successful_charge_stuns_and_grants_one_non_charge_action(self):
        self.game.new_game("Assassin", "Swordsman")
        self.game.distance = self.game.player.weapon.range
        state = self.game.perform_player_action("charge")
        self.assertEqual(state["bonus_actions"]["player"], 1)
        self.assertEqual(state["bonus_action_kind"]["player"], "charge")
        self.assertEqual(self.game.enemy.statuses["stunned"], 1)
        charge = next(action for action in state["actions"]["actions"]
                      if action["id"] == "charge")
        self.assertFalse(charge["available"])
        with self.assertRaisesRegex(ValueError, "only be used once"):
            self.game.perform_player_action("charge")
        state = self.game.perform_player_action("freeze")
        self.assertEqual(state["bonus_actions"]["player"], 3)
        with self.assertRaisesRegex(ValueError, "only be used once"):
            self.game.perform_player_action("freeze")
        self.game.perform_player_action("approach")
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("meditate")
        self.assertEqual(self.game.bonus_actions["player"], 0)
        state = self.game.to_dict()
        charge = next(action for action in state["actions"]["actions"]
                      if action["id"] == "charge")
        self.assertTrue(charge["available"])
        self.assertIsNone(self.game.bonus_action_kind["player"])

    def test_non_assassin_charge_does_not_stun_or_grant_an_action(self):
        self.game.distance = self.game.player.weapon.range
        state = self.game.perform_player_action("charge", defer_bot=True)
        self.assertEqual(state["bonus_actions"]["player"], 0)
        self.assertEqual(self.game.enemy.statuses["stunned"], 0)
        self.assertTrue(state["pending_bot_turn"])

    def test_swordsman_attack_and_charge_can_crit_for_one_point_five_damage(self):
        class CriticalRandom:
            def random(self):
                return .10

        self.game.rng = CriticalRandom()
        self.game.distance = self.game.player.weapon.range
        enemy_health = self.game.enemy.health
        success, _ = self.game._perform_action(
            self.game.player, self.game.enemy, "attack", "player"
        )
        self.assertTrue(success)
        self.assertEqual(self.game.enemy.health, enemy_health - 30)
        self.assertTrue(self.game.effects[-1]["critical"])

        self.game.player.equip_weapon(WEAPONS[0])
        self.game.player.stamina = self.game.player.max_stamina
        self.game.rng = CriticalRandom()
        self.game.distance = self.game.player.weapon.range
        enemy_health = self.game.enemy.health
        self.game._perform_action(
            self.game.player, self.game.enemy, "attack", "player"
        )
        self.assertEqual(self.game.enemy.health, enemy_health - 52.5)
        self.assertTrue(self.game.effects[-1]["critical"])

        self.game.rng = random.Random(4)
        self.game.new_game("Swordsman", "Assassin")
        self.game.rng = CriticalRandom()
        self.game.distance = self.game.player.weapon.range + self.game.player.speed
        enemy_health = self.game.enemy.health
        self.game._perform_action(
            self.game.player, self.game.enemy, "charge", "player"
        )
        self.assertEqual(self.game.enemy.health, enemy_health - 30)
        self.assertTrue(self.game.effects[-1]["critical"])

    def test_juggernaut_super_charge_uses_mana_and_has_two_turn_cooldown(self):
        self.game.new_game("Juggernaut", "Assassin", mode="two_player")
        self.game.distance = self.game.player.weapon.range + self.game.player.speed * 2
        starting_stamina = self.game.player.stamina
        starting_mana = self.game.player.mana
        enemy_health = self.game.enemy.health
        state = self.game.perform_player_action("super_charge")
        self.assertEqual(self.game.distance, self.game.player.weapon.range)
        self.assertEqual(
            self.game.player.stamina,
            starting_stamina - self.game.player.weapon.stamina_cost,
        )
        self.assertEqual(self.game.player.mana, starting_mana - 15)
        self.assertEqual(
            self.game.enemy.health,
            enemy_health - self.game.player.weapon.damage,
        )
        self.assertEqual(self.game.effects[0]["action"], "super_charge")
        self.assertEqual(state["ability_cooldowns"]["player"]["super_charge"], 2)

        self.game.perform_player_action("step_back")
        state = self.game.to_dict()
        self.assertFalse(next(
            command for command in state["actions"]["actions"]
            if command["id"] == "super_charge"
        )["available"])
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.ability_cooldowns["player"]["super_charge"], 1)
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.ability_cooldowns["player"]["super_charge"], 0)

    def test_resistance_reduces_spell_effect_and_weapon_damage(self):
        self.game.new_game("Swordsman", "Sorcerer", mode="two_player")
        self.game.enemy.statuses["resistance"] = 2
        self.game.distance = self.game.player.weapon.range
        enemy_health = self.game.enemy.health
        self.game.rng.random = lambda: .99
        self.game._perform_action(
            self.game.player, self.game.enemy, "attack", "player"
        )
        self.assertEqual(self.game.enemy.health, enemy_health - 10)

        self.game.enemy.health = enemy_health
        self.game.distance = 4
        self.game._perform_action(
            self.game.player, self.game.enemy, "fireball", "player"
        )
        self.assertEqual(self.game.enemy.health, enemy_health - 7.5)
        before_tick = self.game.enemy.health
        self.game._process_statuses(self.game.enemy)
        self.assertEqual(self.game.enemy.health, before_tick - 5)

    def test_resistance_active_two_turns_then_cools_down_for_two_more(self):
        self.game.new_game("Sorcerer", "Assassin", mode="two_player")
        state = self.game.perform_player_action("resistance")
        self.assertEqual(state["player"]["statuses"]["resistance"], 2)
        self.assertEqual(state["ability_cooldowns"]["player"]["resistance"], 4)
        self.assertEqual(self.game.player.mana, self.game.player.max_mana - 10)
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.player.statuses["resistance"], 1)
        self.assertEqual(self.game.ability_cooldowns["player"]["resistance"], 3)
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.player.statuses["resistance"], 0)
        self.assertEqual(self.game.ability_cooldowns["player"]["resistance"], 2)
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.ability_cooldowns["player"]["resistance"], 1)
        self.game.perform_player_action("step_back")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.ability_cooldowns["player"]["resistance"], 0)

        self.game.new_game("Sorcerer", "Assassin", mode="two_player")
        self.game.distance = 5
        self.game.perform_player_action("freeze")
        remaining = self.game.bonus_actions["player"]
        self.game.perform_player_action("resistance")
        self.assertEqual(self.game.bonus_actions["player"], remaining - 1)

    def test_charge_logs_when_movement_reaches_range_without_attack_stamina(self):
        self.game.distance = self.game.player.weapon.range + self.game.player.speed
        self.game.player.stamina = 10 + self.game.player.weapon.stamina_cost - 1
        success, message = self.game._perform_action(
            self.game.player, self.game.enemy, "charge", "player"
        )
        self.assertTrue(success)
        self.assertIn("does not have enough stamina to attack", message)
        self.game.message = message
        self.game._add_log(message)
        self.assertIn("does not have enough stamina to attack",
                      self.game.log[0]["message"])

    def test_movement_actions_emit_distance_animation_data(self):
        approach_state = self.game.perform_player_action("approach")
        movement = approach_state["effects"][0]
        self.assertEqual(movement["type"], "move")
        self.assertEqual(movement["action"], "approach")
        self.assertEqual(movement["from_distance"], 15)
        self.assertLess(movement["to_distance"], movement["from_distance"])

    def test_close_attack_uses_weapon_damage(self):
        self.game.distance = 3
        enemy_health = self.game.enemy.health
        state = self.game.perform_player_action("attack")
        damage = state["effects"][0]["damage"]
        self.assertEqual(self.game.enemy.health, enemy_health - damage)

    def test_successful_attack_and_charge_emit_strike_animation(self):
        self.game.distance = 3
        attack_state = self.game.perform_player_action("attack")
        self.assertEqual(attack_state["effects"][0]["type"], "strike")
        self.assertEqual(attack_state["effects"][0]["from"], "player")
        self.assertEqual(attack_state["effects"][0]["weapon"], "Sword")
        self.game.new_game("Swordsman", "Assassin")
        self.game.distance = 5
        charge_state = self.game.perform_player_action("charge")
        self.assertEqual(charge_state["effects"][0]["type"], "move")
        self.assertEqual(charge_state["effects"][0]["action"], "charge")
        self.assertTrue(charge_state["effects"][1]["hit"])
        self.assertEqual(charge_state["effects"][1]["weapon"], "Sword")

    def test_missed_attack_costs_stamina_but_missed_charge_does_not_swing(self):
        initial_stamina = self.game.player.stamina
        self.game.effects = []
        self.game._perform_action(self.game.player, self.game.enemy, "attack", "player")
        self.assertEqual(self.game.player.stamina, initial_stamina - 15)
        self.assertFalse(self.game.effects[0]["hit"])
        self.game.new_game("Swordsman", "Assassin")
        initial_stamina = self.game.player.stamina
        self.game.effects = []
        self.game._perform_action(self.game.player, self.game.enemy, "charge", "player")
        self.assertEqual(self.game.player.stamina, initial_stamina - 10)
        self.assertFalse(any(effect["type"] == "strike" for effect in self.game.effects))

    def test_defeat_effect_identifies_loser_and_weapon_throw_direction(self):
        self.game.enemy.health = 1
        self.game.distance = 3
        state = self.game.perform_player_action("attack")
        defeat = next(effect for effect in state["effects"] if effect["type"] == "defeat")
        self.assertEqual(defeat["from"], "enemy")
        self.assertEqual(defeat["winner"], "player")
        self.assertIn(defeat["throw_direction"], (-1, 1))

    def test_fireball_cost_and_status_are_processed_in_python(self):
        self.game.distance = 5
        self.game.player.mana = 60
        self.game.perform_player_action("fireball")
        self.assertLessEqual(self.game.player.mana, 40)
        self.assertGreaterEqual(self.game.enemy.statuses["fire"], 0)

    def test_spell_accuracy_falls_linearly_between_hit_and_max_range(self):
        class FixedRandom:
            def __init__(self, value):
                self.value = value

            def random(self):
                return self.value

        self.game.distance = 6  # Fireball is 50% accurate here: hit 4, maximum 8.
        self.game.rng = FixedRandom(0.49)
        self.assertTrue(self.game._spell_hits("fireball"))
        self.game.rng = FixedRandom(0.50)
        self.assertFalse(self.game._spell_hits("fireball"))
        self.game.distance = 4
        self.assertTrue(self.game._spell_hits("fireball"))
        self.game.distance = 8
        self.assertFalse(self.game._spell_hits("fireball"))

    def test_missed_spells_emit_projectiles_without_dealing_damage(self):
        self.game.distance = 8
        enemy_health = self.game.enemy.health
        success, message = self.game._perform_action(
            self.game.player, self.game.enemy, "fireball", "player"
        )
        self.assertTrue(success)
        self.assertIn("misses", message)
        self.assertEqual(self.game.enemy.health, enemy_health)
        self.assertEqual(self.game.effects[-1]["type"], "fireball")
        self.assertFalse(self.game.effects[-1]["hit"])
        self.assertIn(self.game.effects[-1]["miss_y"], (-1, 1))

        self.game.player.mana = 10
        self.game.distance = 16
        success, _ = self.game._perform_action(
            self.game.player, self.game.enemy, "push", "player"
        )
        self.assertTrue(success)
        self.assertEqual(self.game.effects[-1]["type"], "push")
        self.assertFalse(self.game.effects[-1]["hit"])

    def test_freeze_grants_three_different_actions_before_bot_turn(self):
        self.game.distance = 5
        state = self.game.perform_player_action("freeze")
        self.assertEqual(self.game.bonus_actions["player"], 3)
        self.assertEqual(self.game.turn, 1)
        freeze = next(action for action in state["actions"]["spells"]
                      if action["id"] == "freeze")
        self.assertFalse(freeze["available"])
        with self.assertRaisesRegex(ValueError, "only be used once"):
            self.game.perform_player_action("freeze")
        self.game.perform_player_action("charge")
        self.assertEqual(self.game.bonus_actions["player"], 2)
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.bonus_actions["player"], 1)
        self.assertEqual(self.game.turn, 1)
        with self.assertRaisesRegex(ValueError, "must all be different"):
            self.game.perform_player_action("approach")
        approach = next(action for action in self.game.to_dict()["actions"]["actions"]
                        if action["id"] == "approach")
        self.assertFalse(approach["available"])
        self.game.perform_player_action("step_back")
        self.assertEqual(self.game.bonus_actions["player"], 0)
        self.assertEqual(self.game.turn, 2)
        self.game.player.mana = 40
        state = self.game.to_dict()
        freeze = next(action for action in state["actions"]["spells"]
                      if action["id"] == "freeze")
        charge = next(action for action in state["actions"]["actions"]
                      if action["id"] == "charge")
        self.assertTrue(freeze["available"])
        self.assertTrue(charge["available"])
        self.assertIsNone(self.game.bonus_action_kind["player"])

    def test_freeze_bonus_actions_keep_same_player_active_in_two_player_mode(self):
        self.game.new_game("Sorcerer", "Assassin", mode="two_player")
        self.game.distance = 5
        self.game.perform_player_action("freeze")
        self.assertEqual(self.game.active_side, "player")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.active_side, "player")
        self.game.perform_player_action("step_back")
        self.assertEqual(self.game.active_side, "player")
        self.game.perform_player_action("meditate")
        self.assertEqual(self.game.active_side, "enemy")

    def test_freeze_bonus_can_use_juggernaut_super_charge_once(self):
        self.game.new_game("Juggernaut", "Assassin", mode="two_player")
        self.game.player.mana = 55
        self.game.distance = 5
        state = self.game.perform_player_action("freeze")
        super_charge = next(
            action for action in state["actions"]["actions"]
            if action["id"] == "super_charge"
        )
        self.assertTrue(super_charge["available"])
        self.game.perform_player_action("super_charge")
        self.assertEqual(self.game.bonus_actions["player"], 2)
        state = self.game.to_dict()
        super_charge = next(
            action for action in state["actions"]["actions"]
            if action["id"] == "super_charge"
        )
        self.assertFalse(super_charge["available"])

    def test_dummy_bot_skips_its_action(self):
        self.game.new_game("Swordsman", "Assassin", bot_difficulty="dummy")
        enemy_stamina = self.game.enemy.stamina
        state = self.game.perform_player_action("approach")
        self.assertEqual(self.game.enemy.stamina, enemy_stamina)
        self.assertEqual(state["bot_difficulty"], "dummy")
        self.assertEqual(state["log"][0]["message"], "Dummy stares blankly into space.")
        self.assertEqual(state["log"][0]["turn"], 1)

    def test_deferred_singleplayer_action_waits_before_bot_decision(self):
        enemy_stamina = self.game.enemy.stamina
        state = self.game.perform_player_action("approach", defer_bot=True)
        self.assertTrue(state["pending_bot_turn"])
        self.assertEqual(self.game.enemy.stamina, enemy_stamina)
        self.assertIn("approaches", state["log"][0]["message"])
        bot_state = self.game.perform_pending_bot_turn()
        self.assertFalse(bot_state["pending_bot_turn"])
        self.assertGreaterEqual(len(bot_state["log"]), 2)

    def test_deferred_bot_phase_cannot_run_twice(self):
        self.game.perform_player_action("approach", defer_bot=True)
        self.game.perform_pending_bot_turn()
        with self.assertRaisesRegex(ValueError, "no bot turn waiting"):
            self.game.perform_pending_bot_turn()

    def test_all_four_bot_difficulties_are_valid(self):
        for difficulty in ("dummy", "easy", "normal", "hard"):
            with self.subTest(difficulty=difficulty):
                state = self.game.new_game(
                    "Swordsman", "Assassin", bot_difficulty=difficulty
                )
                self.assertEqual(state["bot_difficulty"], difficulty)

    def test_hard_bot_selects_a_visible_lethal_attack(self):
        self.game.new_game("Swordsman", "Assassin", bot_difficulty="hard")
        self.game.distance = self.game.enemy.weapon.range
        self.game.player.health = self.game.enemy.weapon.damage
        self.game.player.inventory = ["Bandage", "Apple"]
        self.assertEqual(self.game._choose_bot_action(), "attack")

    def test_hard_bot_retreats_when_critical_and_threatened(self):
        self.game.new_game("Swordsman", "Assassin", bot_difficulty="hard")
        self.game.enemy.health = 10
        self.game.distance = self.game.player.weapon.range
        self.assertEqual(self.game._choose_bot_action(), "escape")

    def test_hard_bot_balances_safe_scavenging_with_closing_distance(self):
        decisions = set()
        for seed in range(30):
            game = GameState(random.Random(seed))
            game.new_game("Swordsman", "Assassin", bot_difficulty="hard")
            game.distance = 20
            decisions.add(game._choose_bot_action())
        self.assertIn("scavenge", decisions)
        self.assertTrue(decisions.intersection({"approach", "charge"}))

    def test_hard_sorcerer_kites_when_inside_enemy_threat_range(self):
        self.game.new_game("Swordsman", "Sorcerer", bot_difficulty="hard")
        self.game.distance = self.game.player.weapon.range
        action = self.game._choose_bot_action()
        self.assertIn(action, {"push", "escape", "step_back", "resistance"})

    def test_hard_sorcerer_uses_spells_from_a_safe_working_distance(self):
        self.game.new_game("Swordsman", "Sorcerer", bot_difficulty="hard")
        self.game.distance = 7
        action = self.game._choose_bot_action()
        self.assertIn(action, {"fireball", "freeze", "poison", "push"})

    def test_hard_sorcerer_closes_carefully_when_beyond_spell_range(self):
        decisions = set()
        for seed in range(12):
            game = GameState(random.Random(seed))
            game.new_game("Swordsman", "Sorcerer", bot_difficulty="hard")
            game.distance = 12
            decisions.add(game._choose_bot_action())
        self.assertTrue(decisions.issubset({"approach", "scavenge"}))
        self.assertIn("approach", decisions)

    def test_hard_assassin_prioritizes_a_stunning_charge_setup(self):
        self.game.new_game("Swordsman", "Assassin", bot_difficulty="hard")
        self.game.distance = (
            self.game.enemy.weapon.range + self.game.enemy.speed
        )
        self.assertEqual(self.game._choose_bot_action(), "charge")

    def test_hard_juggernaut_uses_super_charge_when_it_will_land(self):
        self.game.new_game("Swordsman", "Juggernaut", bot_difficulty="hard")
        self.game.distance = (
            self.game.enemy.weapon.range + self.game.enemy.speed * 2
        )
        self.assertEqual(self.game._choose_bot_action(), "super_charge")

    def test_hard_swordsman_prefers_weapon_pressure_in_melee(self):
        self.game.new_game("Assassin", "Swordsman", bot_difficulty="hard")
        self.game.distance = self.game.enemy.weapon.range
        self.assertEqual(self.game._choose_bot_action(), "attack")

    def test_low_health_bots_stop_retreating_at_safe_distance(self):
        self.game.enemy.health = 1
        self.game.enemy.mana = 0
        self.game.enemy.inventory = []
        self.game.distance = 20
        self.game.bot_difficulty = "normal"
        self.assertEqual(self.game._choose_bot_action(), "meditate")
        self.game.bot_difficulty = "hard"
        self.assertEqual(self.game._choose_bot_action(), "meditate")

        self.game.distance = 19
        self.game.bot_difficulty = "normal"
        self.assertEqual(self.game._choose_bot_action(), "escape")

    def test_bot_freeze_uses_three_different_critical_followups(self):
        self.game.new_game("Swordsman", "Sorcerer", bot_difficulty="hard")
        self.game.distance = 5
        self.game.enemy.health = 10
        self.game._choose_bot_action = lambda: "freeze"
        self.game._perform_bot_turn()
        self.assertEqual(
            [effect["type"] for effect in self.game.effects],
            ["freeze", "resistance", "move", "move"],
        )
        self.assertEqual(self.game.bonus_action_history["enemy"], [])
        self.assertEqual(self.game.bonus_actions["enemy"], 0)

    def test_bot_freeze_uses_three_different_offensive_followups(self):
        self.game.new_game("Swordsman", "Sorcerer", bot_difficulty="hard")
        self.game.distance = self.game.enemy.weapon.range
        starting_health = self.game.player.health
        self.game._choose_bot_action = lambda: "freeze"
        self.game._perform_bot_turn()
        self.assertEqual(
            [effect["type"] for effect in self.game.effects],
            ["freeze", "strike", "poison", "fireball"],
        )
        expected_damage = 5 + self.game.enemy.weapon.damage + 5 + 15
        self.assertEqual(self.game.player.health, starting_health - expected_damage)

    def test_easy_bot_chooses_a_legal_fight_aware_action(self):
        self.game.new_game("Swordsman", "Assassin", bot_difficulty="easy")
        self.game.distance = 20
        action = self.game._choose_bot_action()
        self.assertIn(action, self.game._bot_legal_actions())

    def test_unknown_action_does_not_advance_game(self):
        with self.assertRaisesRegex(ValueError, "Unknown action"):
            self.game.perform_player_action("dance")
        self.assertEqual(self.game.turn, 1)

    def test_two_player_mode_alternates_human_turns(self):
        self.game.new_game("Swordsman", "Assassin", mode="two_player")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.active_side, "enemy")
        self.game.perform_player_action("approach")
        self.assertEqual(self.game.active_side, "player")
        self.assertEqual(self.game.turn, 2)

    def test_two_player_actions_use_the_active_players_stats(self):
        self.game.new_game("Juggernaut", "Assassin", mode="two_player")
        self.game.perform_player_action("approach")
        enemy_stamina = self.game.enemy.stamina
        self.game.perform_player_action("charge")
        self.assertLess(self.game.enemy.stamina, enemy_stamina)

    def test_bot_heal_spends_mana_and_cannot_repeat_without_mana(self):
        self.game.enemy.health = 10
        self.game.enemy.mana = 25
        self.assertEqual(self.game._choose_bot_action(), "heal")
        success, _ = self.game._perform_action(self.game.enemy, self.game.player, "heal", "enemy")
        self.assertTrue(success)
        self.assertEqual(self.game.enemy.mana, 0)
        success, message = self.game._perform_action(self.game.enemy, self.game.player, "heal", "enemy")
        self.assertFalse(success)
        self.assertEqual(message, "Not enough mana.")

    def test_bot_healing_item_is_consumed(self):
        self.game.enemy.health = 10
        self.game.enemy.inventory = ["Bandage"]
        self.assertEqual(self.game._choose_bot_action(), "bandage")
        self.game._perform_action(self.game.enemy, self.game.player, "bandage", "enemy")
        self.assertNotIn("Bandage", self.game.enemy.inventory)

    def test_duplicate_inventory_items_are_consumed_one_at_a_time(self):
        self.game.enemy.inventory = ["Apple", "Apple"]
        success, _ = self.game._perform_action(self.game.enemy, self.game.player, "apple", "enemy")
        self.assertTrue(success)
        self.assertEqual(self.game.enemy.inventory, ["Apple"])

    def test_scavenge_rolls_independent_zero_to_five_costs(self):
        class ScavengeRandom:
            def __init__(self):
                self.values = iter((2, 4, 20))

            def randint(self, start, end):
                return next(self.values)

        self.game.rng = ScavengeRandom()
        starting_stamina = self.game.player.stamina
        starting_mana = self.game.player.mana
        success, message = self.game._perform_action(
            self.game.player, self.game.enemy, "scavenge", "player"
        )
        self.assertTrue(success)
        self.assertEqual(self.game.player.stamina, starting_stamina - 2)
        self.assertEqual(self.game.player.mana, starting_mana - 4)
        self.assertIn("spending 2 stamina and 4 mana", message)

    def test_round_transition_provides_no_automatic_stat_benefits(self):
        self.game.player.health -= 10
        self.game.player.stamina -= 10
        self.game.player.mana -= 10
        before = (self.game.player.health, self.game.player.stamina, self.game.player.mana)
        self.game._regenerate()
        self.assertEqual(
            (self.game.player.health, self.game.player.stamina, self.game.player.mana),
            before,
        )

    def test_round_regeneration_no_longer_changes_stamina_or_mana(self):
        self.game.player.stamina -= 10
        self.game.player.mana -= 10
        self.game.enemy.stamina -= 10
        self.game.enemy.mana -= 10
        self.game._regenerate()
        self.assertEqual(self.game.player.stamina, self.game.player.max_stamina - 10)
        self.assertEqual(self.game.player.mana, self.game.player.max_mana - 10)
        self.assertEqual(self.game.enemy.stamina, self.game.enemy.max_stamina - 10)
        self.assertEqual(self.game.enemy.mana, self.game.enemy.max_mana - 10)

    def test_holy_tick_restores_health_and_mana(self):
        self.game.player.health -= 10
        self.game.player.mana -= 10
        self.game.player.statuses["holy"] = 2
        before = (self.game.player.health, self.game.player.mana)
        self.game._process_statuses(self.game.player)
        self.assertEqual(
            (self.game.player.health, self.game.player.mana),
            (before[0] + 5, before[1] + 5),
        )
        self.assertEqual(self.game.player.statuses["holy"], 1)
        self.assertIn("mana by 5", self.game.log[0]["message"])

    def test_meditate_rolls_each_stat_independently_and_reports_results(self):
        class MeditationRandom:
            def __init__(self):
                self.values = iter((0, 3, 5))

            def randint(self, start, end):
                return next(self.values)

        self.game.rng = MeditationRandom()
        self.game.player.health -= 10
        self.game.player.stamina -= 10
        self.game.player.mana -= 10
        success, message = self.game._perform_action(
            self.game.player, self.game.enemy, "meditate", "player"
        )
        self.assertTrue(success)
        self.assertEqual(self.game.player.health, self.game.player.max_health - 10)
        self.assertEqual(self.game.player.stamina, self.game.player.max_stamina - 7)
        self.assertEqual(self.game.player.mana, self.game.player.max_mana - 5)
        self.assertIn("+0 HP, +3 stamina, +5 mana", message)
        self.assertEqual(self.game.effects[-1]["type"], "meditate")

    def test_attack_is_unavailable_without_weapon_stamina_even_out_of_range(self):
        self.game.distance = 99
        self.game.player.stamina = self.game.player.weapon.stamina_cost - 1
        attack = next(
            action for action in self.game.to_dict()["actions"]["actions"]
            if action["id"] == "attack"
        )
        self.assertFalse(attack["available"])

    def test_bot_rejects_scavenged_weapons(self):
        class WeaponRandom:
            def randint(self, start, end):
                return 90

            def choice(self, choices):
                return WEAPONS[0]

        self.game.rng = WeaponRandom()
        original_weapon = self.game.enemy.weapon
        success, message = self.game._perform_action(self.game.enemy, self.game.player, "scavenge", "enemy")
        self.assertTrue(success)
        self.assertIn("leaves it behind", message)
        self.assertEqual(self.game.enemy.weapon, original_weapon)
        self.assertIsNone(self.game.pending_weapon)

    def test_player_weapon_choice_pauses_actions_until_resolved(self):
        self.game.pending_weapon = "Claymore"
        self.game.pending_weapon_side = "player"
        with self.assertRaisesRegex(ValueError, "Choose whether to equip"):
            self.game.perform_player_action("approach")
        self.game.resolve_weapon(False)
        self.assertIsNone(self.game.pending_weapon)

    def test_singleplayer_bot_turn_waits_for_weapon_choice(self):
        self.game.pending_weapon = "Claymore"
        self.game.pending_weapon_side = "player"
        turn_before = self.game.turn
        self.game.resolve_weapon(False)
        self.assertGreater(self.game.turn, turn_before)


if __name__ == "__main__":
    unittest.main()
