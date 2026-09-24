# Le Mans Ultimate Times Bot

A timing system for Le Mans Ultimate (LMU) that records lap times with a Discord bot to display the leaderboard.

## Project Structure

```
LMU Times Bot/
├── Backend/        # API server for storing and retrieving timing data
├── Discord_Bot/    # Discord bot for interacting with timing data
├── Recorder/       # Application that captures lap times from LMU
└── scripts/        # Build and setup scripts
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
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:

- Create virtual environments for the Backend and Discord Bot
- Install required dependencies
- Prompt you for configuration values (Discord token, API keys, etc.)

### 3. Recorder Executable Generation

To build the Windows client-side recorder executable on a Windows machine:

1. Place an ICO icon file named `icon.ico` in the project root directory
   - **Note:** For best results, use a multi-size .ico file with sizes: 16, 24, 32, 48, 64, 128, 256. This can be done online with websites such as [aconvert](https://www.aconvert.com/icon/)
2. Open PowerShell or Command Prompt in the project directory
3. Run the build script:

```powershell
.\scripts\build.bat
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

The backend also writes a rotating log file at `Backend/logs/backend.log` by default.
Set `BACKEND_LOG_FILE` or `LOG_FILE` in `Backend/.env` to use a different path.

### 5. Nginx Reverse Proxy (optional)

Use [scripts/nginx.conf.example](scripts/nginx.conf.example) to serve the backend on a public domain. The following commands assume Debian/Ubuntu with nginx, Certbot, and its nginx plugin installed. Point your domain's DNS records to this server first.

Set `HOST=127.0.0.1` and `PORT=8000` in `Backend/.env`, then restart the backend:

```bash
sudo systemctl restart lmu-backend
sudo cp scripts/nginx.conf.example /etc/nginx/sites-available/lmu-times-bot
sudo nano /etc/nginx/sites-available/lmu-times-bot
```

Replace `api.example.com` with your domain. If you changed the backend port, update `proxy_pass` to match. Enable the site and validate the configuration before reloading:

```bash
sudo ln -s /etc/nginx/sites-available/lmu-times-bot /etc/nginx/sites-enabled/lmu-times-bot
sudo nginx -t && sudo systemctl reload nginx
```

Allow inbound TCP ports **80 and 443** in your firewall and hosting provider's network rules. Keep port 8000 private when using nginx. Enable HTTPS and HTTP-to-HTTPS redirection:

```bash
sudo certbot --nginx -d api.example.com --redirect
sudo certbot renew --dry-run
```

Use your actual domain in the Certbot command. Set `DISCORD_CALLBACK_URL=https://api.example.com/discord/callback` in `Backend/.env` and register that exact URL in your Discord application's OAuth2 redirects. Restart `lmu-backend` after changing its configuration. Use `https://api.example.com` as the Recorder's backend API URL; keep `APPLICATION_CALLBACK` as the Recorder's local callback address.

Verify the public endpoint:

```bash
curl --fail https://api.example.com/version
```

See the [nginx proxy documentation](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) and [Certbot nginx instructions](https://eff-certbot.readthedocs.io/en/stable/using.html#nginx) for details.

### 6. Firewall Configuration (direct backend access)

If you are exposing the Backend API directly without nginx, open its port:

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
