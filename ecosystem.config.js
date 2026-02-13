module.exports = {
    apps: [{
        name: "twitch-miner",
        script: "run.py",
        interpreter: "./venv/bin/python3",
        cwd: "/home/KULLANICI_ADIN/Twitch-Channel-Points-Miner-v2",
        autorestart: true,
        max_restarts: 10,
        restart_delay: 30000,
        watch: false,
        env: {
            PYTHONUNBUFFERED: "1"
        }
    }]
};
