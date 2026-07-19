/*
 Browser controller and pixel-art renderer.
 Python owns combat state; this file builds UI, requests JSON, renders HUD/logs,
 queues animations, and draws shared title/tutorial/arena canvas artwork.
*/

// Mutable values below describe UI and animation state, not combat rules.
let gameState = null;
let classCards = [];
let scavengeLoot = [];
let selectedMode = "singleplayer";
let selectedSetupSide = "player";
let selectedClasses = { player: "Swordsman", enemy: "Assassin" };
let activeTab = "actions";
let busy = false;
let animation = null;
let animationQueue = [];
let animationGapUntil = 0;
let animationLock = false;
let statAnimation = null;
let heldTurnOwner = "";
let heldArenaMessage = "";
let defeatSettled = false;
let heldActiveSide = "";
let lastMatchConfig = null;
let transientControlStatuses = {
  player: { frozen: false, stunned: false },
  enemy: { frozen: false, stunned: false },
};

const PLAYER_EFFECT_MS = 520;
const BOT_EFFECT_MS = 650;
const EFFECT_GAP_MS = 150;

const CLASS_ART = {
  Assassin: { color: "#a43d4f", mark: "🔪" },
  Juggernaut: { color: "#e88732", mark: "🪖" },
  Sorcerer: { color: "#a970ff", mark: "🪄" },
  Swordsman: { color: "#4f8fd8", mark: "🗡️" },
};

const canvas = document.querySelector("#arenaCanvas");
const context = canvas.getContext("2d");
const titleDecorCanvas = document.querySelector("#titleDecorCanvas");
const titleDecorContext = titleDecorCanvas.getContext("2d");
const titleScreen = document.querySelector("#titleScreen");
const gameShell = document.querySelector("#gameShell");
const setupDialog = document.querySelector("#setupDialog");
const tutorialDialog = document.querySelector("#tutorialDialog");
const weaponDialog = document.querySelector("#weaponDialog");
const leaveDialog = document.querySelector("#leaveDialog");
const commandGrid = document.querySelector("#commandGrid");


//all game information comes back from Flask as JSON
async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    if (data.state) {
      gameState = data.state;
      render();
    }
    throw new Error(data.error || "The Python server rejected the request.");
  }
  return data;
}


async function loadGame() {
  drawTitleDecorations();
  try {
    const classResponse = await apiRequest("/api/classes");
    classCards = classResponse.classes;
    scavengeLoot = classResponse.scavenge_loot || [];
    buildClassChoices();
    buildOpponentChoices();
    buildTutorialClasses();
    buildTutorialWeapons();
    buildTutorialLoot();
  } catch (error) {
    showError(error.message);
  }
}


function openSetup(mode) {
  selectedMode = mode;
  selectedSetupSide = "player";
  const twoPlayer = mode === "two_player";
  document.querySelector("#setupMode").textContent = twoPlayer ? "2-Player" : "Singleplayer";
  document.querySelector("#setupTitle").textContent = twoPlayer ? "Choose your fighters" : "Choose your fighter";
  document.querySelector("#playerPicker").hidden = !twoPlayer;
  document.querySelector("#opponentField").hidden = twoPlayer;
  updatePlayerPicker();
  buildClassChoices();
  setupDialog.showModal();
}


function buildClassChoices() {
  const selectedClass = selectedClasses[selectedSetupSide];
  const grid = document.querySelector("#classGrid");
  grid.innerHTML = classCards.map((character) => {
    const art = CLASS_ART[character.name];
    return `
      <button class="class-option ${character.name === selectedClass ? "selected" : ""}" type="button" data-class="${character.name}">
        <span class="class-portrait" style="background:${art.color}">${art.mark}</span>
        <h3>${character.name}</h3>
        <span class="class-stats">
          <span>HP ${character.health} / STA ${character.stamina}</span>
          <span>MANA ${character.mana} / SPD ${character.speed}</span>
          <span>${character.weapon.name}</span>
        </span>
      </button>`;
  }).join("");

  grid.querySelectorAll(".class-option").forEach((button) => {
    button.addEventListener("click", () => {
      selectedClasses[selectedSetupSide] = button.dataset.class;
      updatePlayerPicker();
      buildClassChoices();
    });
  });
}


function updatePlayerPicker() {
  document.querySelector("#playerOneChoice").textContent = selectedClasses.player;
  document.querySelector("#playerTwoChoice").textContent = selectedClasses.enemy;
  document.querySelectorAll(".picker-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.side === selectedSetupSide);
  });
}


function buildOpponentChoices() {
  const select = document.querySelector("#opponentSelect");
  select.innerHTML = `<option value="random">Random class</option>` + classCards
    .map((character) => `<option value="${character.name}">${character.name}</option>`)
    .join("");
}


function buildTutorialClasses() {
  document.querySelector("#tutorialClassGrid").innerHTML = classCards.map((character) => {
    const art = CLASS_ART[character.name];
    return `<article class="tutorial-class">
      <span class="tutorial-class-mark" style="background:${art.color}">${art.mark}</span>
      <div><h3>${character.name}</h3><p>${character.weapon.name}</p>
      <small class="tutorial-ability"><strong>${character.ability.active ? `${character.ability.name} (active)` : "Passive ability"}</strong>${character.ability.description}</small></div>
      <dl><div><dt>HP</dt><dd>${character.health}</dd></div><div><dt>STA</dt><dd>${character.stamina}</dd></div>
      <div><dt>MANA</dt><dd>${character.mana}</dd></div><div><dt>SPD</dt><dd>${character.speed}</dd></div></dl>
    </article>`;
  }).join("");
}


function buildTutorialWeapons() {
  document.querySelector("#tutorialWeaponList").innerHTML = classCards.map((character) => {
    const weapon = character.weapon;
    return `<div class="tutorial-weapon-row"><canvas class="tutorial-weapon-art" data-weapon="${weapon.name}" width="145" height="58"></canvas>
      <span class="tutorial-entry-copy"><strong>${weapon.name}</strong><small>Range ${weapon.range} · Damage ${weapon.damage} · Stamina cost ${weapon.stamina_cost} · Bonus ${weapon.bonus}</small></span></div>`;
  }).join("");
  document.querySelectorAll(".tutorial-weapon-art").forEach((weaponCanvas) => {
    const weaponContext = weaponCanvas.getContext("2d");
    weaponContext.imageSmoothingEnabled = false;
    weaponContext.save();
    weaponContext.translate(2, 88);
    drawWeapon(weaponCanvas.dataset.weapon, weaponContext);
    weaponContext.restore();
  });
}


function buildTutorialLoot() {
  document.querySelector("#tutorialLootBody").innerHTML = scavengeLoot.map((entry) =>
    `<tr><td>${entry.result}</td><td>${entry.chance}%</td></tr>`
  ).join("");
}


async function startGame(rematchConfig = null) {
  const enemyClass = rematchConfig?.enemy_class || (selectedMode === "two_player"
    ? selectedClasses.enemy
    : document.querySelector("#opponentSelect").value);
  const config = rematchConfig || {
    mode: selectedMode,
    bot_difficulty: document.querySelector("#botDifficulty").value,
    player_class: selectedClasses.player,
    enemy_class: enemyClass,
  };
  gameState = await apiRequest("/api/new", {
    method: "POST",
    body: JSON.stringify({
      ...config,
      enemy_class: enemyClass,
    }),
  });
  lastMatchConfig = {
    mode: gameState.mode,
    bot_difficulty: gameState.bot_difficulty,
    player_class: gameState.player.class_name,
    enemy_class: gameState.enemy.class_name,
    player_hair: gameState.player.hair_color,
    enemy_hair: gameState.enemy.hair_color,
  };
  defeatSettled = false;
  titleScreen.hidden = true;
  gameShell.hidden = false;
  render();
}


function returnToTitle() {
  if (weaponDialog.open) weaponDialog.close();
  gameShell.hidden = true;
  titleScreen.hidden = false;
  gameState = null;
  document.querySelector("#gameOverPanel").hidden = true;
}


