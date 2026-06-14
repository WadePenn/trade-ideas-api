# Trade Ideas Panel

> AI-powered options scanning panel with FastAPI backend, IBKR integration, and 0DTE credit spread detection.

---

## ⬇️ One-Click Install

**Click the button below to download the installer — then double-click it. That's it.**

[![Install Trade Ideas Panel](https://img.shields.io/badge/⬇️%20DOWNLOAD%20INSTALLER-Click%20Here%20to%20Install-brightgreen?style=for-the-badge&logo=windows)](https://github.com/WadePenn/trade-ideas-api/raw/master/install.bat)

> **What the installer does automatically:**
> - Installs Python 3.11 if missing (via winget)
> - Installs Git if missing (via winget)
> - Clones this repository to `%USERPROFILE%\trade-ideas-api`
> - Creates a Python virtual environment and installs all packages
> - Creates a **"Trade Ideas Panel"** shortcut on your Desktop

**Requirements:** Windows 10 or 11 with an internet connection. No Python or Git needed beforehand.

---

## 🚀 Quick Start (after install)

1. Double-click **Trade Ideas Panel** on your Desktop
2. TWS / IBKR Gateway must be running on port 7497
3. The FastAPI backend starts automatically — the panel opens on top

---

## 🧠 Features

### Strategy Buttons
| Button | What it does |
|---|---|
| Auto (Best Fit) | Scans all strategies and picks the highest-conviction setup |
| Credit Spread | Sell-side vertical credit spreads |
| Debit Spread | Buy-side vertical debit spreads |
| Iron Condor | Neutral range-bound structure |
| Calendar | Time-spread for steady IV environments |
| Sell Premium (0/7 DTE) | Scans 0 DTE and 7 DTE credit trades |
| **0DTE Best Premium** | Best 0DTE credit spread ranked by credit ÷ risk ratio — highlights optimal sell windows |

### 0DTE Window Intelligence
The **0DTE Best Premium** button detects the current time and classifies the session:

| Window | Time (ET) | Status |
|---|---|---|
| Early Premium | 9:45 – 10:15 AM | 🟢 Prime |
| Mid-Morning | 11:00 – 11:30 AM | 🟢 Prime |
| Theta Crush | 1:45 – 2:30 PM | ⭐ Best of day |
| Other market hours | — | 🟡 Off-Peak |
| Outside hours | — | 🔴 Preview mode |

Results are always sorted by **credit collected ÷ max risk** — best trade at the top.

### Automated Daily Schedule
| Time (ET) | Action |
|---|---|
| 6:15 AM | Pre-market IBKR health check |
| 9:45 AM | 🟢 Early Premium window alert |
| 11:00 AM | 🟢 Mid-Morning window alert |
| 1:45 PM | ⭐ Theta Crush alert |
| 4:05 PM | 📊 End-of-day P&L recap prompt |

---

## 🏗️ Project Structure

```
trade-ideas-api/
├── install.bat              ← One-click installer (download & double-click)
├── install.ps1              ← Installer logic (called by install.bat)
├── StartTradeIdeas.bat      ← Launch server + panel
├── requirements.txt         ← All Python dependencies
├── main.py                  ← FastAPI app entry point
├── routers/
│   └── sell_premium.py      ← Sell Premium / 0DTE scan endpoints
└── trade_ideas/
    ├── panel.py             ← Tkinter UI panel
    ├── sell_premium_scanner.py
    └── strategy_engine.py
```

---

## 🔄 Updating

To pull the latest version on any machine that already has it installed, just run the installer again — it will `git pull` and keep your venv intact.

Or from CMD:
```
cd %USERPROFILE%\trade-ideas-api
git pull
venv\Scripts\pip install -r requirements.txt -q
```

---

## 🛠️ Manual Setup (advanced)

If you prefer to set up manually:

```bash
git clone https://github.com/WadePenn/trade-ideas-api.git
cd trade-ideas-api
py -3.11 -m venv venv
venv\Scripts\pip install -r requirements.txt
StartTradeIdeas.bat
```

---

*Built by Wade — Burien, WA*
