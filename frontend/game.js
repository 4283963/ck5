const WS_URL = "ws://localhost:8765";

let ws = null;
let player = null;
let reconnectTimer = null;

const $ = (id) => document.getElementById(id);

const loginScreen = $("login-screen");
const gameScreen = $("game-screen");
const loginBtn = $("login-btn");
const usernameInput = $("username");
const playerNameEl = $("player-name");
const connectionDot = $("connection-dot");

const oreBar = $("ore-bar");
const oreValue = $("ore-value");
const fuelBar = $("fuel-bar");
const fuelValue = $("fuel-value");
const oxygenBar = $("oxygen-bar");
const oxygenValue = $("oxygen-value");
const cargoValue = $("cargo-value");

const miningBtn = $("mining-btn");
const miningStatus = $("mining-status");
const refuelBtn = $("refuel-btn");
const upgradeBtn = $("upgrade-btn");
const logBox = $("log-box");

const toast = $("toast");

function showToast(message, type = "error") {
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => {
        toast.classList.remove("show");
    }, 2500);
}

function addLog(message, level = "info") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${level}`;
    const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    entry.innerHTML = `<span class="time">[${time}]</span>${message}`;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
}

function updateUI() {
    if (!player) return;

    playerNameEl.textContent = player.username;

    const orePct = (player.ore / player.max_cargo) * 100;
    oreBar.style.width = orePct + "%";
    oreValue.textContent = `${player.ore} / ${player.max_cargo}`;

    const fuelPct = (player.fuel / 100) * 100;
    fuelBar.style.width = fuelPct + "%";
    fuelValue.textContent = `${player.fuel} / 100`;

    const oxyPct = (player.oxygen / player.max_oxygen) * 100;
    oxygenBar.style.width = oxyPct + "%";
    oxygenValue.textContent = `${player.oxygen} / ${player.max_oxygen}`;

    cargoValue.textContent = player.max_cargo;

    if (player.mining) {
        miningBtn.textContent = "■ 停止挖矿";
        miningBtn.classList.add("active");
        miningStatus.textContent = "⛏ 正在开采矿石...";
        miningStatus.classList.add("mining");
    } else {
        miningBtn.textContent = "▶ 开始挖矿";
        miningBtn.classList.remove("active");
        miningStatus.textContent = player.fuel <= 0 ? "⚠ 燃料耗尽！" : "系统待机中...";
        miningStatus.classList.remove("mining");
    }

    const upgradeCost = player.max_cargo;
    upgradeBtn.textContent = `${upgradeCost}矿石`;
    upgradeBtn.disabled = player.ore < upgradeCost;

    refuelBtn.disabled = player.ore < 10 || player.fuel >= 100;
}

function connect() {
    connectionDot.className = "status-dot connecting";

    try {
        ws = new WebSocket(WS_URL);
    } catch (e) {
        console.error("WebSocket create error:", e);
        scheduleReconnect();
        return;
    }

    ws.onopen = () => {
        console.log("WebSocket connected");
        connectionDot.className = "status-dot connected";
        addLog("连接到太空站成功", "success");

        if (player && player.username) {
            send({ type: "login", username: player.username });
        }
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleMessage(data);
        } catch (e) {
            console.error("Parse error:", e);
        }
    };

    ws.onclose = () => {
        console.log("WebSocket closed");
        connectionDot.className = "status-dot";
        addLog("与太空站断开连接", "error");
        scheduleReconnect();
    };

    ws.onerror = (e) => {
        console.error("WebSocket error:", e);
    };
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        if (player) {
            addLog("正在重新连接...", "warning");
            connect();
        }
    }, 3000);
}

function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(data));
        return true;
    }
    return false;
}

function handleMessage(data) {
    switch (data.type) {
        case "state":
            player = data.player;
            updateUI();
            break;
        case "error":
            showToast(data.message);
            addLog(data.message, "error");
            break;
    }
}

function login() {
    const username = usernameInput.value.trim();
    if (!username) {
        showToast("请输入宇航员代号");
        return;
    }

    player = { username };
    connect();

    loginScreen.classList.remove("active");
    gameScreen.classList.add("active");

    addLog(`宇航员 ${username} 进入船舱`, "info");
}

function toggleMining() {
    if (!player) return;
    if (player.mining) {
        send({ type: "stop_mining" });
    } else {
        if (player.fuel <= 0) {
            showToast("燃料不足，无法挖矿！");
            return;
        }
        send({ type: "start_mining" });
    }
}

function refuel() {
    if (!player) return;
    send({ type: "refuel" });
}

function upgradeCargo() {
    if (!player) return;
    send({ type: "upgrade_cargo" });
}

loginBtn.addEventListener("click", login);
usernameInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") login();
});

miningBtn.addEventListener("click", toggleMining);
refuelBtn.addEventListener("click", refuel);
upgradeBtn.addEventListener("click", upgradeCargo);

document.addEventListener("DOMContentLoaded", () => {
    usernameInput.focus();
});