async function takeAction(action) {
  if (busy || animationLock || gameState.game_over) return;
  busy = true;
  const previousStats = captureFighterStats(gameState);
  heldActiveSide = gameState.mode === "two_player" ? gameState.active_side : "player";
  heldTurnOwner = document.querySelector("#turnOwner").textContent;
  if (gameState.mode !== "two_player") {
    heldArenaMessage = playerActionMessage(action);
    document.querySelector("#arenaMessage").textContent = heldArenaMessage;
  }
  renderCommands();
  try {
    gameState = await apiRequest("/api/action", {
      method: "POST",
      body: JSON.stringify({
        action,
        defer_bot: gameState.mode !== "two_player",
      }),
    });
    if (gameState.mode !== "two_player"
        && ["charge", "super_charge"].includes(action)
        && gameState.message.includes("does not have enough stamina to attack")) {
      heldArenaMessage = gameState.message
        .replace(/^Player 1 charges/, "You charge")
        .replace(/^Player 1 Super-charges/, "You Super-charge");
    }
    startEffects(gameState.effects || (gameState.effect ? [gameState.effect] : []), previousStats);
    busy = false;
    render();
    if (gameState.pending_weapon) {
      document.querySelector("#foundWeaponName").textContent = gameState.pending_weapon;
      weaponDialog.showModal();
    } else if (gameState.pending_bot_turn && !animationLock) {
      // Actions with no visible/stat change still hand off asynchronously;
      // animated actions hand off from drawArena only after the lock clears.
      setTimeout(runPendingBotTurn, 0);
    }
  } catch (error) {
    showError(error.message);
  } finally {
    busy = false;
    renderCommands();
  }
}


async function runPendingBotTurn() {
  if (busy || animationLock || !gameState?.pending_bot_turn) return;
  busy = true;
  const previousStats = captureFighterStats(gameState);
  heldActiveSide = "enemy";
  heldTurnOwner = "Opponent's turn";
  document.querySelector("#turnOwner").textContent = heldTurnOwner;
  document.querySelector("#arenaMessage").textContent = "Bot is thinking…";
  renderCommands();
  try {
    gameState = await apiRequest("/api/bot", { method: "POST" });
    startEffects(
      gameState.effects || (gameState.effect ? [gameState.effect] : []),
      previousStats,
    );
    busy = false;
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    busy = false;
    renderCommands();
  }
}


function playerActionMessage(action) {
  const labels = {
    approach: "You approach.", step_back: "You step back.",
    attack: "You attack.", charge: "You charge.",
    super_charge: "You Super-charge.", resistance: "You raise Resistance.",
    escape: "You escape.", meditate: "You meditate.", scavenge: "You scavenge.",
    fireball: "You cast Fireball.", freeze: "You cast Freeze.", heal: "You cast Heal.",
    poison: "You cast Poison.", push: "You cast Push.", pull: "You cast Pull.",
    apple: "You use Apple.", bandage: "You use Bandage.",
    holywater: "You use Holy Water.", steak: "You use Steak.",
  };
  return labels[action] || "You act.";
}


async function resolveWeaponChoice(equip) {
  if (busy || !gameState?.pending_weapon) return;
  busy = true;
  const previousStats = captureFighterStats(gameState);
  heldTurnOwner = document.querySelector("#turnOwner").textContent;
  document.querySelector("#acceptWeaponButton").disabled = true;
  document.querySelector("#rejectWeaponButton").disabled = true;
  try {
    gameState = await apiRequest("/api/weapon", {
      method: "POST",
      body: JSON.stringify({
        equip,
        defer_bot: gameState.mode !== "two_player",
      }),
    });
    startEffects(gameState.effects || (gameState.effect ? [gameState.effect] : []), previousStats);
    weaponDialog.close();
    busy = false;
    render();
    if (gameState.pending_bot_turn && !animationLock) {
      setTimeout(runPendingBotTurn, 0);
    }
  } catch (error) {
    showError(error.message);
  } finally {
    busy = false;
    document.querySelector("#acceptWeaponButton").disabled = false;
    document.querySelector("#rejectWeaponButton").disabled = false;
    renderCommands();
  }
}


function meterMarkup(name, current, maximum) {
  const percent = Math.max(0, Math.min(100, current / maximum * 100));
  return `<div class="meter-row"><span>${name}</span><span class="meter-track">
    <span class="meter-fill meter-${name.toLowerCase()}" style="width:${percent}%"></span></span>
    <span class="meter-value">${Math.max(0, current)} / ${maximum}</span></div>`;
}


function renderFighter(prefix, fighter) {
  document.querySelector(`#${prefix}Class`).textContent = fighter.class_name;
  document.querySelector(`#${prefix}Weapon`).textContent = fighter.weapon.name;
  document.querySelector(`#${prefix}WeaponStats`).textContent = `Range ${fighter.weapon.range} · Damage ${fighter.weapon.damage} · Stamina cost ${fighter.weapon.stamina_cost} · Bonus ${fighter.weapon.bonus}`;
  document.querySelector(`#${prefix}Meta`).textContent = `Speed ${fighter.speed} · Items ${fighter.inventory.length}`;
  document.querySelector(`#${prefix}Meters`).innerHTML = [
    meterMarkup("Health", fighter.health, fighter.max_health),
    meterMarkup("Stamina", fighter.stamina, fighter.max_stamina),
    meterMarkup("Mana", fighter.mana, fighter.max_mana),
  ].join("");
  const statuses = Object.entries(fighter.statuses).filter(([, turns]) => turns > 0);
  document.querySelector(`#${prefix}Statuses`).innerHTML = statuses.length
    ? statuses.map(([name, turns]) => `<span class="status-chip">${name} ${turns}</span>`).join("")
    : `<span class="status-chip">No effects</span>`;
}


function captureFighterStats(state) {
  if (!state?.player || !state?.enemy) return null;
  return {
    player: { health: state.player.health, stamina: state.player.stamina, mana: state.player.mana },
    enemy: { health: state.enemy.health, stamina: state.enemy.stamina, mana: state.enemy.mana },
  };
}


function animatedFighter(side, fighter, timestamp = performance.now()) {
  if (!statAnimation) return fighter;
  const start = statAnimation.from[side];
  const valueFor = (stat) => {
    const elapsed = timestamp - statAnimation.started - statAnimation.delays[side][stat];
    const progress = Math.min(1, Math.max(0, elapsed / statAnimation.stepDuration));
    const eased = progress * progress * (3 - 2 * progress);
    return Math.round(
      (start[stat] + (fighter[stat] - start[stat]) * eased) * 10
    ) / 10;
  };
  return {
    ...fighter,
    health: valueFor("health"),
    stamina: valueFor("stamina"),
    mana: valueFor("mana"),
  };
}


function renderCommands() {
  if (!gameState) return;
  const activeFighter = gameState.mode === "two_player" && gameState.active_side === "enemy"
    ? gameState.enemy : gameState.player;
  const itemNames = { apple: "Apple", bandage: "Bandage", holywater: "HolyWater", steak: "Steak" };
  commandGrid.innerHTML = gameState.actions[activeTab].map((command) => `
    <button class="command-button command-${activeTab}" type="button" data-command="${command.id}"
      ${busy || animationLock || gameState.game_over || !command.available ? "disabled" : ""}>
      <span class="command-icon">${command.icon}</span><span class="command-name">${command.name}${activeTab === "items" ? ` (${activeFighter.inventory.filter((item) => item === itemNames[command.id]).length})` : ""}</span>
      <span class="command-cost">${command.cost}</span>
    </button>`).join("");
  commandGrid.querySelectorAll(".command-button").forEach((button) => {
    button.addEventListener("click", () => takeAction(button.dataset.command));
  });
}


