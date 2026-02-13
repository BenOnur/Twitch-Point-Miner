module.exports = {
    apps: [{
        name: "twitch-miner",
        script: "./run.py",
        interpreter: "./venv/bin/python3",
        autorestart: true,
        watch: false,
        max_memory_restart: "500M",
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }]
};
