module.exports = {
    apps: [{
        name: "twitch-miner",
        script: "./run.py",
        interpreter: "python3",
        autorestart: true,
        watch: false,
        max_memory_restart: '500M',
        env: {
            PYTHONUNBUFFERED: "1",
      # Environment variables will be loaded from .env file by python- dotenv or os
    }
  }]
}