function render() {
  if (!gameState || !gameState.player) return;
  const twoPlayer = gameState.mode === "two_player";
  const difficultyLabels = { dummy: "Dummy", easy: "Easy", normal: "Normal", hard: "Hard" };
  document.querySelector("#matchLabel").textContent = twoPlayer
    ? "2-Player duel" : `Singleplayer · ${difficultyLabels[gameState.bot_difficulty] || "Normal"}`;
  applyPlayerColors(twoPlayer);
  document.querySelector("#playerLabel").textContent = twoPlayer
    ? gameState.active_side === "player" ? "YOU" : "Player 1"
    : "YOU";
  document.querySelector("#enemyLabel").textContent = twoPlayer
    ? gameState.active_side === "enemy" ? "YOU" : "Player 2"
    : gameState.bot_difficulty === "dummy" ? "Dummy" : "Opponent";
  document.querySelector("#turnNumber").textContent = gameState.turn;
  document.querySelector("#turnOwner").textContent = animationLock && heldTurnOwner
    ? heldTurnOwner : gameState.game_over
    ? "Duel complete"
    : twoPlayer ? `${gameState.active_label}'s turn` : "Your turn";
  document.querySelector("#distanceValue").textContent = gameState.distance;
  document.querySelector("#arenaMessage").textContent = animationLock && heldArenaMessage
    ? heldArenaMessage : gameState.message;
  renderFighter("player", animatedFighter("player", gameState.player));
  renderFighter("enemy", animatedFighter("enemy", gameState.enemy));
  renderCommands();
  const chronologicalLog = [...gameState.log].reverse();
  const logList = document.querySelector("#logList");
  logList.innerHTML = chronologicalLog.map((entry, index) => {
    const previousEntry = chronologicalLog[index - 1];
    const showTurn = !previousEntry || previousEntry.turn !== entry.turn;
    return `<div class="log-entry"><span class="log-turn">${showTurn ? `${entry.turn}.` : ""}</span><span>${entry.message}</span></div>`;
  }).join("");
  logList.scrollTop = logList.scrollHeight;
  const showGameOver = gameState.game_over && !animationLock;
  document.querySelector("#gameOverPanel").hidden = !showGameOver;
  if (showGameOver) {
    const winnerName = gameState.winner === "player"
      ? "Player 1 wins"
      : twoPlayer ? "Player 2 wins" : "Bot wins";
    const winnerColor = gameState.winner === "player"
      ? gameShell.style.getPropertyValue("--p1-color")
      : gameShell.style.getPropertyValue("--p2-color");
    document.querySelector("#gameOverTitle").textContent = winnerName;
    document.querySelector("#gameOverWinner").textContent = "Duel complete";
    document.querySelector("#gameOverPanel").style.setProperty("--winner-color", winnerColor);
  }
  drawArena();
}


function applyPlayerColors(twoPlayer) {
  const sameClass = gameState.player.class_name === gameState.enemy.class_name;
  const basePlayer = CLASS_ART[gameState.player.class_name].color;
  const baseEnemy = CLASS_ART[gameState.enemy.class_name].color;
  const playerColor = sameClass ? lightenColor(basePlayer) : basePlayer;
  const enemyColor = sameClass ? darkenColor(baseEnemy) : baseEnemy;
  const colorSide = animationLock && heldActiveSide ? heldActiveSide : gameState.active_side;
  const activeColor = twoPlayer && colorSide === "enemy" ? enemyColor : playerColor;
  gameShell.style.setProperty("--p1-color", playerColor);
  gameShell.style.setProperty("--p2-color", enemyColor);
  gameShell.style.setProperty("--active-color", activeColor);
}


function showError(message) {
  const messageBox = document.querySelector("#arenaMessage");
  if (messageBox && !gameShell.hidden) messageBox.textContent = message;
  else window.alert(message);
}


//canvas only draws the state that Python returned
function startEffects(effects, previousStats = null) {
  transientControlStatuses = {
    player: { frozen: false, stunned: false },
    enemy: { frozen: false, stunned: false },
  };
  effects.forEach((effect) => {
    const target = effect.from === "player" ? "enemy" : "player";
    if (effect.type === "freeze" && effect.hit !== false) {
      transientControlStatuses[target].frozen = true;
    }
    if (effect.type === "strike" && effect.stunned) {
      transientControlStatuses[target].stunned = true;
    }
  });
  const sequencedEffects = [];
  for (let index = 0; index < effects.length; index++) {
    const effect = effects[index];
    const nextEffect = effects[index + 1];
    if (effect.type === "move"
        && ["charge", "super_charge"].includes(effect.action)) {
      sequencedEffects.push({ ...effect, type: "ready" });
      if (nextEffect?.type === "strike" && nextEffect.charged
          && nextEffect.from === effect.from) {
        sequencedEffects.push({
          ...effect,
          ...nextEffect,
          type: "charge_strike",
          action: effect.action,
        });
        index += 1;
      } else {
        sequencedEffects.push({ ...effect });
      }
    } else {
      sequencedEffects.push({ ...effect });
    }
  }
  animationQueue = sequencedEffects;
  const next = animationQueue.shift();
  const started = performance.now();
  const holdPlayerSubtitle = next?.from === "enemy"
    && gameState.mode !== "two_player" && Boolean(heldArenaMessage);
  if (holdPlayerSubtitle) {
    animationQueue.unshift(next);
    animation = null;
    animationGapUntil = started + PLAYER_EFFECT_MS;
  } else {
    animation = next ? { ...next, started } : null;
    animationGapUntil = 0;
  }
  if (animation?.from === "enemy" && gameState.mode !== "two_player") {
    heldTurnOwner = "Opponent's turn";
    heldArenaMessage = gameState.message;
  }
  if (animation) announceEffect(animation);
  const effectOffsets = [];
  let effectTime = 0;
  sequencedEffects.forEach((effect, index) => {
    effectOffsets.push(effectTime);
    effectTime += effectDuration(effect);
    if (index < sequencedEffects.length - 1) {
      effectTime += effectGapBetween(effect, sequencedEffects[index + 1]);
    }
  });
  const statsChanged = previousStats && ["player", "enemy"].some((side) =>
    ["health", "stamina", "mana"].some((stat) => previousStats[side][stat] !== gameState[side][stat]));
  const delays = {
    player: { health: 0, stamina: 0, mana: 0 },
    enemy: { health: 0, stamina: 0, mana: 0 },
  };
  const damagingSpells = new Set(["fireball", "freeze", "poison"]);
  const manaSpells = new Set(["fireball", "freeze", "poison", "push", "pull"]);
  sequencedEffects.forEach((effect, index) => {
    const offset = effectOffsets[index];
    const attacker = effect.from;
    const defender = attacker === "player" ? "enemy" : "player";
    if (effect.type === "strike" || effect.type === "charge_strike") {
      delays[attacker].stamina = offset;
      if (effect.hit) delays[defender].health = offset;
    } else if (manaSpells.has(effect.type)) {
      delays[attacker].mana = offset;
      if (damagingSpells.has(effect.type) && effect.hit !== false) {
        delays[defender].health = offset;
      }
    } else if (effect.type === "resistance") {
      delays[attacker].mana = offset;
    } else if (effect.type === "move" && effect.spell) {
      delays[effect.caster].mana = offset;
    } else if (effect.type === "move" && effect.action !== "charge") {
      delays[attacker].stamina = offset;
    }
  });
  statAnimation = statsChanged ? {
    from: previousStats,
    started,
    duration: Math.max(effectTime + 360, BOT_EFFECT_MS),
    stepDuration: 360,
    delays,
  } : null;
  animationLock = Boolean(animation || statAnimation);
  renderCommands();
}


function effectGapBetween(current, next) {
  const chargeSequence = (current?.type === "ready"
      && ["move", "charge_strike"].includes(next?.type)
      && ["charge", "super_charge"].includes(next.action))
    || (current?.type === "move"
      && ["charge", "super_charge"].includes(current.action)
      && next?.type === "strike" && next.charged);
  return chargeSequence ? 0 : EFFECT_GAP_MS;
}


function effectDuration(effect) {
  if (effect?.type === "ready") return 380;
  if (effect?.type === "scavenge") return 720;
  if (effect?.type === "meditate") return 900;
  if (effect?.type === "defeat") return 1200;
  if (effect?.type === "regen") return 850;
  if (effect?.type === "heal") return 650;
  if (effect?.type === "resistance") return 720;
  if (effect?.type === "strike" || effect?.type === "charge_strike") {
    if (effect.weapon === "Claymore") return 820;
    if (effect.weapon === "Staff") return 430;
    if (effect.weapon === "Daggers") return 680;
  }
  return effect?.from === "enemy" && gameState?.mode !== "two_player"
    ? BOT_EFFECT_MS : PLAYER_EFFECT_MS;
}


