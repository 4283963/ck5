const WS_URL = "ws://localhost:8765";

let ws = null;
let player = null;
let market = null;
let reconnectTimer = null;
let countdownTimer = null;

const $ = (id) => document.getElementById(id);

const loginScreen = $("login-screen");
const gameScreen = $("game-screen");
const loginBtn = $("login-btn");
const usernameInput = $("username");
const playerNameEl = $("player-name");
const connectionDot = $("connection-dot");
const creditsValue = $("credits-value");

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

const marketOrdersEl = $("market-orders");
const marketCountdownEl = $("market-countdown");
const marketHintEl = $("market-hint");

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
    creditsValue.textContent = player.credits;

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

function formatTime(seconds) {
    if (seconds <= 0) return "00:00";
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function updateCountdown() {
    if (!market || !market.expires_at) {
        marketCountdownEl.textContent = "--:--";
        return;
    }
    const now = Math.floor(Date.now() / 1000);
    const remaining = market.expires_at - now;
    marketCountdownEl.textContent = formatTime(remaining);

    if (remaining <= 0) {
        marketHintEl.textContent = "商人已离开，等待下一位...";
    }
}

function getItemName(item) {
    const names = {
        ore: "矿石",
        fuel: "燃料",
    };
    return names[item] || item;
}

function getOrderAction(order_type) {
    return order_type === "buy" ? "收购" : "出售";
}

function renderMarketOrders() {
    if (!market || !market.orders || market.orders.length === 0) {
        marketOrdersEl.innerHTML = "";
        marketHintEl.textContent = "商人正在赶来...";
        return;
    }

    const now = Math.floor(Date.now() / 1000);
    if (market.expires_at <= now) {
        marketOrdersEl.innerHTML = "";
        marketHintEl.textContent = "商人已离开，等待下一位...";
        return;
    }

    marketHintEl.textContent = "🪐 神秘商人到访！限时交易";

    marketOrdersEl.innerHTML = market.orders.map(order => {
        const isBuy = order.order_type === "buy";
        const itemName = getItemName(order.item);
        const actionLabel = isBuy ? "卖给商人" : "购买";
        const btnClass = isBuy ? "buy" : "sell";
        const orderClass = isBuy ? "buy" : "sell";
        const typeLabel = isBuy ? "商人收购" : "商人出售";
        const typeClass = isBuy ? "order-type-buy" : "order-type-sell";

        let canTrade = true;
        if (isBuy && player && player.ore < 1) canTrade = false;
        if (!isBuy && player && player.credits < order.price_per_unit) canTrade = false;
        if (!isBuy && player && order.item === "fuel" && player.fuel >= 100) canTrade = false;
        if (order.remaining <= 0) canTrade = false;

        return `
            <div class="market-order ${orderClass}">
                <div class="order-header">
                    <span class="${typeClass}">${typeLabel}</span>
                    <span class="order-item">${itemName}</span>
                </div>
                <div class="order-details">
                    <span class="order-price">💰 ${order.price_per_unit} / 个</span>
                    <span class="order-remaining">剩余: ${order.remaining}/${order.quantity}</span>
                </div>
                <div class="order-actions">
                    <button class="trade-btn ${btnClass}" data-order-id="${order.id}" data-amount="1" ${canTrade ? "" : "disabled"}>
                        ${actionLabel} x1
                    </button>
                    <button class="trade-btn ${btnClass}" data-order-id="${order.id}" data-amount="10" ${canTrade ? "" : "disabled"}>
                        ${actionLabel} x10
                    </button>
                    <button class="trade-btn ${btnClass}" data-order-id="${order.id}" data-amount="max" ${canTrade ? "" : "disabled"}>
                        全部
                    </button>
                </div>
            </div>
        `;
    }).join("");

    marketOrdersEl.querySelectorAll(".trade-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const orderId = parseInt(btn.dataset.orderId);
            const amount = btn.dataset.amount;
            executeTrade(orderId, amount);
        });
    });
}

function executeTrade(orderId, amountStr) {
    if (!player) return;

    let amount = 1;
    if (amountStr === "max") {
        amount = 999;
    } else {
        amount = parseInt(amountStr);
    }

    send({
        type: "trade",
        order_id: orderId,
        amount: amount,
    });
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
            renderMarketOrders();
            break;
        case "market":
            market = data.market;
            renderMarketOrders();
            updateCountdown();
            if (data.market.orders && data.market.orders.length > 0) {
                addLog("👽 神秘黑市商人到访！限时交易开启", "warning");
            }
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

    if (!countdownTimer) {
        countdownTimer = setInterval(updateCountdown, 1000);
    }
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
