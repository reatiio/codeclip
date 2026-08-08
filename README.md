# CodeClip

**CodeClip** is a lightweight Windows app that automatically finds recent verification codes from Gmail and copies them to your clipboard.

It is designed for situations where you receive login codes from services like **Microsoft** or **Steam** and don't want to manually open Gmail, find the email, and copy the code.

## ✨ Features

* 🔍 Automatically scans Gmail when launched
* 📋 Automatically copies the newest code to your clipboard
* ⚡ Quick Mode for a minimal code-only interface
* 📧 Supports multiple email services at once
* 🎯 Microsoft and Steam have built-in code detection
* 🕐 Only searches recent emails instead of your entire inbox
* ⚙️ Add your own services with custom regex patterns
* 🌙 Dark interface
* 💻 Can be packaged as a standalone Windows `.exe`
* 🔒 Uses Google's Gmail API with read-only access

---

# 🚀 Using the EXE

If you're using the packaged version, you don't need Python installed.

Put these files in the same folder:

```text
CodeClip/
├── CodeClip.exe
└── credentials.json
```

On the first launch, CodeClip will open Google's login/authorization page.

Sign into the Gmail account you want CodeClip to read and allow the requested Gmail permission.

After authorization, Google authentication information will be saved locally as:

```text
token.json
```

Your folder will then look something like:

```text
CodeClip/
├── CodeClip.exe
├── credentials.json
├── token.json
└── settings.json
```

You normally won't need to touch `token.json` or `settings.json`.

---

# 📧 Gmail Setup

CodeClip uses the official Gmail API.

You need to create a Google Cloud project and create OAuth credentials.

## 1. Create a Google Cloud Project

Go to:

https://console.cloud.google.com/

Create a new project.

For example:

```text
CodeClip
```

---

## 2. Enable the Gmail API

In Google Cloud:

**APIs & Services → Library**

Search for:

```text
Gmail API
```

Enable it.

---

## 3. Configure OAuth

Go to:

**APIs & Services → OAuth consent screen**

Configure the application.

For a personal project, you can use the appropriate external/testing configuration.

Add the Gmail scope used by CodeClip:

```text
https://www.googleapis.com/auth/gmail.readonly
```

---

## 4. Create Credentials

Go to:

**APIs & Services → Credentials**

Create:

**OAuth Client ID**

Choose:

```text
Desktop app
```

Download the credentials file.

Rename it:

```text
credentials.json
```

Place it next to `CodeClip.exe`.

---

# 🐍 Running From Source

If you want to run the Python version instead of the EXE, install Python 3.10+.

Then install the dependencies:

```bash
pip install PySide6 google-api-python-client google-auth-httplib2 google-auth-oauthlib pyperclip
```

Run:

```bash
python CodeClip.py
```

Make sure `credentials.json` is in the same directory.

---

# 🔑 First Launch

The first time CodeClip runs, Google will ask you to authorize Gmail access.

After authorization, CodeClip can read recent emails and find verification codes.

CodeClip only requests:

```text
gmail.readonly
```

It does **not** have permission to send, delete, or modify your emails.

---

# 📋 How CodeClip Works

When CodeClip launches, it automatically searches Gmail.

By default, it searches the last:

```text
5 minutes
```

If it finds a supported code, it displays it and automatically copies the newest code to your clipboard.

For example:

```text
CodeClip

Microsoft
431823

Steam
M7NP4
```

You can then simply press:

```text
Ctrl + V
```

to paste the code.

---

# ⚙️ Settings

Open the **Settings** tab to configure CodeClip.

## Services

The Services section lets you manage which email services CodeClip searches.

You can:

* Add a service
* Edit a service
* Delete a service
* Enable/disable a service

---

# ➕ Adding a Service

Click:

```text
Settings → + Add Service
```

You'll see:

```text
Service name:
Sender email:
Subject contains:
Code pattern:
Enable this service
```

## Service Name

Enter the name of the service.

Example:

```text
Epic Games
```

---

## Sender Email

Enter the email address that sends the verification codes.

Example:

```text
noreply@epicgames.com
```

This is important because CodeClip uses the sender to narrow down the Gmail search.

---

## Subject Contains

This field is optional.

If verification emails have a consistent subject, you can enter part of it.

Example:

```text
Your Security Code
```

If the subject changes, you can leave this blank.

---

# 🧩 Code Pattern

For custom services, CodeClip uses a regular expression (regex) to find the code.

The pattern needs **one capture group** containing the code.

For example, if the email says:

```text
Your verification code is: 123456
```

Use:

```regex
Your verification code is:\s*(\d{6})
```

The important part is:

```regex
(\d{6})
```

That tells CodeClip:

> This is the code I want.

---

# 🔢 Common Patterns

### Six-digit code

```regex
(\d{6})
```

Matches:

```text
123456
```

---

### Five-digit code

```regex
(\d{5})
```

Matches:

```text
12345
```

---

### Five-character code

```regex
([A-Z0-9]{5})
```

Matches:

```text
M7NP4
```

---

### Code after a specific sentence

Email:

```text
Your verification code is 839201
```

Pattern:

```regex
Your verification code is\s+(\d{6})
```

---

# 🎮 Steam

Steam is already built into CodeClip.

The Steam email looks similar to:

```text
Here is the Steam Guard code you need to access your account:

Request made from
Florida, United States

M7NP4

If this wasn't you
```

CodeClip specifically searches for the Steam Guard section rather than simply searching for random five-character strings.

This prevents words such as:

```text
STEAM
HELLO
CHEERS
```

from accidentally being detected as the code.

---

# 🪟 Microsoft

Microsoft is also built into CodeClip.

Microsoft verification emails contain:

```text
Your single-use code is: 431823
```

CodeClip specifically looks for the six-digit number following that text.

---

# ⚡ Quick Mode

Quick Mode provides a minimal interface.

Instead of the full CodeClip interface, it simply shows the codes it finds.

You can open it from:

```text
Codes → Quick Mode
```

You can also enable:

```text
Settings → Start in Quick Mode
```

if you want CodeClip to start with the minimal interface.

---

# 🕐 Search Time

By default CodeClip searches the last:

```text
5 minutes
```

You can change this under:

```text
Settings → Search the last
```

For example:

```text
1 minute
5 minutes
10 minutes
30 minutes
60 minutes
```

Keeping this relatively short is recommended because CodeClip is intended to find newly received codes rather than old verification emails.

---

# 📦 Building the EXE

If you're building the Windows executable yourself, install PyInstaller:

```bash
pip install pyinstaller
```

Then run:

```bash
pyinstaller --onefile --windowed CodeClip.py
```

The executable will be created inside:

```text
dist/
```

So you'll have:

```text
dist/
└── CodeClip.exe
```

Copy `credentials.json` next to the executable.

Your final distribution folder can look like:

```text
CodeClip/
├── CodeClip.exe
└── credentials.json
```

`token.json` and `settings.json` will be created automatically after the user runs the application.

---

# 🗂️ Files

| File               | Purpose                         |
| ------------------ | ------------------------------- |
| `CodeClip.py`      | Python source code              |
| `CodeClip.exe`     | Packaged Windows application    |
| `credentials.json` | Google OAuth client credentials |
| `token.json`       | Saved Gmail authorization       |
| `settings.json`    | CodeClip settings and services  |

---

# 🔐 Security

CodeClip uses Gmail's read-only API permission:

```text
https://www.googleapis.com/auth/gmail.readonly
```

CodeClip does not need permission to:

* Send emails
* Delete emails
* Modify emails
* Change Gmail settings

Keep your Google OAuth files private and **never commit your personal `token.json` to GitHub**.

Add these to your `.gitignore`:

```gitignore
token.json
settings.json
__pycache__/
*.pyc
build/
dist/
```

If `credentials.json` contains credentials specific to your personal Google Cloud project, consider keeping it private as well.

---

# 🛠️ Troubleshooting

## "credentials.json was not found"

Make sure:

```text
credentials.json
```

is in the same directory as CodeClip.

---

## CodeClip doesn't find a code

Check:

1. The email was received within the configured search window.
2. The sender email is correct.
3. The service is enabled.
4. The code pattern matches the email.
5. The Gmail account you authorized is the account receiving the code.

Try increasing the search time temporarily.

---

## Google authorization doesn't work

Delete:

```text
token.json
```

and launch CodeClip again.

This will make Google authorization run again.

---

## My custom service detects the wrong thing

Make the regex more specific.

Instead of:

```regex
(\d{6})
```

use something tied to the text surrounding the code:

```regex
Your verification code is:\s*(\d{6})
```

The more specific the pattern, the less likely CodeClip is to detect the wrong number.

---

# 📜 License

Add your preferred license here.

For example:

```text
MIT License
```

---

# ⭐ CodeClip

A simple way to go from:

```text
Email arrives
↓
Open Gmail
↓
Find email
↓
Find code
↓
Copy code
↓
Go back to login
↓
Paste code
```

to:

```text
Email arrives
↓
CodeClip
↓
Ctrl + V
```