function announceEffect(effect) {
  if (effect.type !== "regen") return;
  const format = (side) => {
    const gain = effect.gains?.[side] || {};
    const parts = [["HP", gain.health], ["stamina", gain.stamina], ["mana", gain.mana]]
      .filter(([, value]) => value > 0).map(([name, value]) => `+${value} ${name}`);
    const label = side === "player" ? "P1"
      : gameState.mode === "two_player" ? "P2"
      : gameState.bot_difficulty === "dummy" ? "Dummy" : "Bot";
    return `${label} ${parts.join(", ") || "no recovery"}`;
  };
  heldArenaMessage = `Round recovery — ${format("player")} · ${format("enemy")}`;
  document.querySelector("#arenaMessage").textContent = heldArenaMessage;
}


function separationForDistance(distance, width) {
  return Math.min(Math.max(230, width - 60), 230 + Math.max(0, distance) * 25);
}


function fighterScaleForDistance(distance, width) {
  const naturalSeparation = 230 + Math.max(0, distance) * 25;
  return Math.max(.55, Math.min(1, (width - 220) / naturalSeparation));
}


function drawDistanceGrid(left, right, distance) {
  const y = 280;
  const units = Math.max(0, Math.round(distance));
  context.strokeStyle = "#68747d";
  context.fillStyle = "#a7b0b7";
  context.lineWidth = 1;
  context.font = '9px "Courier New", monospace';
  context.textAlign = "center";
  context.beginPath();
  context.moveTo(left, y);
  context.lineTo(right, y);
  context.stroke();
  const tickCount = Math.max(1, units);
  const labelEvery = Math.max(1, Math.ceil(tickCount / 10));
  for (let unit = 0; unit <= tickCount; unit++) {
    const x = left + (right - left) * unit / tickCount;
    context.fillRect(Math.round(x), y - (unit % labelEvery === 0 ? 7 : 4), 1, unit % labelEvery === 0 ? 10 : 7);
    if (unit % labelEvery === 0) context.fillText(String(unit), x, y + 15);
  }
}


function controlStatusVisible(targetSide, status) {
  const target = targetSide === "player" ? gameState.player : gameState.enemy;
  if (target.statuses[status] <= 0
      && !transientControlStatuses[targetSide][status]) return false;
  const attackerSide = targetSide === "player" ? "enemy" : "player";
  return gameState.bonus_actions[attackerSide] > 0
    || (animationLock && heldActiveSide === attackerSide);
}


