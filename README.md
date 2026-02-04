# Le Mans Ultimate Times Bot

A timing system for Le Mans Ultimate (LMU) that records lap times with a Discord bot to display the leaderboard.

## Project Structure

```
LMU Times Bot/
├── Backend/        # API server for storing and retrieving timing data
├── Discord Bot/    # Discord bot for interacting with timing data
└── Recorder/       # Application that captures lap times from LMU
```

## Requirements

- Python 3.10 or higher
- A Discord Developer Application ([create one here](https://discord.com/developers/applications))
- A Linux server (for hosting the Backend and Discord Bot)
- A Windows Instance (Computer, Virtual Machine, etc)

## Setup

### 1. Discord Application Setup

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** and give it a name
3. Navigate to **Bot** in the sidebar
4. Click **Reset Token** and copy your bot token (save it for later)
5. Navigate to **OAuth2 > URL Generator**
6. Select scopes: `bot`, `applications.commands`
7. Select bot permissions: `Send Messages`, `Embed Links`, `Attach Files`
8. Copy the generated URL and use it to invite the bot to your server

### 2. Server Setup

Clone the repository and run the setup script:

```bash
git clone https://github.com/AdamTuraj/LMU-Times-Bot.git
cd "LMU-Times-Bot"
chmod +x setup.sh
./setup.sh
```

The setup script will:

- Create virtual environments for the Backend and Discord Bot
- Install required dependencies
- Prompt you for configuration values (Discord token, API keys, etc.)

### 3. Recorder Executable Generation

To build the Windows client-side recorder executable on a Windows machine:

1. Place an ICO icon file named `icon.ico` in the project root directory
2. Open PowerShell or Command Prompt in the project directory
3. Run the build script:

```powershell
.\build.bat
```

After entering the required configuration data, the recorder executable will be generated in the `Recorder\dist` directory.

### 4. Systemd Services

Create systemd service files to run the Backend and Discord Bot in the background.

**Backend Service:**

```bash
sudo nano /etc/systemd/system/lmu-backend.service
```

```ini
[Unit]
Description=LMU Times Bot Backend API
After=network.target

[Service]
Type=simple
User=<username>
WorkingDirectory=/home/<username>/LMU-Times-Bot/Backend

EnvironmentFile=/home/<username>/LMU-Times-Bot/Backend/.env

ExecStart=/home/<username>/LMU-Times-Bot/Backend/.venv/bin/uvicorn main:app --host ${HOST} --port ${PORT}

Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Discord Bot Service:**

```bash
sudo nano /etc/systemd/system/lmu-discord-bot.service
```

```ini
[Unit]
Description=LMU Times Discord Bot
After=network.target lmu-backend.service

[Service]
Type=simple
User=<username>
WorkingDirectory=/home/<username>/LMU-Times-Bot/Discord_Bot
ExecStart=/home/<username>/LMU-Times-Bot/Discord_Bot/.venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start the services:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable lmu-backend lmu-discord-bot
sudo systemctl start lmu-backend lmu-discord-bot
```

**Check service status:**

```bash
sudo systemctl status lmu-backend
sudo systemctl status lmu-discord-bot
```

**Check logs:**

```bash
sudo journalctl -u lmu-backend.service
sudo journalctl -u lmu-discord-bot.service
```

### 5. Firewall Configuration

Open the required port for the Backend API:

```bash
# Using UFW (Ubuntu/Debian)
sudo ufw allow 8000/tcp
sudo ufw reload

# Using firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
