# RBXChance Auto Joiner

A simple script to automatically join RBXChance freebies and giveaways.

## Requirements
- Python 3.x
- A **3+ month old** Discord account
- A Roblox account

## Setup

1. Create an account on [RBXChance](https://www.rbxchance.com/freebies).

2. Obtain multiple accounts (recommended for better results):
   - **Discord Accounts** → [discord-accounts.com](https://discord-accounts.com/category/fresh)
   - **Roblox Accounts** → [bloxgen.net](https://bloxgen.net/@d1wpe)

3. For each account:
   - Log into RBXChance
   - Press `F12` to open Developer Tools
   - Go to the **Network** tab
   - Refresh the page (`Ctrl + R`)
   - Find and copy your `accessToken`
   - Paste it into `token.txt` (one token per line)

4. Repeat step 3 until you have the desired number of accounts.

## Usage

Once you have added all your tokens:

1. Open the `main.py` file and configure the following variables:

   - `WEBHOOK_URL` — Discord webhook URL for notifications. Leave empty to disable notifications.
   - `RECIPIENT_ID` — Default rbxchance user ID to tip when none is specified.
   - `LOOP_INTERVAL` — Time (in seconds) to sleep between each cycle.

2. Run the script.

---

**Note:** I (Lyez) am not responsible if your accounts get banned, your IP gets leaked, or if someone uses your IP to DDoS you. Use at your own risk. Automating actions on websites may violate their Terms of Service (TOS). If you need to reach out please dm me on discord