function drawArena(timestamp = performance.now()) {
  if (!gameState || !gameState.player) return;
  const width = canvas.width;
  context.imageSmoothingEnabled = false;
  context.clearRect(0, 0, width, canvas.height);
  context.fillStyle = "#121821";
  context.fillRect(0, 0, width, canvas.height);
  context.fillStyle = "#1b2530";
  for (let x = 0; x < width; x += 80) context.fillRect(x, 46 + x % 160, 48, 5);
  context.fillStyle = "#26313a";
  context.fillRect(0, 258, width, 102);
  context.fillStyle = "#35414a";
  context.fillRect(0, 258, width, 8);
  context.fillStyle = "#202a32";
  for (let x = 12; x < width; x += 64) context.fillRect(x, 286 + x % 3 * 16, 34, 6);
  drawRuin(65, 140);
  drawRuin(width - 205, 126);
  const separation = separationForDistance(gameState.distance, width);
  const playerX = width / 2 - separation / 2;
  const enemyX = width / 2 + separation / 2;
  let playerDrawX = playerX;
  let enemyDrawX = enemyX;
  let displayedDistance = gameState.distance;
  let movementProgress = 1;
  const duration = effectDuration(animation);
  const animationActive = animation && timestamp - animation.started < duration;
  const statsActive = statAnimation && timestamp - statAnimation.started < statAnimation.duration;
  if (animationActive && animation.type === "ready") {
    displayedDistance = animation.from_distance;
    const readySeparation = separationForDistance(displayedDistance, width);
    playerDrawX = width / 2 - readySeparation / 2;
    enemyDrawX = width / 2 + readySeparation / 2;
  }
  if (animationActive && ["move", "charge_strike"].includes(animation.type)) {
    const rawProgress = Math.min(1, (timestamp - animation.started) / duration);
    const progress = rawProgress * rawProgress * (3 - 2 * rawProgress);
    movementProgress = progress;
    const oldSeparation = separationForDistance(animation.from_distance, width);
    const oldPlayerX = width / 2 - oldSeparation / 2;
    const oldEnemyX = width / 2 + oldSeparation / 2;
    const interimPlayerX = animation.from === "player" ? oldEnemyX - separation : oldPlayerX;
    const interimEnemyX = animation.from === "enemy" ? oldPlayerX + separation : oldEnemyX;
    if (progress < .7) {
      const moveProgress = progress / .7;
      playerDrawX = oldPlayerX + (interimPlayerX - oldPlayerX) * moveProgress;
      enemyDrawX = oldEnemyX + (interimEnemyX - oldEnemyX) * moveProgress;
    } else {
      const centerProgress = (progress - .7) / .3;
      playerDrawX = interimPlayerX + (playerX - interimPlayerX) * centerProgress;
      enemyDrawX = interimEnemyX + (enemyX - interimEnemyX) * centerProgress;
    }
    displayedDistance = animation.from_distance + (animation.to_distance - animation.from_distance) * progress;
  }
  const fighterScale = fighterScaleForDistance(displayedDistance, width);
  let playerWeaponAngle = 0;
  let enemyWeaponAngle = 0;
  let playerBodyAngle = 0;
  let enemyBodyAngle = 0;
  const queuedChargeStrike = animationQueue.find((effect) => effect.type === "charge_strike");
  const activeChargeAttacker = animationActive && animation?.type === "charge_strike"
    ? animation.from
    : animation?.type === "ready" && queuedChargeStrike ? animation.from : null;
  const suppressPlayerStun = activeChargeAttacker === "enemy";
  const suppressEnemyStun = activeChargeAttacker === "player";
  const playerFrozenVisible = controlStatusVisible("player", "frozen");
  const enemyFrozenVisible = controlStatusVisible("enemy", "frozen");
  const playerStunnedVisible = controlStatusVisible("player", "stunned");
  const enemyStunnedVisible = controlStatusVisible("enemy", "stunned");
  let playerEyesClosed = playerFrozenVisible
    || (playerStunnedVisible && !suppressPlayerStun);
  let enemyEyesClosed = enemyFrozenVisible
    || (enemyStunnedVisible && !suppressEnemyStun);
  let playerWeaponHidden = false;
  let enemyWeaponHidden = false;
  let playerWeaponOffset = 0;
  let enemyWeaponOffset = 0;
  let playerPose = "stand";
  let enemyPose = "stand";
  let playerPoseAmount = 0;
  let enemyPoseAmount = 0;
  if (animationActive && ["move", "charge_strike"].includes(animation.type)) {
    const rawLean = Math.min(1, (timestamp - animation.started) / duration);
    const leanWave = Math.sin(rawLean * Math.PI);
    const toward = animation.action === "approach"
      || ["charge", "super_charge"].includes(animation.action)
      || animation.spell === "pull";
    const degrees = ["approach", "step_back"].includes(animation.action) ? 10 : 25;
    const lean = (toward ? 1 : -1) * degrees * Math.PI / 180 * leanWave;
    if (animation.from === "player") playerBodyAngle = lean;
    else enemyBodyAngle = -lean;
  } else if (animationActive && animation.type === "scavenge") {
    const bend = Math.sin(Math.min(1, (timestamp - animation.started) / duration) * Math.PI);
    if (animation.from === "player") {
      playerBodyAngle = Math.PI / 4 * bend;
      playerPose = "scavenge";
    } else {
      enemyBodyAngle = -Math.PI / 4 * bend;
      enemyPose = "scavenge";
    }
  } else if (animationActive && animation.type === "meditate") {
    const phase = Math.min(1, (timestamp - animation.started) / duration);
    const transition = phase < .3 ? phase / .3 : phase > .7 ? (1 - phase) / .3 : 1;
    const sit = transition * transition * (3 - 2 * transition);
    if (animation.from === "player") {
      playerPose = "meditate";
      playerPoseAmount = sit;
      playerEyesClosed = sit > .2;
    } else {
      enemyPose = "meditate";
      enemyPoseAmount = sit;
      enemyEyesClosed = sit > .2;
    }
  }
  // Ease through the final unit of distance so entering attack range does not
  // snap the weapon between its carried and ready positions.
  let playerWeaponReady = Math.max(0, Math.min(1,
    gameState.player.weapon.range + 1 - displayedDistance));
  let enemyWeaponReady = Math.max(0, Math.min(1,
    gameState.enemy.weapon.range + 1 - displayedDistance));
  if (animationActive && animation.type === "ready") {
    const rawReady = Math.min(1, (timestamp - animation.started) / duration);
    const easedReady = rawReady * rawReady * (3 - 2 * rawReady);
    const fighter = animation.from === "player" ? gameState.player : gameState.enemy;
    const startingReady = Math.max(0, Math.min(1,
      fighter.weapon.range + 1 - animation.from_distance));
    const ready = startingReady + (1 - startingReady) * easedReady;
    if (animation.from === "player") playerWeaponReady = ready;
    else enemyWeaponReady = ready;
  }
  const holdingChargePose = animation?.type === "ready"
    && ["move", "charge_strike"].includes(animationQueue[0]?.type)
    && ["charge", "super_charge"].includes(animationQueue[0]?.action);
  if (holdingChargePose && !animationActive) {
    if (animation.from === "player") playerWeaponReady = 1;
    else enemyWeaponReady = 1;
  }
  if (animationActive && ["move", "charge_strike"].includes(animation.type)
      && ["charge", "super_charge"].includes(animation.action)) {
    if (animation.from === "player") playerWeaponReady = 1;
    else enemyWeaponReady = 1;
  }
  if (animationActive && ["strike", "charge_strike"].includes(animation.type)) {
    if (animation.from === "player") playerWeaponReady = 1;
    else enemyWeaponReady = 1;
    const progress = Math.min(1, (timestamp - animation.started) / duration);
    const weapon = animation.weapon || (animation.from === "player"
      ? gameState.player.weapon.name : gameState.enemy.weapon.name);
    let angle = 0;
    let offset = 0;
    if (weapon === "Staff") {
      offset = Math.sin(progress * Math.PI) * 54;
    } else {
      const liftEnd = weapon === "Claymore" ? .74 : .66;
      const liftAngle = weapon === "Claymore" ? -Math.PI * .58 : -Math.PI / 3;
      const finishAngle = weapon === "Claymore" ? Math.PI * .38 : Math.PI / 6;
      if (progress < liftEnd) {
        const lift = progress / liftEnd;
        const easedLift = lift * lift * (3 - 2 * lift);
        angle = liftAngle * easedLift;
      } else {
        const swing = (progress - liftEnd) / (1 - liftEnd);
        const fastSwing = 1 - (1 - swing) * (1 - swing);
        angle = liftAngle + (finishAngle - liftAngle) * fastSwing;
      }
    }
    if (weapon === "Daggers" && animation.type === "strike") {
      const dash = Math.sin(progress * Math.PI) * Math.min(145, separation * .28);
      if (animation.from === "player") playerDrawX += dash;
      else enemyDrawX -= dash;
    }
    if (animation.from === "player") {
      playerWeaponAngle = angle;
      playerWeaponOffset = offset;
    } else {
      enemyWeaponAngle = angle;
      enemyWeaponOffset = offset;
    }
  } else if ((animation && animation.type === "defeat") || defeatSettled) {
    const progress = defeatSettled ? 1 : Math.min(1, (timestamp - animation.started) / duration);
    const fall = progress * progress * (3 - 2 * progress);
    const fallAngle = Math.PI / 2 * fall;
    const defeatWinner = defeatSettled ? gameState.winner : animation.winner;
    const defeatedSide = defeatSettled
      ? (gameState.winner === "player" ? "enemy" : "player")
      : animation.from;
    playerWeaponAngle = defeatWinner === "player" ? Math.PI / 7 * fall : 0;
    enemyWeaponAngle = defeatWinner === "enemy" ? Math.PI / 7 * fall : 0;
    if (defeatedSide === "player") {
      playerBodyAngle = -fallAngle;
      playerEyesClosed = progress > .2;
      playerWeaponHidden = true;
    } else {
      enemyBodyAngle = fallAngle;
      enemyEyesClosed = progress > .2;
      enemyWeaponHidden = true;
    }
  }
  drawDistanceGrid(playerDrawX, enemyDrawX, displayedDistance);
  const playerIceVisible = playerFrozenVisible
    || (animationActive && animation.type === "freeze"
      && animation.from === "enemy" && animation.hit !== false);
  const enemyIceVisible = enemyFrozenVisible
    || (animationActive && animation.type === "freeze"
      && animation.from === "player" && animation.hit !== false);
  if (playerIceVisible) drawIceGlintBehind(playerDrawX, fighterScale);
  if (enemyIceVisible) drawIceGlintBehind(enemyDrawX, fighterScale);
  const samePlayerClass = gameState.player.class_name === gameState.enemy.class_name;
  drawFighter(playerDrawX, 256, gameState.player, false, samePlayerClass ? "light" : "original", fighterScale, playerWeaponAngle, playerBodyAngle, playerEyesClosed, playerWeaponHidden, context, playerWeaponOffset, playerWeaponReady, playerPose, playerPoseAmount);
  drawFighter(enemyDrawX, 256, gameState.enemy, true, samePlayerClass ? "dark" : "original", fighterScale, enemyWeaponAngle, enemyBodyAngle, enemyEyesClosed, enemyWeaponHidden, context, enemyWeaponOffset, enemyWeaponReady, enemyPose, enemyPoseAmount);
  drawPersistentStatusEffects(playerDrawX, gameState.player, fighterScale, timestamp,
    false, playerStunnedVisible && !suppressPlayerStun, playerFrozenVisible, 1);
  drawPersistentStatusEffects(enemyDrawX, gameState.enemy, fighterScale, timestamp,
    animationActive && animation.type === "freeze"
      && animation.from === "player" && animation.hit !== false,
    enemyStunnedVisible && !suppressEnemyStun, enemyFrozenVisible, -1);
  if (animationActive && animation.type === "freeze"
      && animation.from === "enemy" && animation.hit !== false) {
    drawIceBlock(playerDrawX, fighterScale);
  }
  if (animationActive && ["move", "charge_strike"].includes(animation.type)
      && ["approach", "step_back", "charge", "super_charge", "escape"].includes(animation.action)) {
    const subtleTrail = ["approach", "step_back"].includes(animation.action);
    drawAirTrail(animation, playerDrawX, enemyDrawX, fighterScale, timestamp, subtleTrail);
  }
  if (animationActive && ["strike", "charge_strike"].includes(animation.type)
      && animation.hit) {
    drawHitSweep(animation, playerDrawX, enemyDrawX, fighterScale, timestamp);
    if (animation.critical) {
      drawCriticalMarks(animation, playerDrawX, enemyDrawX, fighterScale, timestamp);
    }
  }
  if (animationActive
      && (["strike", "charge_strike"].includes(animation.type)
        || animation.type === "defeat")) {
    const strength = animation.type === "defeat" ? 8
      : animation.hit
        ? (animation.super_charge ? 5.5 : animation.charged ? 4 : 1.6)
        : .6;
    const phase = (timestamp - animation.started) / 28;
    canvas.style.transform = `translate(${Math.sin(phase) * strength}px, ${Math.cos(phase * 1.7) * strength}px)`;
  } else {
    canvas.style.transform = "";
  }
  if (animationActive && animation.type === "defeat") {
    drawThrownWeapon(animation, playerDrawX, enemyDrawX, fighterScale, timestamp);
  }
  if (statsActive) {
    renderFighter("player", animatedFighter("player", gameState.player, timestamp));
    renderFighter("enemy", animatedFighter("enemy", gameState.enemy, timestamp));
  }
  if (animationActive) {
    if (["fireball", "freeze", "poison", "push", "pull"].includes(animation.type)) {
      drawEffect(animation, playerDrawX, enemyDrawX, timestamp, fighterScale);
    } else if (animation.type === "heal") {
      drawHealParticles(animation, playerDrawX, enemyDrawX, fighterScale, timestamp);
    } else if (animation.type === "regen") {
      drawRegenParticles(animation, playerDrawX, enemyDrawX, fighterScale, timestamp);
    }
    requestAnimationFrame(drawArena);
  } else if (animationQueue.length) {
    if (!animationGapUntil) {
      animationGapUntil = timestamp + effectGapBetween(animation, animationQueue[0]);
    }
    if (timestamp >= animationGapUntil) {
      animation = { ...animationQueue.shift(), started: timestamp };
      announceEffect(animation);
      if (animation.from === "enemy" && gameState.mode !== "two_player") {
        heldTurnOwner = "Opponent's turn";
        heldArenaMessage = gameState.message;
        document.querySelector("#turnOwner").textContent = heldTurnOwner;
        document.querySelector("#arenaMessage").textContent = heldArenaMessage;
      }
      animationGapUntil = 0;
    } else {
      animation = null;
    }
    requestAnimationFrame(drawArena);
  } else if (statsActive) {
    requestAnimationFrame(drawArena);
  } else {
    if (animation?.type === "defeat") defeatSettled = true;
    animation = null;
    animationGapUntil = 0;
    statAnimation = null;
    transientControlStatuses = {
      player: { frozen: false, stunned: false },
      enemy: { frozen: false, stunned: false },
    };
    if (animationLock) {
      animationLock = false;
      heldTurnOwner = "";
      heldArenaMessage = "";
      heldActiveSide = "";
      render();
      if (gameState.pending_bot_turn) runPendingBotTurn();
    } else if (["fire", "poison", "resistance"].some((status) =>
      gameState.player.statuses[status] > 0 || gameState.enemy.statuses[status] > 0)
      || controlStatusVisible("player", "stunned")
      || controlStatusVisible("enemy", "stunned")) {
      requestAnimationFrame(drawArena);
    }
  }
}


