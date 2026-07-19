"""Authoritative combat, turn, bot, inventory, log, and serialization rules.

Keep balance changes here so Flask, both modes, tests, and the app agree.
"""

import random
from dataclasses import dataclass, field


#OOP assets: setup data shared by console and web versions
@dataclass(frozen=True)
class Weapon:
    name: str
    range: int
    damage: int
    stamina_cost: int
    bonus_stat: str
    bonus_amount: int

    def to_dict(self):
        return {
            "name": self.name,
            "range": self.range,
            "damage": self.damage,
            "stamina_cost": self.stamina_cost,
            "bonus_stat": self.bonus_stat,
            "bonus_amount": self.bonus_amount,
            "bonus": f"+{self.bonus_amount} {self.bonus_stat}",
        }


@dataclass(frozen=True)
class CharacterClass:
    name: str
    weapon: Weapon
    max_health: int
    max_stamina: int
    max_mana: int
    speed: int

    #creates fresh player stats from the selected class
    def create_player(self):
        player = Player(
            class_name=self.name,
            weapon=self.weapon,
            health=self.max_health,
            max_health=self.max_health,
            stamina=self.max_stamina,
            max_stamina=self.max_stamina,
            mana=self.max_mana,
            max_mana=self.max_mana,
            speed=self.speed,
        )
        player.apply_weapon_bonus(self.weapon)
        return player

    def to_dict(self):
        # Class information always exposes the unmodified base stats. The
        # equipped weapon's bonus belongs to the Player and can change when a
        # scavenged weapon is equipped.
        return {
            "name": self.name,
            "weapon": self.weapon.to_dict(),
            "health": self.max_health,
            "stamina": self.max_stamina,
            "mana": self.max_mana,
            "speed": self.speed,
            "ability": CLASS_ABILITY_DETAILS[self.name].copy(),
        }


@dataclass
class Player:
    class_name: str
    weapon: Weapon
    health: int
    max_health: int
    stamina: int
    max_stamina: int
    mana: int
    max_mana: int
    speed: int
    hair_color: str = "#0b1017"
    inventory: list[str] = field(default_factory=list)
    statuses: dict[str, int] = field(default_factory=lambda: {
        "fire": 0,
        "holy": 0,
        "poison": 0,
        "frozen": 0,
        "stunned": 0,
        "resistance": 0,
    })

    def heal_stat(self, stat, amount):
        maximum = getattr(self, f"max_{stat}")
        setattr(self, stat, min(getattr(self, stat) + amount, maximum))

    def apply_weapon_bonus(self, weapon, direction=1):
        """Add or remove a weapon's bonus from current and maximum stats."""
        amount = weapon.bonus_amount * direction
        stat = weapon.bonus_stat
        if stat == "speed":
            self.speed = max(0, self.speed + amount)
            return
        maximum_name = f"max_{stat}"
        new_maximum = max(1 if stat == "health" else 0, getattr(self, maximum_name) + amount)
        setattr(self, maximum_name, new_maximum)
        current = getattr(self, stat) + amount
        setattr(self, stat, max(1 if stat == "health" else 0, min(current, new_maximum)))

    def equip_weapon(self, weapon):
        """Swap weapons while removing the old bonus and applying the new one."""
        self.apply_weapon_bonus(self.weapon, -1)
        self.weapon = weapon
        self.apply_weapon_bonus(weapon)

    def to_dict(self):
        return {
            "class_name": self.class_name,
            "weapon": self.weapon.to_dict(),
            "health": self.health,
            "max_health": self.max_health,
            "stamina": self.stamina,
            "max_stamina": self.max_stamina,
            "mana": self.mana,
            "max_mana": self.max_mana,
            "speed": self.speed,
            "hair_color": self.hair_color,
            "inventory": self.inventory.copy(),
            "statuses": self.statuses.copy(),
        }


# Balance tables also feed the picker, HUD, command buttons, and tutorial.
WEAPONS = (
    Weapon("Claymore", 4, 35, 25, "health", 20),
    Weapon("Sword", 3, 20, 15, "stamina", 20),
    Weapon("Daggers", 2, 15, 10, "speed", 1),
    Weapon("Staff", 4, 15, 15, "mana", 20),
)

CLASSES = (
    CharacterClass("Assassin", WEAPONS[2], 80, 100, 80, 4),
    CharacterClass("Juggernaut", WEAPONS[0], 150, 120, 40, 2),
    CharacterClass("Sorcerer", WEAPONS[3], 50, 80, 160, 4),
    CharacterClass("Swordsman", WEAPONS[1], 100, 120, 60, 3),
)

CLASS_LOOKUP = {character.name: character for character in CLASSES}
WEAPON_LOOKUP = {weapon.name: weapon for weapon in WEAPONS}
ITEMS = ("Apple", "Bandage", "Steak", "HolyWater")
HAIR_COLORS = ("#0b1017", "#65472f", "#e2c36f", "#e8e8e2")
SPELL_HIT_RANGES = {"fireball": 4, "freeze": 5, "poison": 6, "push": 8, "pull": 8}
SCAVENGE_NOTHING_CHANCE = 30
SCAVENGE_ITEM_CHANCE = 50
SCAVENGE_WEAPON_CHANCE = 20
BOT_RETREAT_DISTANCE = 20
CLASS_ABILITY_DETAILS = {
    "Assassin": {
        "name": "",
        "active": False,
        "description": (
            "Passive: a successful Charge stuns the target and grants one "
            "extra action. Charge can only be used once during that turn."
        ),
    },
    "Swordsman": {
        "name": "",
        "active": False,
        "description": (
            "Passive: every successful Attack or Charge has a 20% chance to "
            "deal 1.5× damage."
        ),
    },
    "Juggernaut": {
        "name": "Super-charge",
        "active": True,
        "description": (
            "Active: spend 15 mana to charge at twice normal speed, then "
            "attack if the equipped weapon reaches the target. After use, "
            "Super-charge has a 2-turn cooldown."
        ),
    },
    "Sorcerer": {
        "name": "Resistance",
        "active": True,
        "description": (
            "Active: spend 10 mana and one action for two turns of 50% damage "
            "reduction against every incoming damage type. It then remains on "
            "cooldown for two more turns, so it can be reused four turns after "
            "activation."
        ),
    },
}

