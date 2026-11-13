# AMU-ECSF Counseling Telegram Bot

> **Official confidential counseling bot for AMU-ECSF (Arba Minch University Evangelical Christian Students Fellowship).**

This bot provides a safe and private space where students/seekers can reach out with questions, concerns, and prayer requests anonymously. Counselors receive incoming questions on their feed, select a seeker, and engage in confidential 1-on-1 counseling through the bot.

---

## Key Features

1. **100% Anonymous for Seekers**:
   - The seeker's name, username, phone number, and numeric Telegram ID are **never** revealed to the counselors.
   - Counselors only see an anonymous identifier (e.g. `Anonymous User #1001`).

2. **Counselor Feed & Multiple Counselors**:
   - Multiple counselors can be configured in `.env`.
   - New incoming questions appear on each counselor's feed (and optionally in a shared counselors' Telegram group).
   - Any counselor can click `[Select User & Chat]` to claim that seeker.
   - Atomic claiming prevents two counselors from claiming the same seeker simultaneously.

3. **Confidential Two-Way Communication**:
   - Once a counselor selects a user, regular messages sent by the counselor are forwarded to the seeker labeled as `Counselor:`.
   - Messages sent by the seeker are forwarded to the counselor labeled as `[User #1001]:`.
   - Full support for **Text**, **Voice notes**, **Photos**, **Audio**, and **Documents**.

4. **Clean Session Management**:
   - Seekers can conclude their session anytime using `/close`.
   - Counselors can conclude their session using `/close` or an inline button, leaving both parties with respectful closure notes.
   - Counselors can release a user back to the feed using `/release` if they need another team member to take over.

5. **Self-Contained SQLite Database**:
   - Zero external database setup required.
   - Automatically initializes and manages cases, timestamps, and message history.

---

## Directory Structure

```
AMU-ECSF-Counseling-Bot/
├── .env                  # Your actual configuration (token & counselor IDs)
├── .env.example          # Template configuration
├── .gitignore            # Git exclusion rules
├── requirements.txt      # Python dependencies (python-telegram-bot>=20.7)
├── run.bat               # Windows 1-click launcher
├── main.py               # Application entry point and router
├── config.py             # Configuration loader and branding strings
├── database.py           # SQLite database layer with atomic transactions
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py      # Seeker flows (/start, question submission, live chat)
│   ├── counselor_handlers.py # Counselor flows (feed, claiming, chatting, closing)
│   └── common.py             # Anonymous message forwarding and feed broadcast
└── README.md             # Complete documentation
```

---

## Quick Setup Guide

### 1. Create Your Telegram Bot
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`.
3. Choose a name (e.g., `AMU-ECSF Counseling Bot`) and a username (e.g., `AMU_ECSF_Counseling_bot`).
4. Copy the API Token provided by BotFather.

### 2. Configure `.env`
Open the `.env` file in `c:\Users\hp\Desktop\AMU-ECSF-Counseling-Bot` with Notepad or any text editor:

```env
# 1. Paste your bot token from BotFather:
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# 2. Add counselor Telegram user IDs separated by commas:
COUNSELOR_IDS=123456789,987654321

# 3. (Optional) Counselor team group ID if you want requests posted to a group feed:
COUNSELOR_GROUP_ID=
```

> **How to find your Telegram User ID:**  
> Simply start the bot in Telegram and send the `/myid` command. The bot will immediately reply with your numeric ID.

### 3. Run the Bot
- **Option A (Double-Click)**:
  Double-click `run.bat` in the project folder.

- **Option B (Command Line)**:
  ```powershell
  python main.py
  ```

---

## How It Works in Practice

### Seeker Workflow:
1. Seeker sends `/start`.
2. The bot sends the welcoming message:
   ```
   Welcome

   Welcome to the AMU-ECSF Counseling bot. Our team is ready to counsel you on your journey. We offer a safe and confidential space for you to explore your concerns.

   Here no one can know who you are.

   You are 100% safe.

   Please send your question or concern.

   #Spiritual #Family_Issue #Addiction #Relationships #Anxiety #Friendship #Decision_Making #Academic #Fear #Stress
   ```
3. Seeker types their question or sends a voice message.
4. Bot confirms:
   ```
   #SENT

   Request received.

   Please Wait for the Response Patiently.

   Your Question:
   ...
   ```
5. When a counselor joins, the seeker is notified:
   ```
   A counselor has connected to your session.
   You are now in a private, confidential counseling chat.
   ```
6. Seeker chats freely and confidentially.
7. Seeker or counselor ends the session with `/close`.

---

### Counselor Workflow:
1. Counselor sends `/start` to access the **Counselor Control Panel**.
2. When a seeker submits a question, all counselors receive an alert:
   ```
   [New Seeker in Feed]
   User: Anonymous Seeker #1001
   Message: "I need prayer and counsel regarding my family..."

   [Select User #1001 & Chat]
   ```
3. Counselor clicks `[Select User #1001 & Chat]`.
4. The bot connects the counselor directly to User #1001.
5. While connected, all text, photos, and voice notes the counselor sends to the bot are forwarded to the seeker as `Counselor:`.
6. When counseling is finished, counselor types `/close` or clicks `[End Session]`.
7. Counselor can type `/feed` at any time to see other waiting users.

---

## Bot Commands Reference

### Seeker Commands
| Command | Description |
|---|---|
| `/start` | View welcome message and guidelines |
| `/status` | Check if your request is pending or active |
| `/close` | Conclude and close your current session |
| `/myid` | View your numeric Telegram user ID |
| `/help` | Read the seeker confidentiality guide |

### Counselor Commands
| Command | Description |
|---|---|
| `/start` | Open the Counselor Control Panel |
| `/feed` or `/cases` | View the live feed of waiting seekers |
| `/active` | View the user currently assigned to you |
| `/close` | Conclude and close your active session |
| `/release` | Return the active seeker back to the feed |
| `/stats` | View case statistics (total, pending, active, closed) |
| `/reload` | Reload counselor IDs from `.env` without restarting |
| `/myid` | Check your Telegram User ID |
| `/help` | View counselor instructions |

---

## Technical Notes
- **Framework**: `python-telegram-bot` v20.7+ (Async / Await).
- **Database**: SQLite3 (`counseling_bot.db`), automatic table creation, indexed lookup.
- **Privacy Enforcement**: Seeker metadata (username, real name, chat ID) is completely stripped before forwarding to counselors.