function drawRuin(x, y) {
  context.fillStyle = "#303942";
  context.fillRect(x, y, 24, 118);
  context.fillRect(x + 76, y + 28, 24, 90);
  context.fillRect(x, y, 100, 18);
  context.fillStyle = "#151b22";
  context.fillRect(x + 38, y + 44, 24, 74);
}


function darkenColor(hex, amount = 0.80) {
  const value = Number.parseInt(hex.slice(1), 16);
  const channel = (shift) => Math.round(((value >> shift) & 255) * amount);
  return `rgb(${channel(16)}, ${channel(8)}, ${channel(0)})`;
}


function lightenColor(hex, amount = 0.20) {
  const value = Number.parseInt(hex.slice(1), 16);
  const channel = (shift) => {
    const original = (value >> shift) & 255;
    return Math.round(original + (255 - original) * amount);
  };
  return `rgb(${channel(16)}, ${channel(8)}, ${channel(0)})`;
}


function drawTitleWeapon(context, name, x, y, rotation, flipped = false) {
  context.save();
  context.translate(Math.round(x), Math.round(y));
  context.rotate(rotation);
  context.scale(flipped ? -1.15 : 1.15, 1.15);
  drawWeapon(name, context);
  context.restore();
}


function drawTitleDecorations() {
  const width = Math.max(1, Math.round(titleDecorCanvas.clientWidth));
  const height = Math.max(1, Math.round(titleDecorCanvas.clientHeight));
  titleDecorCanvas.width = width;
  titleDecorCanvas.height = height;
  titleDecorContext.imageSmoothingEnabled = false;
  titleDecorContext.clearRect(0, 0, width, height);
  const titleFighters = [
    { class_name: "Assassin", weapon: { name: "Daggers" }, hair_color: "#0b1017" },
    { class_name: "Juggernaut", weapon: { name: "Claymore" }, hair_color: "#65472f" },
    { class_name: "Sorcerer", weapon: { name: "Staff" }, hair_color: "#e2c36f" },
    { class_name: "Swordsman", weapon: { name: "Sword" }, hair_color: "#e8e8e2" },
  ];
  drawFighter(width * .07, height * .43, titleFighters[0], false, "original", 1.12, 0, -.10, false, true, titleDecorContext);
  drawFighter(width * .93, height * .45, titleFighters[1], true, "original", 1.12, 0, .10, false, true, titleDecorContext);
  drawFighter(width * .08, height * .97, titleFighters[2], true, "original", 1.12, 0, .08, false, true, titleDecorContext);
  drawFighter(width * .92, height * .97, titleFighters[3], false, "original", 1.12, 0, -.08, false, true, titleDecorContext);
  drawTitleWeapon(titleDecorContext, "Claymore", width * .20, height * .19, .42);
  drawTitleWeapon(titleDecorContext, "Sword", width * .77, height * .19, -.31, true);
  drawTitleWeapon(titleDecorContext, "Daggers", width * .20, height * .83, -.38);
  drawTitleWeapon(titleDecorContext, "Staff", width * .78, height * .84, .83, true);
}


function drawWeapon(weaponName, context) {
  if (weaponName === "Claymore") {
    context.fillStyle = "#65472f";
    context.fillRect(12, -66, 22, 7);
    context.fillStyle = "#aeb5bd";
    context.fillRect(30, -75, 5, 25);
    context.fillStyle = "#737b85";
    context.fillRect(34, -68, 92, 13);
    context.beginPath();
    context.moveTo(126, -68);
    context.lineTo(140, -61.5);
    context.lineTo(126, -55);
    context.closePath();
    context.fill();
    context.fillStyle = "#d9dde2";
    context.fillRect(37, -66, 88, 3);
    return;
  }

  if (weaponName === "Staff") {
    context.fillStyle = "#76502c";
    context.fillRect(14, -65, 88, 7);
    context.fillStyle = "#9a6b38";
    context.fillRect(20, -63, 78, 2);
    // Mirrored upper and lower cup arms keep the head symmetric around the shaft.
    context.strokeStyle = "#76502c";
    context.lineWidth = 3;
    context.beginPath();
    context.moveTo(98, -66);
    context.quadraticCurveTo(106, -75, 114, -70);
    context.moveTo(98, -60);
    context.quadraticCurveTo(106, -51, 114, -56);
    context.stroke();
    context.strokeStyle = "#9a6b38";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(99, -65);
    context.quadraticCurveTo(106, -72, 112, -68);
    context.moveTo(99, -61);
    context.quadraticCurveTo(106, -54, 112, -58);
    context.stroke();
    // The magic orb floats just beyond the open cup instead of filling it.
    context.fillStyle = "rgba(169, 112, 255, .18)";
    context.fillRect(112, -69, 13, 13);
    context.fillStyle = "rgba(169, 112, 255, .35)";
    context.fillRect(114, -67, 10, 10);
    context.fillStyle = "#8f50ed";
    context.fillRect(116, -65, 7, 7);
    context.fillStyle = "#c8a8ff";
    context.fillRect(118, -64, 4, 4);
    context.fillStyle = "#f0e8ff";
    context.fillRect(119, -64, 2, 2);
    return;
  }

  if (weaponName === "Sword") {
    // The guard joint sits exactly between the handle and the blade.
    context.fillStyle = "#6b4a2b";
    context.fillRect(9, -66, 20, 7);
    context.fillStyle = "#c39a42";
    context.fillRect(27, -70, 5, 15);
    context.strokeStyle = "#c39a42";
    context.lineWidth = 4;
    context.beginPath();
    context.arc(24, -62, 12, -1.35, 1.35);
    context.stroke();
    // The straight blade shares the handle's horizontal center line.
    context.fillStyle = "#929aa4";
    context.fillRect(29, -68, 72, 10);
    context.beginPath();
    context.moveTo(101, -68);
    context.lineTo(112, -63);
    context.lineTo(101, -58);
    context.closePath();
    context.fill();
    context.strokeStyle = "#dce1e6";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(32, -65);
    context.lineTo(103, -65);
    context.stroke();
    return;
  }

  //Daggers are deliberately much shorter than every other weapon.
  context.fillStyle = "#69472c";
  context.fillRect(12, -75, 18, 5);
  context.fillRect(12, -60, 18, 5);
  context.fillStyle = "#7b838c";
  context.fillRect(28, -78, 4, 11);
  context.fillRect(28, -63, 4, 11);
  context.fillStyle = "#b8c0c8";
  context.fillRect(32, -75, 25, 5);
  context.beginPath();
  context.moveTo(57, -75);
  context.lineTo(65, -72.5);
  context.lineTo(57, -70);
  context.closePath();
  context.fill();
  context.fillRect(32, -60, 25, 5);
  context.beginPath();
  context.moveTo(57, -60);
  context.lineTo(65, -57.5);
  context.lineTo(57, -55);
  context.closePath();
  context.fill();
  context.fillStyle = "#e1e5e9";
  context.fillRect(34, -74, 21, 1);
  context.fillRect(34, -59, 21, 1);
}


