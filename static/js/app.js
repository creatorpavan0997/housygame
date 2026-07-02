let socket = null;
let reconnectAttempts = 0;
let voiceEnabled = true;
let soundEnabled = true;

// Client Game State
let calledHistory = new Set();
let playerTicket = [];
let markedTicketNumbers = new Set();
let timerInterval = null;
let timerSecondsMax = 6;
let timerCurrent = 0;

// Initialize sound toggles from localStorage
if (localStorage.getItem("voiceEnabled") !== null) {
    voiceEnabled = localStorage.getItem("voiceEnabled") === "true";
}
if (localStorage.getItem("soundEnabled") !== null) {
    soundEnabled = localStorage.getItem("soundEnabled") === "true";
}

// UI Elements caching
const elements = {
    boardGrid: document.getElementById("board-grid"),
    ticketGrid: document.getElementById("ticket-grid"),
    currentNumber: document.getElementById("current-number-display"),
    historyItems: document.getElementById("history-items"),
    timerContainer: document.getElementById("timer-container"),
    timerBar: document.getElementById("timer-bar"),
    timerSeconds: document.getElementById("timer-seconds"),
    leaderboard: document.getElementById("leaderboard-list"),
    gameFeed: document.getElementById("game-feed"),
    gameOverOverlay: document.getElementById("game-over-overlay"),
    gameWinnerAnnounce: document.getElementById("game-winner-announce"),
    finalScoreboard: document.getElementById("final-scoreboard-list"),
    voiceToggle: document.getElementById("voice-toggle-btn"),
    soundToggle: document.getElementById("sound-toggle-btn"),
    ticketMarkedCount: document.getElementById("ticket-marked-count"),
    nextDrawBtn: document.getElementById("next-draw-btn")
};

// Start Up Orchestrations
function init() {
    renderBoard();
    updateToggleButtons();
    connectWebSocket();
}

// 1-90 Number Board rendering
function renderBoard() {
    if (!elements.boardGrid) return;
    elements.boardGrid.innerHTML = "";
    for (let i = 1; i <= 90; i++) {
        const cell = document.createElement("div");
        cell.className = "board-cell";
        cell.id = `board-cell-${i}`;
        cell.innerText = i;
        elements.boardGrid.appendChild(cell);
    }
}

// Render ticket grid (3x9)
function renderTicket(grid) {
    if (!elements.ticketGrid) return;
    playerTicket = grid;
    elements.ticketGrid.innerHTML = "";

    grid.forEach((row, rowIndex) => {
        const rowDiv = document.createElement("div");
        rowDiv.className = "ticket-row";
        
        row.forEach((cell, colIndex) => {
            const cellDiv = document.createElement("div");
            
            if (cell === 0) {
                cellDiv.className = "ticket-cell empty";
            } else {
                cellDiv.className = "ticket-cell number";
                cellDiv.innerText = cell;
                cellDiv.id = `ticket-cell-${cell}`;
                
                // Click handlers
                cellDiv.onclick = () => toggleMarkNumber(cell);
                
                // If reconnecting, restore marked cell indicators
                if (markedTicketNumbers.has(cell)) {
                    cellDiv.classList.add("marked");
                }
            }
            rowDiv.appendChild(cellDiv);
        });
        
        elements.ticketGrid.appendChild(rowDiv);
    });
    updateMarkedCount();
}

function toggleMarkNumber(num) {
    // Only allow marking if the number was actually called by the server!
    if (!calledHistory.has(num)) {
        addFeedMessage("System", `You cannot mark ${num} yet - it hasn't been called!`, "warning");
        if (soundEnabled) AudioSynth.playError();
        return;
    }

    const cellDiv = document.getElementById(`ticket-cell-${num}`);
    if (markedTicketNumbers.has(num)) {
        markedTicketNumbers.delete(num);
        if (cellDiv) cellDiv.classList.remove("marked");
    } else {
        markedTicketNumbers.add(num);
        if (cellDiv) cellDiv.classList.add("marked");
        if (soundEnabled) AudioSynth.playTick();
    }
    updateMarkedCount();
}

function updateMarkedCount() {
    if (elements.ticketMarkedCount) {
        elements.ticketMarkedCount.innerText = `${markedTicketNumbers.size} / 15 Marked`;
    }
}

