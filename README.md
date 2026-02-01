# Le Mans Ultimate Times Bot

A timing system for Le Mans Ultimate (LMU) that records lap times with a Discord to show the leaderboard.

## Project Structure

```
LMU Times Bot/
├── Backend/        # API server for storing and retrieving timing data
├── Discord Bot/    # Discord bot for interacting with timing data
└── Recorder/       # Application that captures lap times from LMU
```

## Components

### Backend
REST API server that handles data storage and retrieval for lap times and session information.

### Discord Bot
A Discord bot that allows users to view and manage their lap times through Discord commands.

### Recorder
Desktop application that connects to Le Mans Ultimate to capture live timing data. Compiled using PyInstaller.

## Setup

Each component has its own dependencies. Install them using:

```bash
pip install -r requirements.txt
```

You can generate a custom EXE after editing the recorder main.py using PyInstaller. Simply run this command:

```bash
pyinstaller --onefile --windowed --icon=icon.ico --name "LMU Times Recorder" main.py
```

## License

Uses the MIT license
