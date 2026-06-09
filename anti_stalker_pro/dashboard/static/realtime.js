/**
 * WebSocket real-time client for the Anti-Stalker Dashboard.
 * Connects to /ws/realtime, handles incoming events, updates the DOM,
 * and reconnects on disconnect with exponential backoff.
 */

class RealtimeClient {
    constructor() {
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.baseDelay = 1000;
        this.maxDelay = 30000;
        this.listeners = {};
        this.connected = false;
    }

    /**
     * Connect to the WebSocket server.
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws/realtime`;

        try {
            this.ws = new WebSocket(url);
            this._setupEventHandlers();
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this._scheduleReconnect();
        }
    }

    /**
     * Set up WebSocket event handlers.
     */
    _setupEventHandlers() {
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.connected = true;
            this.reconnectAttempts = 0;
            this._emit('connected', {});
            this._startPingInterval();
        };

        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this._handleMessage(message);
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket disconnected:', event.code, event.reason);
            this.connected = false;
            this._stopPingInterval();
            this._emit('disconnected', { code: event.code });
            this._scheduleReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this._emit('error', { error });
        };
    }

    /**
     * Handle an incoming WebSocket message and dispatch to listeners.
     * @param {Object} message - Parsed message with type and data fields
     */
    _handleMessage(message) {
        const { type, data, timestamp } = message;

        switch (type) {
            case 'story_view':
                this._updateStoryViewers(data);
                break;
            case 'online_change':
                this._updateOnlineStatus(data);
                break;
            case 'bio_click':
                this._updateBioClicks(data);
                break;
            case 'alert':
                this._updateAlerts(data);
                break;
            case 'pong':
            case 'heartbeat':
                break;
            case 'connected':
                console.log('Server confirmed connection');
                break;
            default:
                console.log('Unknown event type:', type);
        }

        this._emit(type, data);
    }

    /**
     * Update DOM with new story viewer data.
     * @param {Object} data - Story view event data
     */
    _updateStoryViewers(data) {
        const container = document.getElementById('realtime-events');
        if (!container) return;

        const item = document.createElement('div');
        item.className = 'p-3 bg-gray-800 rounded-lg border border-indigo-500/30 animate-pulse-once';
        item.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-indigo-500"></span>
                <span class="text-sm text-gray-300">
                    <strong class="text-indigo-400">${data.username || data.user_id || 'Unknown'}</strong>
                    viewed your story
                </span>
                <span class="ml-auto text-xs text-gray-500">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        container.prepend(item);
        this._trimEvents(container);
    }

    /**
     * Update DOM with online status change.
     * @param {Object} data - Online status event data
     */
    _updateOnlineStatus(data) {
        const container = document.getElementById('realtime-events');
        if (!container) return;

        const status = data.is_online ? 'came online' : 'went offline';
        const color = data.is_online ? 'green' : 'gray';

        const item = document.createElement('div');
        item.className = 'p-3 bg-gray-800 rounded-lg border border-' + color + '-500/30';
        item.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-${color}-500"></span>
                <span class="text-sm text-gray-300">
                    <strong class="text-${color}-400">${data.username || data.user_id || 'Unknown'}</strong>
                    ${status}
                </span>
                <span class="ml-auto text-xs text-gray-500">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        container.prepend(item);
        this._trimEvents(container);
    }

    /**
     * Update DOM with bio link click event.
     * @param {Object} data - Bio link click event data
     */
    _updateBioClicks(data) {
        const container = document.getElementById('realtime-events');
        if (!container) return;

        const item = document.createElement('div');
        item.className = 'p-3 bg-gray-800 rounded-lg border border-yellow-500/30';
        item.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-yellow-500"></span>
                <span class="text-sm text-gray-300">
                    Bio link clicked from <strong class="text-yellow-400">${data.country || 'Unknown'}</strong>
                    (${data.device || 'Unknown device'})
                </span>
                <span class="ml-auto text-xs text-gray-500">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        container.prepend(item);
        this._trimEvents(container);
    }

    /**
     * Update DOM with alert event.
     * @param {Object} data - Alert event data
     */
    _updateAlerts(data) {
        const container = document.getElementById('realtime-events');
        if (!container) return;

        const item = document.createElement('div');
        item.className = 'p-3 bg-gray-800 rounded-lg border border-red-500/30';
        item.innerHTML = `
            <div class="flex items-center gap-2">
                <span class="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                <span class="text-sm text-gray-300">
                    <strong class="text-red-400">ALERT:</strong> ${data.message || 'New alert triggered'}
                </span>
                <span class="ml-auto text-xs text-gray-500">${new Date().toLocaleTimeString()}</span>
            </div>
        `;
        container.prepend(item);
        this._trimEvents(container);

        const alertCount = document.getElementById('alert-count');
        if (alertCount) {
            alertCount.textContent = parseInt(alertCount.textContent || '0') + 1;
        }
    }

    /**
     * Trim events container to keep only the last 50 entries.
     * @param {HTMLElement} container - Events container element
     */
    _trimEvents(container) {
        while (container.children.length > 50) {
            container.removeChild(container.lastChild);
        }
    }

    /**
     * Schedule a reconnection attempt with exponential backoff.
     */
    _scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnection attempts reached');
            this._emit('max_reconnect', {});
            return;
        }

        const delay = Math.min(
            this.baseDelay * Math.pow(2, this.reconnectAttempts),
            this.maxDelay
        );
        this.reconnectAttempts++;

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
        setTimeout(() => this.connect(), delay);
    }

    /**
     * Start periodic ping to keep connection alive.
     */
    _startPingInterval() {
        this._pingInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send('ping');
            }
        }, 25000);
    }

    /**
     * Stop the ping interval.
     */
    _stopPingInterval() {
        if (this._pingInterval) {
            clearInterval(this._pingInterval);
            this._pingInterval = null;
        }
    }

    /**
     * Register an event listener.
     * @param {string} event - Event type to listen for
     * @param {Function} callback - Callback function
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    /**
     * Emit an event to registered listeners.
     * @param {string} event - Event type
     * @param {Object} data - Event data
     */
    _emit(event, data) {
        const handlers = this.listeners[event] || [];
        handlers.forEach(handler => {
            try {
                handler(data);
            } catch (error) {
                console.error(`Error in ${event} handler:`, error);
            }
        });
    }

    /**
     * Disconnect the WebSocket client.
     */
    disconnect() {
        this._stopPingInterval();
        if (this.ws) {
            this.ws.close(1000, 'Client disconnect');
            this.ws = null;
        }
        this.connected = false;
    }
}

// Global instance
const realtimeClient = new RealtimeClient();