// Websocket logic
function connectWebSocket() {
    const wsScheme = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${wsScheme}://${window.location.host}/ws/room/${roomId}/`;
    
    socket = new WebSocket(wsUrl);

    socket.onopen = function() {
        console.log("WebSocket connection established!");
        reconnectAttempts = 0;
    };

    socket.onmessage = function(e) {
        const data = JSON.parse(e.data);
        
        switch (data.type) {
            case "game_started":
                calledHistory.clear();
                markedTicketNumbers.clear();
                renderTicket(data.ticket);
                addFeedMessage("System", "The game has started! Good luck!", "info");
                break;
                
            case "number_drawn":
                handleNumberDrawn(data.number, data.history, data.timer);
                break;
                
            case "claim_result":
                handleClaimResult(data);
                break;
                
            case "game_over":
                handleGameOver(data);
                break;
                
            case "sync_state":
                handleSyncState(data);
                break;
                
            case "game_status":
                addFeedMessage("Host", data.message, data.is_paused ? "warning" : "success");
                if (data.is_paused) {
                    stopClientTimer();
                }
                break;
                
            case "player_list":
                // Updates list, if host panel is active we can update kick hooks too
                break;
                
            case "removed":
                alert(data.message);
                window.location.href = "/";
                break;
        }
    };

    socket.onclose = function() {
        console.log("WebSocket socket disconnected.");
        stopClientTimer();
        if (reconnectAttempts < 5) {
            reconnectAttempts++;
            setTimeout(connectWebSocket, 3000);
        }
    };
}

// Event Actions
function handleNumberDrawn(num, history, timerVal) {
    calledHistory = new Set(history);
    timerSecondsMax = timerVal;
    
    // Highlight board number
    const boardCell = document.getElementById(`board-cell-${num}`);
    if (boardCell) {
        boardCell.classList.add("called");
    }
    
    // Announce Display
    if (elements.currentNumber) {
        elements.currentNumber.innerText = num;
        elements.currentNumber.classList.remove("animate-zoom-in");
        void elements.currentNumber.offsetWidth; // Reflow reset animation
        elements.currentNumber.classList.add("animate-zoom-in");
    }
    
    // Announce Voice & Sound FX
    if (soundEnabled) AudioSynth.playTick();
    speakNumber(num);
    
    // History
    if (elements.historyItems) {
        // Last 5 numbers
        const lastFive = history.slice(-5).reverse();
        elements.historyItems.innerText = lastFive.join(", ");
    }
    
    // Start countdown bar
    startClientTimer();
    addFeedMessage("Game", `Number drawn: ${num}`, "info");
}

function handleClaimResult(data) {
    const isApproved = data.status === "APPROVED";
    
    // Play sound FX
    if (soundEnabled) {
        if (isApproved) {
            AudioSynth.playSuccess();
        } else {
            AudioSynth.playError();
        }
    }
    
    // Announce log
    addFeedMessage("Winner Info", data.message, isApproved ? "success" : "danger");
    
    // Update Scoreboard list
    updateLeaderboard(data.leaderboard);
    
    // If approved, disable claim buttons of this challenge category
    if (isApproved) {
        const btn = document.getElementById(`claim-${data.pattern}`);
        if (btn) {
            btn.classList.remove("btn-outline-warning");
            btn.classList.add("btn-success", "disabled");
            btn.removeAttribute("onclick");
        }
        
        // Burst Confetti if current user won!
        const playerSessionName = document.querySelector(".nav-link.text-white")?.innerText.trim();
        if (playerSessionName && playerSessionName === data.player_name.trim()) {
            triggerConfettiBurst();
        }
    }
}

function handleGameOver(data) {
    stopClientTimer();
    if (elements.gameOverOverlay) {
        // Build winners list
        let winnerText = "Winners: ";
        if (data.winners.length > 0) {
            winnerText += data.winners.map(w => `${w.player__name} (${w.pattern_name.replace('_', ' ').toUpperCase()})`).join(", ");
        } else {
            winnerText += "No winners registered.";
        }
        
        elements.gameWinnerAnnounce.innerText = winnerText;
        
        // Final Scoreboard
        elements.finalScoreboard.innerHTML = "";
        data.final_leaderboard.forEach((item, index) => {
            const row = document.createElement("div");
            row.className = "d-flex justify-content-between p-2 border-bottom border-light border-opacity-10 text-white";
            row.innerHTML = `<span>${index + 1}. ${item.player_name}</span><span class="fw-bold">${item.points} pts</span>`;
            elements.finalScoreboard.appendChild(row);
        });
        
        elements.gameOverOverlay.style.display = "flex";
        if (soundEnabled) AudioSynth.playSuccess();
        triggerConfettiBurst(3); // Confetti!
    }
}

function handleSyncState(data) {
    calledHistory = new Set(data.called_history);
    
    // Fill board highlights
    data.called_history.forEach(num => {
        const cell = document.getElementById(`board-cell-${num}`);
        if (cell) cell.classList.add("called");
    });
    
    // Render ticket
    renderTicket(data.ticket);
    
    // Update scoreboard
    updateLeaderboard(data.leaderboard);
    
    // Restore current draw
    if (data.last_number) {
        elements.currentNumber.innerText = data.last_number;
        const lastFive = data.called_history.slice(-5).reverse();
        elements.historyItems.innerText = lastFive.join(", ");
    }
}