# Tuple format: internal id, visible name, emoji, visible cost/details.
ACTION_DETAILS = {
    "actions": (
        ("approach", "Approach", "🚶‍➡️", "No cost"),
        ("step_back", "Step Back", "🚶", "No cost"),
        ("attack", "Attack", "⚔️", "Weapon stamina"),
        ("charge", "Charge", "🏃‍➡️", "10 + attack stamina"),
        ("escape", "Escape", "🏃", "10 stamina"),
        ("meditate", "Meditate", "🧘", "Random +0–5 all stats"),
        ("scavenge", "Scavenge", "🔍", "Random 0–5 stamina / mana"),
    ),
    "spells": (
        ("fireball", "Fireball", "🔥", "25 mana / hit 4 / max 8"),
        ("freeze", "Freeze", "🧊", "40 mana · hit 5 / max 10"),
        ("heal", "Heal", "❤️", "25 mana / +20 HP"),
        ("poison", "Poison", "☠️", "25 mana / hit 6 / max 12"),
        ("push", "Push", "🫸", "10 mana / hit 8 / max 16"),
        ("pull", "Pull", "🤜", "10 mana / hit 8 / max 16"),
    ),
    "items": (
        ("apple", "Apple", "🍎", "+10 HP / +20 mana"),
        ("bandage", "Bandage", "🩹", "+20 HP"),
        ("holywater", "Holy Water", "✝️", "+10 HP / 2 Holy ticks"),
        ("steak", "Steak", "🥩", "+5 HP / +20 stamina"),
    ),
}