function drawFighter(x, groundY, fighter, flipped, clothesShade, scale = 1, weaponAngle = 0,
  bodyAngle = 0, eyesClosed = false, weaponHidden = false, renderContext = context,
  weaponOffset = 0, weaponReady = 0, pose = "stand", poseAmount = 0) {
  renderContext.save();
  renderContext.translate(Math.round(x), groundY);
  renderContext.rotate(bodyAngle);
  renderContext.scale((flipped ? -1 : 1) * scale, scale);
  if (pose === "meditate") renderContext.translate(0, 28 * poseAmount);
  const classColor = CLASS_ART[fighter.class_name].color;
  renderContext.fillStyle = clothesShade === "light"
    ? lightenColor(classColor)
    : clothesShade === "dark" ? darkenColor(classColor) : classColor;
  renderContext.fillRect(-14, -84, 34, 52);
  if (pose === "meditate") {
    // One foreground leg represents the seated pair; its bottom stays exactly
    // on the arena floor while the torso lowers and rises.
    renderContext.fillRect(-8, -12 - 28 * poseAmount, 48, 12);
  } else {
    renderContext.fillRect(-14, -32, 14, 34);
    renderContext.fillRect(6, -32, 14, 34);
  }
  renderContext.fillStyle = "#d8c7a6";
  renderContext.fillRect(-9, -103, 24, 19);
  renderContext.fillStyle = fighter.hair_color || "#0b1017";
  renderContext.fillRect(-12, -111, 30, 8);
  if (!eyesClosed) {
    renderContext.fillStyle = "#0b1017";
    renderContext.fillRect(3, -100, 15, 4);
  }
  renderContext.fillStyle = "#d8c7a6";
  renderContext.fillRect(15, -97, 4, 5);
  if (!weaponHidden) {
    const weaponName = fighter.weapon.name;
    // A compact leather waistband supports the cutlass and dagger mounts
    // without drawing oversized sheaths down the character's legs.
    if (weaponName === "Daggers" || weaponName === "Sword") {
      renderContext.fillStyle = "#352014";
      renderContext.fillRect(-15, -38, 36, 8);
      renderContext.fillStyle = "#5a3720";
      renderContext.fillRect(-15, -38, 36, 3);
      renderContext.fillStyle = "#a07038";
      renderContext.fillRect(1, -38, 6, 8);
    }
    renderContext.save();
    renderContext.translate(weaponOffset, 0);
    const idlePose = {
      Staff: { x: 36, y: -51, angle: -Math.PI / 2, scale: 1, px: 65, py: -61 },
      Daggers: { x: 5, y: -48, angle: Math.PI / 2, scale: 1, px: 20, py: -67 },
      Sword: { x: 4, y: -66, angle: Math.PI / 2, scale: .7, px: 20, py: -62 },
      Claymore: { x: 7, y: -88, angle: Math.PI, scale: 1, px: 20, py: -62 },
    }[weaponName];
    const blend = Math.max(0, Math.min(1, weaponReady));
    const smoothBlend = blend * blend * (3 - 2 * blend);
    const x = idlePose.x + (14 - idlePose.x) * smoothBlend;
    const y = idlePose.y + (-61 - idlePose.y) * smoothBlend;
    const angle = idlePose.angle + (weaponAngle - idlePose.angle) * smoothBlend;
    const weaponScale = idlePose.scale + (1 - idlePose.scale) * smoothBlend;
    const pivotX = idlePose.px + (14 - idlePose.px) * smoothBlend;
    const pivotY = idlePose.py + (-61 - idlePose.py) * smoothBlend;
    renderContext.translate(x, y);
    renderContext.rotate(angle);
    renderContext.scale(weaponScale, weaponScale);
    renderContext.translate(-pivotX, -pivotY);
    drawWeapon(weaponName, renderContext);
    renderContext.fillStyle = "#d8c7a6";
    if (weaponName === "Daggers") {
      const handX = 10;
      const upperY = -76 + 2 * smoothBlend;
      const lowerY = -61 + 2 * smoothBlend;
      renderContext.fillRect(handX, upperY, 16, 5);
      renderContext.fillRect(handX, lowerY, 16, 5);
    } else if (weaponName === "Staff") {
      const handX = 59 + (10 - 59) * smoothBlend;
      const handY = -64 + 3 * smoothBlend;
      renderContext.fillRect(handX, handY, 16, 6);
    } else {
      renderContext.fillRect(10, -61, 16, 5);
    }
    renderContext.restore();
  }
  renderContext.restore();
}


function drawPersistentStatusEffects(x, fighter, scale, timestamp, forceIce,
    showStun, showIce, facing) {
  const groundY = 256;
  if (showStun) {
    context.fillStyle = "#ffd85a";
    for (let index = 0; index < 3; index++) {
      const phase = timestamp / 260 + index * Math.PI * 2 / 3;
      const px = x + Math.cos(phase) * 28 * scale;
      const py = groundY - (120 + Math.sin(phase) * 8) * scale;
      context.fillRect(px - 3 * scale, py - 3 * scale, 6 * scale, 6 * scale);
    }
  }
  if (fighter.statuses.poison > 0) {
    context.fillStyle = "rgba(72, 190, 76, .22)";
    context.fillRect(x - 19 * scale, groundY - 112 * scale, 42 * scale, 112 * scale);
    context.fillStyle = "#67d85f";
    for (let index = 0; index < 6; index++) {
      const drift = (timestamp / 22 + index * 31) % 92;
      context.fillRect(x + ((index % 3) - 1) * 18 * scale, groundY - drift * scale, 5 * scale, 5 * scale);
    }
  }
  if (fighter.statuses.resistance > 0) {
    drawResistanceShield(x + facing * 3 * scale, scale * 1.1, timestamp);
  }
  if (forceIce || showIce) drawIceBlock(x, scale);
  // Flames are deliberately drawn after ice so simultaneous Fire and Freeze
  // remain visible instead of the translucent ice block hiding the burn.
  if (fighter.statuses.fire > 0) {
    for (let index = 0; index < 8; index++) {
      const flicker = (Math.floor(timestamp / 70) + index) % 4;
      context.fillStyle = index % 2 ? "#ffb22e" : "#ef552f";
      const px = x + ((index % 4) - 1.5) * 11 * scale;
      const py = groundY - (18 + Math.floor(index / 4) * 28 + flicker * 6) * scale;
      context.fillRect(px, py, 8 * scale, (13 + flicker * 3) * scale);
    }
  }
}


function drawResistanceShield(x, scale, timestamp) {
  const pulse = .86 + Math.sin(timestamp / 180) * .06;
  context.save();
  context.translate(x, 198);
  context.scale(scale * pulse, scale);
  context.fillStyle = "rgba(120, 216, 255, .12)";
  context.strokeStyle = "rgba(150, 230, 255, .82)";
  context.lineWidth = 4;
  context.beginPath();
  context.ellipse(0, 0, 38, 62, 0, 0, Math.PI * 2);
  context.fill();
  context.stroke();
  context.restore();
}


function drawIceBlock(x, scale) {
  context.fillStyle = "rgba(115, 218, 245, .28)";
  context.fillRect(x - 27 * scale, 256 - 118 * scale, 58 * scale, 120 * scale);
  context.strokeStyle = "rgba(190, 245, 255, .85)";
  context.lineWidth = Math.max(2, 3 * scale);
  context.strokeRect(x - 27 * scale, 256 - 118 * scale, 58 * scale, 120 * scale);
}


function drawIceGlintBehind(x, scale) {
  context.fillStyle = "rgba(232, 253, 255, .7)";
  context.fillRect(x - 20 * scale, 256 - 109 * scale, 7 * scale, 42 * scale);
}