// Client Countdown display
function startClientTimer() {
    stopClientTimer();
    if (!elements.timerContainer) return;
    
    elements.timerContainer.style.display = "block";
    timerCurrent = timerSecondsMax;
    elements.timerBar.style.width = "100%";
    elements.timerSeconds.innerText = `${timerCurrent}s`;
    
    const intervalTickMs = 100;
    const ticksTotal = (timerSecondsMax * 1000) / intervalTickMs;
    let tickCount = 0;
    
    timerInterval = setInterval(() => {
        tickCount++;
        const percentLeft = 100 - (tickCount / ticksTotal) * 100;
        elements.timerBar.style.width = `${percentLeft}%`;
        
        const secondsLeft = Math.ceil(timerSecondsMax - (tickCount * intervalTickMs) / 1000);
        elements.timerSeconds.innerText = `${secondsLeft}s`;
        
        if (tickCount >= ticksTotal) {
            stopClientTimer();
        }
    }, intervalTickMs);
}

function stopClientTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
    if (elements.timerContainer) {
        elements.timerContainer.style.display = "none";
    }
}

// Claim challenge click
function claimPrize(pattern) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
            action: "claim_prize",
            pattern: pattern
        }));
        addFeedMessage("Claim Info", `Submitted claim for ${pattern.replace("_", " ").title()}...`, "warning");
    }
}

// Host controls calls
function sendPause() {
    if (socket) socket.send(JSON.stringify({ action: "pause_game" }));
}

function sendResume() {
    if (socket) socket.send(JSON.stringify({ action: "resume_game" }));
}

function sendNextDraw() {
    if (socket) socket.send(JSON.stringify({ action: "draw_number" }));
}

// Speak announcements
function speakNumber(num) {
    if (!voiceEnabled || !('speechSynthesis' in window)) return;
    
    window.speechSynthesis.cancel();
    
    let text = `Number ${num}. `;
    if (num < 10) {
        text += `Single number ${num}.`;
    } else {
        const digits = num.toString().split('');
        // Add typical RabbitHouse nicknames for flair if wanted, or just standard numbers
        text += `${digits[0]} and ${digits[1]}. ${num}.`;
    }
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.85;
    window.speechSynthesis.speak(utterance);
}

// Sound Toggles
function toggleVoice() {
    voiceEnabled = !voiceEnabled;
    localStorage.setItem("voiceEnabled", voiceEnabled);
    updateToggleButtons();
}

function toggleSound() {
    soundEnabled = !soundEnabled;
    localStorage.setItem("soundEnabled", soundEnabled);
    updateToggleButtons();
}

function updateToggleButtons() {
    if (elements.voiceToggle) {
        elements.voiceToggle.innerHTML = voiceEnabled ? 
            '<i class="fa-solid fa-volume-high text-info"></i>' : 
            '<i class="fa-solid fa-volume-xmark text-white-50"></i>';
    }
    if (elements.soundToggle) {
        elements.soundToggle.innerHTML = soundEnabled ? 
            '<i class="fa-solid fa-music text-info"></i>' : 
            '<i class="fa-solid fa-music-slash text-white-50"></i>';
    }
}

// Helper to append logs
function addFeedMessage(sender, message, type) {
    if (!elements.gameFeed) return;
    
    const log = document.createElement("div");
    log.className = `small text-${type} mb-1`;
    log.innerHTML = `<strong>[${sender}]</strong> ${message}`;
    
    elements.gameFeed.appendChild(log);
    elements.gameFeed.scrollTop = elements.gameFeed.scrollHeight;
}

function updateLeaderboard(list) {
    if (!elements.leaderboard) return;
    elements.leaderboard.innerHTML = "";
    
    if (list.length === 0) {
        elements.leaderboard.innerHTML = '<div class="text-white-50 small text-center py-3">No scores yet.</div>';
        return;
    }
    
    list.forEach((item, index) => {
        const row = document.createElement("div");
        row.className = "d-flex justify-content-between p-2 rounded-3 glass-player-item text-white small";
        row.innerHTML = `<span>${index + 1}. ${item.player_name}</span><span class="fw-bold">${item.points} pts</span>`;
        elements.leaderboard.appendChild(row);
    });
}

// Confetti burst using canvas-confetti
function triggerConfettiBurst(iterations = 1) {
    let count = 0;
    const interval = setInterval(() => {
        confetti({
            particleCount: 80,
            spread: 60,
            origin: { y: 0.6 }
        });
        count++;
        if (count >= iterations) {
            clearInterval(interval);
        }
    }, 400);
}

// Extension to string title conversion
String.prototype.title = function() {
    return this.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

// Start
window.onload = init;