class GameState:
    """Own one match and enforce its legal state transitions."""
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.player = None
        self.enemy = None
        self.turn = 1
        self.distance = 15
        self.game_over = False
        self.winner = None
        self.log = []
        self.message = "Choose your fighter"
        self.last_effect = None
        self.effects = []
        self.pending_weapon = None
        self.pending_weapon_side = None
        self.mode = "singleplayer"
        self.bot_difficulty = "normal"
        self.active_side = "player"
        self.bonus_actions = {"player": 0, "enemy": 0}
        self.bonus_action_history = {"player": [], "enemy": []}
        self.bonus_action_kind = {"player": None, "enemy": None}
        self.resistance_fresh = {"player": False, "enemy": False}
        self.ability_cooldowns = {
            "player": {"super_charge": 0, "resistance": 0},
            "enemy": {"super_charge": 0, "resistance": 0},
        }
        self.ability_cooldown_fresh = {
            "player": {"super_charge": False, "resistance": False},
            "enemy": {"super_charge": False, "resistance": False},
        }
        self.pending_bot_turn = False

    #starts either a singleplayer or two-player game
    def new_game(self, player_class, enemy_class="random", mode="singleplayer",
                 bot_difficulty="normal", player_hair=None, enemy_hair=None):
        if player_class not in CLASS_LOOKUP:
            raise ValueError("Unknown player class.")
        if mode not in ("singleplayer", "two_player"):
            raise ValueError("Unknown game mode.")
        if bot_difficulty not in ("dummy", "easy", "normal", "hard"):
            raise ValueError("Unknown bot difficulty.")
        if enemy_class == "random":
            enemy_class = self.rng.choice(CLASSES).name
        if enemy_class not in CLASS_LOOKUP:
            raise ValueError("Unknown opponent class.")

        self.player = CLASS_LOOKUP[player_class].create_player()
        self.enemy = CLASS_LOOKUP[enemy_class].create_player()
        self.player.hair_color = player_hair if player_hair in HAIR_COLORS else self.rng.choice(HAIR_COLORS)
        self.enemy.hair_color = enemy_hair if enemy_hair in HAIR_COLORS else self.rng.choice(HAIR_COLORS)
        self.turn = 1
        self.distance = 15
        self.game_over = False
        self.winner = None
        self.log = []
        self.last_effect = None
        self.effects = []
        self.pending_weapon = None
        self.pending_weapon_side = None
        self.mode = mode
        self.bot_difficulty = bot_difficulty
        self.active_side = "player"
        self.bonus_actions = {"player": 0, "enemy": 0}
        self.bonus_action_history = {"player": [], "enemy": []}
        self.bonus_action_kind = {"player": None, "enemy": None}
        self.resistance_fresh = {"player": False, "enemy": False}
        self.ability_cooldowns = {
            "player": {"super_charge": 0, "resistance": 0},
            "enemy": {"super_charge": 0, "resistance": 0},
        }
        self.ability_cooldown_fresh = {
            "player": {"super_charge": False, "resistance": False},
            "enemy": {"super_charge": False, "resistance": False},
        }
        self.pending_bot_turn = False
        self.message = f"{player_class} faces {enemy_class}."
        return self.to_dict()

    #routes the action through singleplayer or two-player turn rules
    def perform_player_action(self, action, defer_bot=False):
        self._require_game()
        if self.game_over:
            raise ValueError("The duel is already over.")
        if self.pending_weapon:
            raise ValueError("Choose whether to equip the found weapon first.")

        if self.mode == "two_player":
            return self._perform_two_player_action(action)

        self.last_effect = None
        self.effects = []
        using_bonus_action = self.bonus_actions["player"] > 0
        history = self.bonus_action_history["player"]
        if action in ("charge", "freeze") and action in history:
            raise ValueError(f"{action.title()} can only be used once per turn.")
        if using_bonus_action and self.bonus_action_kind["player"] == "freeze" \
                and action in history:
            raise ValueError("Freeze bonus actions must all be different.")
        success, message = self._perform_action(self.player, self.enemy, action, "player")
        if not success:
            raise ValueError(message)
        self.message = message
        self._add_log(message)
        if self._check_winner():
            return self.to_dict()
        history.append(action)
        if using_bonus_action:
            self.bonus_actions["player"] -= 1
        if self.bonus_actions["player"] > 0:
            return self.to_dict()
        if self.pending_weapon:
            return self.to_dict()

        self._clear_bonus_state("player")
        if defer_bot:
            self.pending_bot_turn = True
            return self.to_dict()
        self._perform_bot_turn()
        self._clear_bonus_state("enemy")
        if self._check_winner():
            return self.to_dict()

        self.turn += 1
        self._regenerate()
        self._process_statuses(self.player)
        self._process_statuses(self.enemy)
        self._check_winner()
        return self.to_dict()

    def perform_pending_bot_turn(self):
        """Resolve a deferred singleplayer bot phase after player animations."""
        self._require_game()
        if self.mode != "singleplayer" or not self.pending_bot_turn:
            raise ValueError("There is no bot turn waiting.")
        self.pending_bot_turn = False
        self.last_effect = None
        self.effects = []
        self._perform_bot_turn()
        self._clear_bonus_state("enemy")
        if not self._check_winner():
            self.turn += 1
            self._regenerate()
            self._process_statuses(self.player)
            self._process_statuses(self.enemy)
            self._check_winner()
        return self.to_dict()

    #both players use the same Python rules and alternate actions
    def _perform_two_player_action(self, action):
        side = self.active_side
        actor = self.player if side == "player" else self.enemy
        target = self.enemy if side == "player" else self.player
        self.last_effect = None
        self.effects = []
        using_bonus_action = self.bonus_actions[side] > 0
        history = self.bonus_action_history[side]
        if action in ("charge", "freeze") and action in history:
            raise ValueError(f"{action.title()} can only be used once per turn.")
        if using_bonus_action and self.bonus_action_kind[side] == "freeze" \
                and action in history:
            raise ValueError("Freeze bonus actions must all be different.")
        success, message = self._perform_action(actor, target, action, side)
        if not success:
            raise ValueError(message)
        self.message = message
        self._add_log(message)
        if self._check_winner():
            return self.to_dict()
        history.append(action)
        if using_bonus_action:
            self.bonus_actions[side] -= 1
        if self.bonus_actions[side] > 0:
            return self.to_dict()
        if self.pending_weapon:
            return self.to_dict()

        self._clear_bonus_state(side)
        self.active_side = "enemy" if side == "player" else "player"
        if self.active_side == "player":
            self.turn += 1
            self._regenerate()
            self._process_statuses(self.player)
            self._process_statuses(self.enemy)
            self._check_winner()
        return self.to_dict()

    #weapon choice created by scavenging
    def resolve_weapon(self, equip, defer_bot=False):
        self._require_game()
        if not self.pending_weapon:
            raise ValueError("There is no weapon waiting for a decision.")
        weapon = WEAPON_LOOKUP[self.pending_weapon]
        side = self.pending_weapon_side or "player"
        fighter = self.player if side != "enemy" else self.enemy
        if equip:
            fighter.equip_weapon(weapon)
            message = f"{self._fighter_name(fighter, self.pending_weapon_side or 'player')} equips {weapon.name}."
        else:
            message = f"{weapon.name} is left behind."
        self.pending_weapon = None
        self.pending_weapon_side = None
        self.message = message
        self._add_log(message)
        if self.bonus_actions[side] > 0:
            return self.to_dict()
        self._clear_bonus_state(side)
        if self.mode == "two_player":
            self.active_side = "enemy" if side == "player" else "player"
            if self.active_side == "player":
                self.turn += 1
                self._regenerate()
                self._process_statuses(self.player)
                self._process_statuses(self.enemy)
                self._check_winner()
            return self.to_dict()

        if defer_bot:
            self.pending_bot_turn = True
            return self.to_dict()
        self._perform_bot_turn()
        self._clear_bonus_state("enemy")
        if not self._check_winner():
            self.turn += 1
            self._regenerate()
            self._process_statuses(self.player)
            self._process_statuses(self.enemy)
        self._check_winner()
        return self.to_dict()

    def _weapon_damage(self, actor):
        """Roll the Swordsman's passive critical and return raw weapon damage."""
        critical = actor.class_name == "Swordsman" and self.rng.random() < 0.20
        multiplier = 1.5 if critical else 1
        return actor.weapon.damage * multiplier, critical

    @staticmethod
    def _format_amount(amount):
        """Keep exact half damage readable without trailing decimal zeroes."""
        return str(int(amount)) if float(amount).is_integer() else str(amount)

    @staticmethod
    def _deal_damage(target, amount, damage_kind):
        """Apply Resistance's universal reduction and subtract exact damage."""
        multiplier = 0.50 if target.statuses["resistance"] > 0 else 1
        dealt = amount * multiplier
        target.health -= dealt
        return dealt

    def _perform_action(self, actor, target, action, side):
        """Validate and execute one command, returning success and a message."""
        name = self._fighter_name(actor, side)
        if action == "approach":
            old_distance = self.distance
            self.distance = max(0, self.distance - actor.speed // 2)
            self._set_effect(
                "move", side, action="approach",
                from_distance=old_distance, to_distance=self.distance,
            )
            return True, f"{name} approaches. Distance is {self.distance}."

        if action == "step_back":
            old_distance = self.distance
            self.distance += actor.speed // 2
            self._set_effect(
                "move", side, action="step_back",
                from_distance=old_distance, to_distance=self.distance,
            )
            return True, f"{name} steps back. Distance is {self.distance}."

        if action == "escape":
            if actor.stamina < 10:
                return False, "Not enough stamina."
            actor.stamina -= 10
            old_distance = self.distance
            self.distance += actor.speed
            self._set_effect(
                "move", side, action="escape",
                from_distance=old_distance, to_distance=self.distance,
            )
            return True, f"{name} escapes. Distance is {self.distance}."

        if action == "attack":
            if actor.stamina < actor.weapon.stamina_cost:
                return False, "Not enough stamina."
            actor.stamina -= actor.weapon.stamina_cost
            if self.distance > actor.weapon.range:
                self._set_effect("strike", side, hit=False, weapon=actor.weapon.name)
                return True, f"{name}'s attack misses at distance {self.distance}."
            base_damage, critical = self._weapon_damage(actor)
            damage = self._deal_damage(target, base_damage, "weapon")
            self._set_effect(
                "strike", side, hit=True, weapon=actor.weapon.name,
                critical=critical, damage=damage,
            )
            critical_text = " critical" if critical else ""
            return True, (
                f"{name} lands a{critical_text} attack with {actor.weapon.name} "
                f"for {self._format_amount(damage)} damage."
            )

        if action == "charge":
            if actor.stamina < 10:
                return False, "Not enough stamina."
            actor.stamina -= 10
            old_distance = self.distance
            self.distance = max(0, self.distance - actor.speed)
            self._set_effect(
                "move", side, action="charge",
                from_distance=old_distance, to_distance=self.distance,
            )
            if self.distance <= actor.weapon.range and actor.stamina >= actor.weapon.stamina_cost:
                actor.stamina -= actor.weapon.stamina_cost
                base_damage, critical = self._weapon_damage(actor)
                damage = self._deal_damage(target, base_damage, "weapon")
                assassin_stun = actor.class_name == "Assassin"
                if assassin_stun:
                    target.statuses["stunned"] = max(target.statuses["stunned"], 1)
                    self.bonus_actions[side] += 1
                    if self.bonus_action_kind[side] is None:
                        self.bonus_action_kind[side] = "charge"
                self._set_effect(
                    "strike", side, hit=True, weapon=actor.weapon.name,
                    charged=True, critical=critical, damage=damage,
                    stunned=assassin_stun,
                )
                critical_text = " critical" if critical else ""
                bonus_text = (
                    ", stuns the target, and gains 1 extra action"
                    if assassin_stun else ""
                )
                return True, (
                    f"{name} lands a{critical_text} charge for "
                    f"{self._format_amount(damage)} damage{bonus_text}."
                )
            if self.distance <= actor.weapon.range:
                return True, (
                    f"{name} charges to distance {self.distance}, but does not "
                    f"have enough stamina to attack."
                )
            return True, f"{name} charges to distance {self.distance}."

        if action == "super_charge":
            if actor.class_name != "Juggernaut":
                return False, "Only Juggernauts can use Super-charge."
            if self.ability_cooldowns[side]["super_charge"] > 0:
                return False, "Super-charge is still on cooldown."
            if actor.mana < 15:
                return False, "Not enough mana."
            actor.mana -= 15
            self.ability_cooldowns[side]["super_charge"] = 2
            self.ability_cooldown_fresh[side]["super_charge"] = True
            old_distance = self.distance
            self.distance = max(0, self.distance - actor.speed * 2)
            self._set_effect(
                "move", side, action="super_charge",
                from_distance=old_distance, to_distance=self.distance,
            )
            if self.distance <= actor.weapon.range and actor.stamina >= actor.weapon.stamina_cost:
                actor.stamina -= actor.weapon.stamina_cost
                damage = self._deal_damage(target, actor.weapon.damage, "weapon")
                self._set_effect(
                    "strike", side, hit=True, weapon=actor.weapon.name,
                    charged=True, super_charge=True, damage=damage,
                )
                return True, (
                    f"{name} Super-charges for "
                    f"{self._format_amount(damage)} damage."
                )
            if self.distance <= actor.weapon.range:
                return True, (
                    f"{name} Super-charges to distance {self.distance}, but does "
                    f"not have enough stamina to attack."
                )
            return True, f"{name} Super-charges to distance {self.distance}."

        if action == "resistance":
            if actor.class_name != "Sorcerer":
                return False, "Only Sorcerers can use Resistance."
            if self.ability_cooldowns[side]["resistance"] > 0:
                return False, "Resistance is still active or on cooldown."
            if actor.mana < 10:
                return False, "Not enough mana."
            actor.mana -= 10
            actor.statuses["resistance"] = 2
            self.resistance_fresh[side] = True
            self.ability_cooldowns[side]["resistance"] = 4
            self.ability_cooldown_fresh[side]["resistance"] = True
            self._set_effect("resistance", side)
            return True, f"{name} raises Resistance for 2 turns."

        if action in ("fireball", "freeze", "poison"):
            costs = {"fireball": 25, "freeze": 40, "poison": 25}
            damage = {"fireball": 15, "freeze": 5, "poison": 5}
            if actor.mana < costs[action]:
                return False, "Not enough mana."
            actor.mana -= costs[action]
            if not self._spell_hits(action):
                self._set_effect(
                    action, side, hit=False,
                    miss_y=-1 if self.rng.random() < .5 else 1,
                )
                return True, f"{name} casts {action}, but the spell misses."
            dealt_damage = self._deal_damage(target, damage[action], "spell")
            if action == "fireball":
                target.statuses["fire"] += 2
            elif action == "freeze":
                self.bonus_actions[side] += 3
                self.bonus_action_kind[side] = "freeze"
                target.statuses["frozen"] = max(target.statuses["frozen"], 1)
            else:
                target.statuses["poison"] += 2
            self._set_effect(action, side, hit=True)
            if action == "freeze":
                return True, (
                    f"{name} casts freeze for {self._format_amount(dealt_damage)} "
                    f"damage and gains 3 different extra actions."
                )
            return True, (
                f"{name} casts {action} for "
                f"{self._format_amount(dealt_damage)} damage."
            )

        if action == "heal":
            if actor.mana < 25:
                return False, "Not enough mana."
            actor.mana -= 25
            actor.heal_stat("health", 20)
            self._set_effect("heal", side)
            return True, f"{name} heals 20 HP."

        if action in ("push", "pull"):
            if actor.mana < 10:
                return False, "Not enough mana."
            actor.mana -= 10
            if not self._spell_hits(action):
                self._set_effect(
                    action, side, hit=False,
                    miss_y=-1 if self.rng.random() < .5 else 1,
                )
                return True, f"{name} casts {action}, but the spell misses."
            old_distance = self.distance
            if action == "push":
                self.distance += 3
            else:
                self.distance = max(0, self.distance - 3)
            target_side = "enemy" if side == "player" else "player"
            self._set_effect(
                "move", target_side, from_distance=old_distance,
                to_distance=self.distance, trail=True, spell=action, caster=side,
            )
            return True, f"{name} casts {action}. Distance is {self.distance}."

        if action == "meditate":
            health_gain = self.rng.randint(0, 5)
            stamina_gain = self.rng.randint(0, 5)
            mana_gain = self.rng.randint(0, 5)
            actor.heal_stat("health", health_gain)
            actor.heal_stat("stamina", stamina_gain)
            actor.heal_stat("mana", mana_gain)
            self._set_effect("meditate", side)
            return True, (
                f"{name} meditates: +{health_gain} HP, "
                f"+{stamina_gain} stamina, +{mana_gain} mana."
            )

        if action == "scavenge":
            stamina_cost = min(5, max(0, self.rng.randint(0, 5)))
            mana_cost = min(5, max(0, self.rng.randint(0, 5)))
            if actor.stamina < stamina_cost:
                return False, f"Scavenge rolled {stamina_cost} stamina, but there is not enough."
            if actor.mana < mana_cost:
                return False, f"Scavenge rolled {mana_cost} mana, but there is not enough."
            actor.stamina -= stamina_cost
            actor.mana -= mana_cost
            self._set_effect("scavenge", side)
            cost_text = f"spending {stamina_cost} stamina and {mana_cost} mana"
            roll = self.rng.randint(1, 100)
            if roll <= SCAVENGE_NOTHING_CHANCE:
                return True, f"{name} scavenges, {cost_text}, but finds nothing."
            if roll <= SCAVENGE_NOTHING_CHANCE + SCAVENGE_ITEM_CHANCE:
                item = self.rng.choice(ITEMS)
                actor.inventory.append(item)
                return True, f"{name} scavenges, {cost_text}, and finds {item}."
            weapon = self.rng.choice(WEAPONS)
            if side == "player" or self.mode == "two_player":
                self.pending_weapon = weapon.name
                self.pending_weapon_side = side
                return True, f"{name} scavenges, {cost_text}, and finds {weapon.name}. Equip it?"
            return True, f"{name} scavenges, {cost_text}, and finds {weapon.name}, but leaves it behind."

        item_actions = {
            "apple": "Apple",
            "bandage": "Bandage",
            "holywater": "HolyWater",
            "steak": "Steak",
        }
        if action in item_actions:
            item = item_actions[action]
            if item not in actor.inventory:
                return False, f"{item} was not found."
            actor.inventory.remove(item)
            if action == "apple":
                actor.heal_stat("health", 10)
                actor.heal_stat("mana", 20)
            elif action == "bandage":
                actor.heal_stat("health", 20)
            elif action == "holywater":
                actor.heal_stat("health", 10)
                actor.statuses["holy"] += 2
            else:
                actor.heal_stat("health", 5)
                actor.heal_stat("stamina", 20)
                actor.heal_stat("mana", 5)
            return True, f"{name} uses {item}."

        return False, "Unknown action."

    def _spell_hits(self, action):
        """Guaranteed through hit range, then falls linearly to 0 at twice that range."""
        hit_range = SPELL_HIT_RANGES[action]
        if self.distance <= hit_range:
            return True
        maximum_range = hit_range * 2
        if self.distance >= maximum_range:
            return False
        hit_probability = (maximum_range - self.distance) / hit_range
        return self.rng.random() < hit_probability

    def _choose_bot_action(self):
        """Dispatch to a strategy without exposing the player's inventory."""
        if self.bot_difficulty == "easy":
            return self._choose_easy_bot_action()
        if self.bot_difficulty == "hard":
            return self._choose_hard_bot_action()
        return self._choose_normal_bot_action()

    def _perform_bot_turn(self):
        """Run a bot decision and any Freeze or charged-stun bonus actions."""
        if self.bot_difficulty == "dummy":
            self.message = "Dummy stares blankly into space."
            self._add_log(self.message)
            return
        action = self._choose_bot_action()
        success, message = self._perform_action(
            self.enemy, self.player, action, "enemy"
        )
        self.message = message
        self._add_log(message)
        self.bonus_action_history["enemy"] = [action]
        if not success or self.bonus_actions["enemy"] <= 0:
            return
        while self.bonus_actions["enemy"] > 0:
            if self._check_winner():
                break
            followup = self._choose_bot_followup_action()
            success, message = self._perform_action(
                self.enemy, self.player, followup, "enemy"
            )
            if not success:
                followup = next(
                    (candidate for candidate in ("meditate", "approach", "step_back")
                     if candidate not in self.bonus_action_history["enemy"]),
                    "approach",
                )
                _, message = self._perform_action(
                    self.enemy, self.player, followup, "enemy"
                )
            self.message = message
            self._add_log(message)
            self.bonus_action_history["enemy"].append(followup)
            self.bonus_actions["enemy"] -= 1
        self.bonus_actions["enemy"] = 0
        self.bonus_action_history["enemy"] = []
        self.bonus_action_kind["enemy"] = None

    def _choose_bot_followup_action(self):
        """Plan a Freeze bonus action from the newly updated combat state."""
        bot = self.enemy
        opponent = self.player
        used_actions = set(self.bonus_action_history["enemy"])
        legal = [action for action in self._bot_legal_actions() if action not in used_actions]
        if self.bot_difficulty == "hard" and bot.class_name == "Assassin" \
                and self.bonus_action_kind["enemy"] == "charge" \
                and bot.health <= bot.max_health * .60 \
                and opponent.stamina >= opponent.weapon.stamina_cost:
            for action in ("escape", "step_back"):
                if action in legal:
                    return action
        if "resistance" in legal and bot.statuses["resistance"] == 0 \
                and bot.health <= bot.max_health * .65:
            return "resistance"
        if bot.health <= bot.max_health * .30:
            if self.distance < BOT_RETREAT_DISTANCE and "escape" in legal:
                return "escape"
            if self.distance < BOT_RETREAT_DISTANCE and "push" in legal:
                return "push"
            for action in ("heal", "bandage", "apple", "steak", "holywater",
                           "resistance", "meditate"):
                if action in legal:
                    return action
            return "step_back"
        if self.distance <= bot.weapon.range and "attack" in legal:
            return "attack"
        if opponent.health <= 15 and "fireball" in legal \
                and self.distance <= SPELL_HIT_RANGES["fireball"]:
            return "fireball"
        if "poison" in legal and opponent.statuses["poison"] == 0 \
                and self.distance <= SPELL_HIT_RANGES["poison"]:
            return "poison"
        if "fireball" in legal and self.distance <= SPELL_HIT_RANGES["fireball"]:
            return "fireball"
        if "charge" in legal:
            return "charge"
        if "pull" in legal and self.distance <= SPELL_HIT_RANGES["pull"]:
            return "pull"
        return "approach"

    # Normal preserves the original direct, fight-aware strategy.
    def _choose_normal_bot_action(self):
        bot = self.enemy
        weapon = bot.weapon
        if bot.class_name == "Sorcerer" and bot.mana >= 10 \
                and self.ability_cooldowns["enemy"]["resistance"] == 0 \
                and bot.statuses["resistance"] == 0 \
                and self.distance <= self.player.weapon.range + self.player.speed:
            return "resistance"
        if bot.health <= bot.max_health / 4:
            for action, item in (("bandage", "Bandage"), ("apple", "Apple"), ("steak", "Steak"), ("holywater", "HolyWater")):
                if item in bot.inventory:
                    return action
            if bot.mana >= 25:
                return "heal"
            if bot.stamina >= 10 and self.distance < BOT_RETREAT_DISTANCE:
                return "escape"
            return "meditate"
        if self.distance <= weapon.range and bot.stamina >= weapon.stamina_cost:
            return "attack"
        if self.distance <= 5:
            if self.player.health <= 15 and bot.mana >= 25:
                return "fireball"
            if bot.mana >= 25:
                return self.rng.choice(("fireball", "poison"))
        if bot.health <= bot.max_health / 2 and bot.mana >= 25:
            return "heal"
        if self.distance > weapon.range:
            if bot.class_name == "Juggernaut" and bot.mana >= 15 \
                    and self.ability_cooldowns["enemy"]["super_charge"] == 0:
                return "super_charge"
            if bot.stamina >= 10:
                return "charge"
            return "approach"
        if bot.mana >= 10:
            return "push"
        if bot.stamina >= 10 and self.distance < BOT_RETREAT_DISTANCE:
            return "escape"
        return "meditate"

    def _bot_legal_actions(self):
        """Return actions the bot can pay for using only its own inventory."""
        bot = self.enemy
        legal = ["approach", "step_back", "meditate"]
        if bot.stamina >= 5 and bot.mana >= 5:
            legal.append("scavenge")
        if bot.stamina >= bot.weapon.stamina_cost:
            legal.append("attack")
        if bot.stamina >= 10:
            legal.extend(("charge", "escape"))
        if bot.class_name == "Juggernaut" and bot.mana >= 15 \
                and self.ability_cooldowns["enemy"]["super_charge"] == 0:
            legal.append("super_charge")
        if bot.mana >= 25:
            legal.extend(("fireball", "heal", "poison"))
        if bot.mana >= 40:
            legal.append("freeze")
        if bot.mana >= 10:
            legal.extend(("push", "pull"))
            if bot.class_name == "Sorcerer" \
                    and self.ability_cooldowns["enemy"]["resistance"] == 0:
                legal.append("resistance")
        item_actions = {
            "Apple": "apple", "Bandage": "bandage",
            "HolyWater": "holywater", "Steak": "steak",
        }
        legal.extend(item_actions[item] for item in bot.inventory if item in item_actions)
        return list(dict.fromkeys(legal))

    def _choose_easy_bot_action(self):
        """Use sensible weighted randomness with deliberately frequent mistakes."""
        bot = self.enemy
        legal = self._bot_legal_actions()
        weights = {action: 2.0 for action in legal}
        if self.distance <= bot.weapon.range:
            weights["attack"] = 7.0 if "attack" in weights else 0
            weights["step_back"] = 3.0
        else:
            weights["approach"] = 6.0
            if "super_charge" in weights:
                weights["super_charge"] = 5.0
            if "charge" in weights:
                weights["charge"] = 4.0
        if "resistance" in weights:
            weights["resistance"] = (
                5.0 if bot.statuses["resistance"] == 0 else .5
            )
        if bot.health < bot.max_health / 2:
            for action in ("heal", "apple", "bandage", "steak", "holywater", "escape"):
                if action in weights:
                    weights[action] += 5.0
            if self.distance >= BOT_RETREAT_DISTANCE:
                for action in ("escape", "push", "step_back"):
                    if action in weights:
                        weights[action] = 0
                weights["meditate"] = weights.get("meditate", 0) + 7
        if self.distance <= 8:
            for action in ("fireball", "poison", "push", "pull"):
                if action in weights:
                    weights[action] += 2.5
        population = [action for action in legal if weights.get(action, 0) > 0]
        return self.rng.choices(population, weights=[weights[action] for action in population], k=1)[0]

    def _choose_hard_bot_action(self):
        """Score all legal options from visible stats, classes, weapons, and range."""
        bot = self.enemy
        opponent = self.player
        legal = self._bot_legal_actions()
        scores = {action: 0.0 for action in legal}
        bot_health_ratio = bot.health / bot.max_health
        opponent_health_ratio = opponent.health / opponent.max_health
        opponent_in_range = self.distance <= opponent.weapon.range
        bot_in_range = self.distance <= bot.weapon.range
        opponent_can_attack = opponent.stamina >= opponent.weapon.stamina_cost
        opponent_can_charge = opponent.stamina >= opponent.weapon.stamina_cost + 10
        opponent_can_super_charge = (
            opponent.class_name == "Juggernaut"
            and opponent.mana >= 15
            and opponent.stamina >= opponent.weapon.stamina_cost
            and self.ability_cooldowns["player"]["super_charge"] == 0
        )
        opponent_threat_reach = opponent.weapon.range + (
            opponent.speed * 2 if opponent_can_super_charge
            else opponent.speed if opponent_can_charge else 0
        )
        under_immediate_threat = opponent_in_range and opponent_can_attack
        under_charge_threat = self.distance <= opponent_threat_reach

        # Finish a guaranteed win before considering defensive play.
        if bot_in_range and "attack" in legal and opponent.health <= bot.weapon.damage:
            return "attack"
        if "fireball" in legal and self.distance <= SPELL_HIT_RANGES["fireball"] \
                and opponent.health <= 15:
            return "fireball"

        # Critical bots prioritize creating safety instead of trading damage.
        if bot_health_ratio <= .30:
            if self.distance < BOT_RETREAT_DISTANCE \
                    and under_charge_threat and "escape" in legal:
                return "escape"
            if self.distance < BOT_RETREAT_DISTANCE \
                    and under_charge_threat and "push" in legal:
                return "push"
            for action in ("bandage", "apple", "steak", "holywater", "heal"):
                if action in legal:
                    return action
            return "meditate" if self.distance >= BOT_RETREAT_DISTANCE else "step_back"

        # At a safe distance, weigh gathering supplies against making progress.
        # Greater distance increasingly favors closing in, preventing endless
        # scavenging while still using safe opportunities.
        safe_to_scavenge = (
            "scavenge" in legal
            and self.distance > opponent_threat_reach + 2
            and bot_health_ratio >= .70
            and bot.stamina >= bot.max_stamina * .65
            and bot.mana >= bot.max_mana * .50
        )
        if safe_to_scavenge:
            if bot.class_name == "Sorcerer":
                # Close carefully toward spell range without rushing directly
                # into the opponent's next weapon/charge threat.
                closing_action = "approach"
            else:
                closing_action = "super_charge" if "super_charge" in legal \
                    and bot.stamina >= bot.weapon.stamina_cost \
                    else "charge" if "charge" in legal \
                    and bot.stamina >= bot.weapon.stamina_cost + 25 else "approach"
            distance_excess = self.distance - opponent_threat_reach
            closing_weight = 4 + min(5, distance_excess / 3)
            scavenge_weight = 4 if not bot.inventory else 2.5
            return self.rng.choices(
                (closing_action, "scavenge"),
                weights=(closing_weight, scavenge_weight),
                k=1,
            )[0]

        scores["meditate"] = (
            (bot.max_health - bot.health) / 8
            + (bot.max_stamina - bot.stamina) / 10
            + (bot.max_mana - bot.mana) / 10
        )
        scores["scavenge"] = 12 if not under_charge_threat else -8
        scores["approach"] = 14 if not bot_in_range else -6
        scores["step_back"] = 18 if under_immediate_threat and not bot_in_range else 3
        if "attack" in scores:
            scores["attack"] = 30 + bot.weapon.damage
            if opponent.health <= bot.weapon.damage:
                scores["attack"] += 80
            if not bot_in_range:
                scores["attack"] = -30
        if "charge" in scores:
            landing_distance = max(0, self.distance - bot.speed)
            scores["charge"] = 20 if landing_distance <= bot.weapon.range else 10
            if bot.stamina < bot.weapon.stamina_cost + 20:
                scores["charge"] -= 8
        if "super_charge" in scores:
            landing_distance = max(0, self.distance - bot.speed * 2)
            scores["super_charge"] = (
                29 if landing_distance <= bot.weapon.range else 17
            )
            if bot.stamina < bot.weapon.stamina_cost:
                scores["super_charge"] -= 12
        if "escape" in scores:
            scores["escape"] = -25 if self.distance >= BOT_RETREAT_DISTANCE else (
                6 + (1 - bot_health_ratio) * 45
                + (18 if under_immediate_threat else 8 if under_charge_threat else 0)
            )

        spell_accuracy = {
            spell: 1.0 if self.distance <= SPELL_HIT_RANGES[spell]
            else max(0.0, (SPELL_HIT_RANGES[spell] * 2 - self.distance) / SPELL_HIT_RANGES[spell])
            for spell in SPELL_HIT_RANGES
        }
        for spell, base in (("fireball", 22), ("poison", 18), ("freeze", 38)):
            if spell in scores:
                scores[spell] = base * spell_accuracy[spell]
        if "fireball" in scores and opponent.health <= 15:
            scores["fireball"] += 65
        if "poison" in scores and opponent.statuses["poison"] > 0:
            scores["poison"] -= 12
        if "freeze" in scores and opponent.statuses["frozen"] > 0:
            scores["freeze"] -= 15
        if "heal" in scores:
            scores["heal"] = (1 - bot_health_ratio) * 42 - (8 if bot.health == bot.max_health else 0)
        if "push" in scores:
            scores["push"] = (
                24 if under_immediate_threat else 13 if under_charge_threat else 5
            ) * spell_accuracy["push"]
        if "pull" in scores:
            scores["pull"] = (17 if self.distance > bot.weapon.range else 2) * spell_accuracy["pull"]
        if "resistance" in scores:
            scores["resistance"] = (
                28 if bot.statuses["resistance"] == 0 and under_charge_threat
                else 16 if bot.statuses["resistance"] == 0 else -15
            )

        item_scores = {
            "bandage": (1 - bot_health_ratio) * 48,
            "apple": (1 - bot_health_ratio) * 25 + (bot.max_mana - bot.mana) / 6,
            "steak": (1 - bot_health_ratio) * 14 + (bot.max_stamina - bot.stamina) / 5,
            "holywater": (1 - bot_health_ratio) * 18 + (8 if bot.statuses["holy"] == 0 else 0),
        }
        for action, score in item_scores.items():
            if action in scores:
                scores[action] = score

        # Conservative hard play values resource reserves and avoids low-odds spells.
        if bot.stamina < bot.weapon.stamina_cost + 10:
            for action in ("attack", "charge", "super_charge", "escape"):
                if action in scores:
                    scores[action] -= 8
        if bot.mana < 35:
            for action in ("fireball", "poison", "push", "pull"):
                if action in scores:
                    scores[action] -= 5
        if opponent_health_ratio < .25:
            for action in ("attack", "charge", "super_charge", "fireball"):
                if action in scores:
                    scores[action] += 12
        if bot_health_ratio < .50 and under_charge_threat:
            for action in ("escape", "push", "step_back", "heal"):
                if action in scores:
                    scores[action] += 16
            for action in ("attack", "charge", "super_charge", "pull", "scavenge"):
                if action in scores:
                    scores[action] -= 14
        if opponent.stamina < opponent.weapon.stamina_cost:
            # Notice when the opponent cannot currently use its weapon.
            for action in ("meditate", "scavenge", "poison"):
                if action in scores:
                    scores[action] += 8

        self._apply_hard_class_strategy(
            scores=scores,
            bot=bot,
            opponent=opponent,
            bot_health_ratio=bot_health_ratio,
            bot_in_range=bot_in_range,
            opponent_can_attack=opponent_can_attack,
            opponent_threat_reach=opponent_threat_reach,
            under_immediate_threat=under_immediate_threat,
            under_charge_threat=under_charge_threat,
            spell_accuracy=spell_accuracy,
        )

        best_score = max(scores.values())
        varied_best = [action for action, score in scores.items() if score >= best_score - 3]
        return self.rng.choice(varied_best)

    def _apply_hard_class_strategy(self, scores, bot, opponent,
                                   bot_health_ratio, bot_in_range,
                                   opponent_can_attack, opponent_threat_reach,
                                   under_immediate_threat,
                                   under_charge_threat, spell_accuracy):
        """Teach Hard mode the preferred range and resources of each class."""
        def add(action, amount):
            if action in scores:
                scores[action] += amount

        if bot.class_name == "Sorcerer":
            # Sorcerers are fast but fragile. Stay outside the opponent's
            # weapon/charge reach while remaining within the 6–8 range where
            # Poison, Push, Pull, and long-range spell chances remain useful.
            if under_charge_threat:
                add("push", 52 * spell_accuracy["push"])
                add("escape", 34)
                add("step_back", 26)
                add("resistance", 34)
                add("pull", -35)
                add("attack", -28)
                add("charge", -25)
            elif self.distance > 8:
                add("approach", 32)
                add("pull", 18 * spell_accuracy["pull"])
            else:
                add("fireball", 18 * spell_accuracy["fireball"])
                add("poison", 22 * spell_accuracy["poison"])
                add("freeze", 18 * spell_accuracy["freeze"])
                add("push", 8 * spell_accuracy["push"])
            if bot.mana < 25:
                add("meditate", 30)
                add("scavenge", 10 if self.distance > opponent_threat_reach else -12)
            if under_immediate_threat and opponent_can_attack:
                add("heal", 18)
            return

        if bot.class_name == "Assassin":
            # Assassins use their speed to land a dagger Charge, trigger the
            # stun/bonus action, then disengage when too fragile to trade.
            charge_lands = self.distance - bot.speed <= bot.weapon.range
            if charge_lands:
                add("charge", 55)
            elif not bot_in_range:
                add("charge", 22)
                add("approach", 8)
            if bot_in_range:
                add("attack", 24)
                if bot_health_ratio <= .60 and opponent_can_attack:
                    add("escape", 34)
                    add("step_back", 18)
            add("super_charge", -20)
            add("fireball", -8)
            add("freeze", -8)
            return

        if bot.class_name == "Juggernaut":
            # Juggernauts can afford trades. Use the Claymore's heavy damage
            # and reserve mana for Super-charge instead of kiting or spell spam.
            super_lands = self.distance - bot.speed * 2 <= bot.weapon.range
            if super_lands:
                add("super_charge", 52)
            else:
                add("super_charge", 22)
            add("attack", 30 if bot_in_range else 0)
            add("charge", 24)
            add("approach", 16)
            add("escape", -24)
            add("step_back", -12)
            for spell in ("fireball", "freeze", "poison", "push", "pull"):
                add(spell, -12)
            return

        if bot.class_name == "Swordsman":
            # Swordsmen have high stamina and a crit passive on weapon attacks,
            # so reliable Attack/Charge pressure is better than spell trading.
            add("attack", 32 if bot_in_range else 0)
            if self.distance - bot.speed <= bot.weapon.range:
                add("charge", 34)
            else:
                add("approach", 14)
                add("charge", 12)
            for spell in ("fireball", "freeze", "poison", "push", "pull"):
                add(spell, -8)

    def _regenerate(self):
        """Round transitions intentionally provide no automatic stat benefits."""
        return None

    def _clear_bonus_state(self, side):
        """End a side's turn, clearing bonus locks and aging timed abilities."""
        self.bonus_actions[side] = 0
        self.bonus_action_history[side] = []
        self.bonus_action_kind[side] = None
        fighter = self.player if side == "player" else self.enemy
        if self.resistance_fresh[side]:
            self.resistance_fresh[side] = False
        elif fighter and fighter.statuses["resistance"] > 0:
            fighter.statuses["resistance"] -= 1
        for ability, turns in self.ability_cooldowns[side].items():
            if self.ability_cooldown_fresh[side][ability]:
                self.ability_cooldown_fresh[side][ability] = False
            elif turns > 0:
                self.ability_cooldowns[side][ability] -= 1

    def _process_statuses(self, fighter):
        """Tick timed damage/healing statuses and record visible results."""
        effects = {"fire": -10, "holy": 5, "poison": -5}
        for status, amount in effects.items():
            if fighter.statuses[status] > 0:
                if status == "holy":
                    fighter.heal_stat("health", amount)
                    fighter.heal_stat("mana", amount)
                    health_change = amount
                else:
                    health_change = -self._deal_damage(fighter, -amount, "effect")
                fighter.statuses[status] -= 1
                side = "player" if fighter is self.player else "enemy"
                suffix = f" and mana by {amount}" if status == "holy" else ""
                self._add_log(
                    f"{self._fighter_name(fighter, side)}: "
                    f"{status} changes HP by "
                    f"{self._format_amount(health_change)}{suffix}."
                )
        if fighter.statuses["frozen"] > 0:
            fighter.statuses["frozen"] -= 1
        if fighter.statuses["stunned"] > 0:
            fighter.statuses["stunned"] -= 1

    def _check_winner(self):
        """Set terminal state when either fighter reaches zero health."""
        if self.game_over:
            return True
        if self.enemy.health <= 0:
            self.game_over = True
            self.winner = "player"
        elif self.player.health <= 0:
            self.game_over = True
            self.winner = "enemy"
        if self.game_over:
            loser = "enemy" if self.winner == "player" else "player"
            self._set_effect(
                "defeat",
                loser,
                winner=self.winner,
                throw_direction=self.rng.choice((-1, 1)),
            )
            winner_fighter = self.player if self.winner == "player" else self.enemy
            winner = self._fighter_name(winner_fighter, self.winner)
            self.message = f"{winner} wins the duel."
            self._add_log(self.message)
        return self.game_over

    def _set_effect(self, effect, side, **details):
        """Queue browser animation metadata without implementing visuals."""
        self.last_effect = {"type": effect, "from": side, **details}
        self.effects.append(self.last_effect.copy())

    def _fighter_name(self, fighter, side):
        if self.mode == "two_player":
            return "Player 1" if side == "player" else "Player 2"
        if side == "enemy":
            return "Dummy" if self.bot_difficulty == "dummy" else "Bot"
        return "Player 1"

    def _add_log(self, message):
        """Store newest-first structured entries with a payload cap."""
        self.log.insert(0, {"turn": self.turn, "message": message})
        del self.log[30:]

    def _require_game(self):
        if not self.player or not self.enemy:
            raise ValueError("Start a game first.")

    def _action_available(self, action):
        """Return whether the active fighter can currently use a command."""
        if not self.player or self.game_over or self.pending_weapon:
            return False
        side = "enemy" if self.mode == "two_player" and self.active_side == "enemy" else "player"
        p = self.enemy if side == "enemy" else self.player
        if self.bonus_actions[side] > 0 and action in self.bonus_action_history[side]:
            return False
        items = {"apple": "Apple", "bandage": "Bandage", "holywater": "HolyWater", "steak": "Steak"}
        if action in items:
            return items[action] in p.inventory
        if action == "attack":
            return p.stamina >= p.weapon.stamina_cost
        if action in ("charge", "escape"):
            return p.stamina >= 10
        if action == "super_charge":
            return (
                p.class_name == "Juggernaut"
                and p.mana >= 15
                and self.ability_cooldowns[side]["super_charge"] == 0
            )
        if action == "resistance":
            return (
                p.class_name == "Sorcerer"
                and p.mana >= 10
                and self.ability_cooldowns[side]["resistance"] == 0
            )
        if action in ("fireball", "heal", "poison"):
            return p.mana >= 25
        if action == "freeze":
            return p.mana >= 40
        if action in ("push", "pull"):
            return p.mana >= 10
        return True

    def to_dict(self):
        """Build the complete JSON-safe snapshot consumed by JavaScript."""
        actions = {
            category: [
                {"id": action, "name": name, "icon": icon, "cost": cost, "available": self._action_available(action)}
                for action, name, icon, cost in details
            ]
            for category, details in ACTION_DETAILS.items()
        }
        active_fighter = self.enemy if self.mode == "two_player" and self.active_side == "enemy" else self.player
        if active_fighter:
            attack_command = next(command for command in actions["actions"] if command["id"] == "attack")
            attack_command["cost"] = f"{active_fighter.weapon.stamina_cost} stamina"
            if active_fighter.class_name == "Juggernaut":
                cooldown = self.ability_cooldowns[
                    "enemy" if active_fighter is self.enemy else "player"
                ]["super_charge"]
                actions["actions"].append({
                    "id": "super_charge",
                    "name": "Super-charge (ability)",
                    "icon": "💥",
                    "cost": (
                        f"Cooldown: {cooldown} turn{'s' if cooldown != 1 else ''}"
                        if cooldown else
                        "15 mana + attack stamina / 2-turn cooldown"
                    ),
                    "available": self._action_available("super_charge"),
                })
            elif active_fighter.class_name == "Sorcerer":
                side = "enemy" if active_fighter is self.enemy else "player"
                cooldown = self.ability_cooldowns[side]["resistance"]
                active_turns = active_fighter.statuses["resistance"]
                actions["actions"].append({
                    "id": "resistance",
                    "name": "Resistance (ability)",
                    "icon": "🛡️",
                    "cost": (
                        f"Active: {active_turns} / reuse in {cooldown} turns"
                        if active_turns else
                        f"Cooldown: {cooldown} turn{'s' if cooldown != 1 else ''}"
                        if cooldown else
                        "10 mana / active 2 turns / reuse after 4"
                    ),
                    "available": self._action_available("resistance"),
                })
        return {
            "turn": self.turn,
            "distance": self.distance,
            "game_over": self.game_over,
            "winner": self.winner,
            "message": self.message,
            "log": self.log.copy(),
            "effect": self.last_effect,
            "effects": [effect.copy() for effect in self.effects],
            "pending_weapon": self.pending_weapon,
            "pending_bot_turn": self.pending_bot_turn,
            "mode": self.mode,
            "bot_difficulty": self.bot_difficulty,
            "bonus_actions": self.bonus_actions.copy(),
            "bonus_action_history": {
                side: actions.copy() for side, actions in self.bonus_action_history.items()
            },
            "bonus_action_kind": self.bonus_action_kind.copy(),
            "ability_cooldowns": {
                side: cooldowns.copy()
                for side, cooldowns in self.ability_cooldowns.items()
            },
            "active_side": self.active_side,
            "active_label": "Player 2" if self.mode == "two_player" and self.active_side == "enemy" else "Player 1",
            "player": self.player.to_dict() if self.player else None,
            "enemy": self.enemy.to_dict() if self.enemy else None,
            "actions": actions,
        }


def class_cards():
    """Return class-selection data without exposing mutable objects."""
    return [character.to_dict() for character in CLASSES]


def scavenge_loot_table():
    """Return exact per-result probabilities derived from scavenge constants."""
    rows = [{"result": "Nothing", "chance": SCAVENGE_NOTHING_CHANCE}]
    rows.extend({
        "result": item.replace("HolyWater", "Holy Water"),
        "chance": SCAVENGE_ITEM_CHANCE / len(ITEMS),
    } for item in ITEMS)
    rows.extend({
        "result": weapon.name,
        "chance": SCAVENGE_WEAPON_CHANCE / len(WEAPONS),
    } for weapon in WEAPONS)
    return rows
