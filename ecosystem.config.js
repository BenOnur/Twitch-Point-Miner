module.exports = {
    apps: [{
        name: "twitch-miner",
        script: "./run.py",
        interpreter: "./venv/bin/python3",
        autorestart: true,
        watch: false,
        ignore_watch: ["node_modules", "logs", "analytics", "*.json"],
        exp_backoff_restart_delay: 100,
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }]
};
