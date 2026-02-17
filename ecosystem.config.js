module.exports = {
    apps: [{
        name: "twitch-miner",
        script: "./run.py",
        interpreter: "./venv/bin/python3",
        autorestart: true,
        watch: false,
        ignore_watch: ["node_modules", "logs", "analytics", "*.json", "*.log", "__pycache__", "venv"],
        max_memory_restart: "1024M",
        exp_backoff_restart_delay: 100,
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }]
};