function drawAirTrail(effect, playerX, enemyX, scale, timestamp, subtle = false) {
  const moverX = effect.from === "player" ? playerX : enemyX;
  const direction = effect.to_distance > effect.from_distance
    ? (effect.from === "player" ? -1 : 1)
    : (effect.from === "player" ? 1 : -1);
  const pulse = (timestamp - effect.started) / effectDuration(effect);
  context.strokeStyle = effect.spell ? "rgba(185,225,255,.75)"
    : subtle ? "rgba(210,225,235,.65)" : "rgba(210,225,235,.48)";
  context.lineWidth = subtle ? 2 : 3;
  const lineCount = subtle ? 3 : 4;
  for (let index = 0; index < lineCount; index++) {
    const y = 184 + index * 14;
    const baseLength = subtle ? 18 : 34;
    const length = (baseLength + index * (subtle ? 5 : 9)) * scale * (1 - pulse * .35);
    context.beginPath();
    context.moveTo(moverX - direction * 20 * scale, y);
    context.lineTo(moverX - direction * (20 * scale + length), y + direction * 3);
    context.stroke();
  }
}


function drawHitSweep(effect, playerX, enemyX, scale, timestamp) {
  const progress = Math.min(1, (timestamp - effect.started) / effectDuration(effect));
  if (progress < .62) return;
  const targetX = effect.from === "player" ? enemyX : playerX;
  const direction = effect.from === "player" ? 1 : -1;
  const sweep = (progress - .62) / .38;
  context.strokeStyle = `rgba(255, 235, 145, ${1 - sweep})`;
  context.lineWidth = 6 * scale;
  context.save();
  context.translate(targetX - direction * 5 * scale, 205);
  context.scale(direction, 1);
  context.beginPath();
  context.arc(0, 0, 32 * scale, -1.25 + sweep * .35, 1.25 + sweep * .35);
  context.stroke();
  context.restore();
}


function drawCriticalMarks(effect, playerX, enemyX, scale, timestamp) {
  const progress = Math.min(1, (timestamp - effect.started) / effectDuration(effect));
  if (progress < .58) return;
  const targetX = effect.from === "player" ? enemyX : playerX;
  const fade = 1 - (progress - .58) / .42;
  context.save();
  context.strokeStyle = `rgba(242, 58, 67, ${Math.max(0, fade)})`;
  context.lineWidth = Math.max(3, 5 * scale);
  for (let index = 0; index < 3; index++) {
    const centerX = targetX + (index - 1) * 23 * scale;
    const centerY = 184 + (index % 2) * 25 * scale;
    const radius = 8 * scale;
    context.beginPath();
    context.moveTo(centerX - radius, centerY - radius);
    context.lineTo(centerX + radius, centerY + radius);
    context.moveTo(centerX + radius, centerY - radius);
    context.lineTo(centerX - radius, centerY + radius);
    context.stroke();
  }
  context.restore();
}


function drawHealParticles(effect, playerX, enemyX, scale, timestamp) {
  const x = effect.from === "player" ? playerX : enemyX;
  const progress = (timestamp - effect.started) / effectDuration(effect);
  context.fillStyle = "#ef4e58";
  context.font = `${Math.max(15, 22 * scale)}px "Courier New"`;
  context.textAlign = "center";
  for (let index = 0; index < 6; index++) {
    const local = (progress + index / 6) % 1;
    context.globalAlpha = 1 - local;
    context.fillText("+", x + ((index % 3) - 1) * 25 * scale, 235 - local * 105 * scale);
  }
  context.globalAlpha = 1;
}


function drawRegenParticles(effect, playerX, enemyX, scale, timestamp) {
  drawHealParticles({ ...effect, from: "player" }, playerX, enemyX, scale, timestamp);
  drawHealParticles({ ...effect, from: "enemy" }, playerX, enemyX, scale, timestamp);
}


function drawThrownWeapon(effect, playerX, enemyX, fighterScale, timestamp) {
  const progress = Math.min(1, (timestamp - effect.started) / effectDuration(effect));
  const loser = effect.from === "player" ? gameState.player : gameState.enemy;
  const startX = effect.from === "player" ? playerX : enemyX;
  const direction = effect.throw_direction || 1;
  const x = startX + direction * canvas.width * 1.15 * progress;
  const y = 256 - 61 * fighterScale - Math.sin(progress * Math.PI) * 180 + progress * 120;
  context.save();
  context.translate(x, y);
  context.rotate(direction * progress * Math.PI * 4);
  context.scale(fighterScale, fighterScale);
  context.translate(-14, 61);
  drawWeapon(loser.weapon.name, context);
  context.restore();
}


function drawEffect(effect, playerX, enemyX, timestamp, fighterScale = 1) {
  const progress = Math.min(1, (timestamp - effect.started) / effectDuration(effect));
  const attacker = effect.from === "player" ? gameState.player : gameState.enemy;
  const direction = effect.from === "player" ? 1 : -1;
  const originOffset = attacker.weapon.name === "Staff" ? 115 : 24;
  const from = (effect.from === "player" ? playerX : enemyX) + direction * originOffset * fighterScale;
  const opponentX = effect.from === "player" ? enemyX : playerX;
  // A missed spell keeps travelling beyond the target and completely exits
  // the arena rather than stopping shortly behind the opponent.
  const to = effect.hit === false
    ? (direction > 0 ? canvas.width + 80 : -80) : opponentX;
  const x = from + (to - from) * progress;
  const colors = {
    fireball: "#ef6f3e", freeze: "#8fe6f1", poison: "#78c45b",
    push: "#b9e1ff", pull: "#b9e1ff", strike: "#a970ff",
  };
  const size = 20;
  context.fillStyle = colors[effect.type] || "#a970ff";
  const baseY = 256 - 61 * fighterScale;
  const y = effect.hit === false
    ? baseY + (effect.miss_y || 1) * 210 * fighterScale
      * Math.sin(progress * Math.PI / 2)
    : baseY;
  context.fillRect(x - size / 2, y - size / 2, size, size);
  context.fillRect(x - direction * size, y, size / 2, size / 2);
}


document.querySelectorAll(".mode-button").forEach((button) => {
  button.addEventListener("click", () => openSetup(button.dataset.mode));
});
document.querySelectorAll(".picker-button").forEach((button) => {
  button.addEventListener("click", () => {
    selectedSetupSide = button.dataset.side;
    updatePlayerPicker();
    buildClassChoices();
  });
});
document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    activeTab = tab.dataset.tab;
    document.querySelectorAll(".tab").forEach((button) => {
      const isActive = button === tab;
      button.classList.toggle("active", isActive);
      button.setAttribute("aria-selected", String(isActive));
    });
    renderCommands();
  });
});
document.querySelectorAll(".tutorial-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tutorial-tab").forEach((button) => button.classList.toggle("active", button === tab));
    document.querySelectorAll(".tutorial-pane").forEach((pane) => pane.classList.toggle("active", pane.dataset.pane === tab.dataset.tutorial));
  });
});
document.querySelector("#setupForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await startGame();
    setupDialog.close();
  } catch (error) { showError(error.message); }
});
document.querySelector("#acceptWeaponButton").addEventListener("click", () => resolveWeaponChoice(true));
document.querySelector("#rejectWeaponButton").addEventListener("click", () => resolveWeaponChoice(false));
document.querySelector("#setupCloseButton").addEventListener("click", () => setupDialog.close());
document.querySelector("#tutorialButton").addEventListener("click", () => tutorialDialog.showModal());
document.querySelector("#tutorialCloseButton").addEventListener("click", () => tutorialDialog.close());
document.querySelector("#newGameButton").addEventListener("click", () => leaveDialog.showModal());
document.querySelector("#cancelLeaveButton").addEventListener("click", () => leaveDialog.close());
document.querySelector("#confirmLeaveButton").addEventListener("click", () => {
  leaveDialog.close();
  returnToTitle();
});
document.querySelector("#gameOverMenuButton").addEventListener("click", returnToTitle);
document.querySelector("#rematchButton").addEventListener("click", async () => {
  document.querySelector("#gameOverPanel").hidden = true;
  try { await startGame(lastMatchConfig); } catch (error) { showError(error.message); }
});
document.querySelector("#clearLogButton").addEventListener("click", () => { document.querySelector("#logList").innerHTML = ""; });
window.addEventListener("resize", drawArena);
window.addEventListener("resize", drawTitleDecorations);

loadGame();
