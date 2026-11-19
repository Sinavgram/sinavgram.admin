# Sınavgram Admin Panel

**Sınavgram Admin** is a web-based administration dashboard developed to manage the operational side of the Sınavgram educational platform.

Built with Python and Flask, the application integrates directly with Firebase Firestore through the Firebase Admin SDK. It provides administrative tools for question moderation, educational content management, email operations, newsletter distribution, and user score administration.

## Features

### Question Management

Manage the question lifecycle through a centralized dashboard.

- View pending questions.
- Review reported questions.
- Browse approved questions.
- Approve or change question statuses.
- Edit question content and answer options.
- Update course and subtopic associations.
- Manage question image URLs.
- Delete questions when necessary.
- Search and paginate through question records.

### Course & Subtopic Management

- Retrieve course information from Firestore.
- Display associated subtopics.
- Resolve course and subtopic references when reviewing questions.
- Cache course information to reduce repeated database queries.

### Email Management

The panel includes an integrated Gmail interface using IMAP and SMTP.

- Browse inbox messages.
- View sent messages.
- Access spam messages.
- Search email messages.
- Read individual messages.
- Compose and send emails.
- Send attachments.
- Reply to existing messages.

### Newsletter Management

Newsletter functionality is integrated with Firestore.

- Manage newsletter distribution.
- Send test newsletters.
- Prepare HTML-based newsletter content.
- Retrieve registered newsletter subscribers.
- Queue newsletter messages through the Firestore `mail` collection.

### User Score Administration

The application includes seasonal score archiving functionality.

- Retrieve registered users.
- Archive existing user scores.
- Reset current scores.
- Preserve historical scores under season-specific fields.
- Process bulk updates using Firestore batch operations.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Flask | Web application framework |
| Firebase Admin SDK | Firebase administration |
| Cloud Firestore | Database operations |
| Gmail IMAP | Email retrieval |
| Gmail SMTP | Email delivery |
| AES-GCM | Credential encryption |
| Jinja2 | HTML template rendering |
| Werkzeug | File handling and utilities |

## Architecture

The application uses a server-side architecture based on Flask.

```text
Administrator
     |
     v
Flask Web Application
     |
     +----------------------+
     |                      |
     v                      v
Firebase Admin SDK      Gmail Services
     |                      |
     v                      v
Cloud Firestore         IMAP / SMTP
     |
     +----------------------+
     |
     +-- Questions
     +-- Courses
     +-- Subtopics
     +-- Users
     +-- Newsletter Subscribers
     +-- Mail Queue
```

The Flask application handles administrative requests, retrieves records from Firestore, and renders the dashboard using Jinja2 templates.

## Project Structure

```text
sinavgram.admin/
│
├── templates/
│   └── index.html
│
├── app.py
├── config.json
├── serviceAccountKey.json
│
├── requirements.txt
│
├── setup.bat
├── open.bat
│
├── setup.command
└── run.command
```

## Installation

### Requirements

- Python 3.10 or newer (compatible with the installed dependencies).
- pip
- A Firebase project with Cloud Firestore enabled.
- A Firebase service account.
- A Gmail account with an App Password.
- IMAP and SMTP access enabled where required.

### 1. Clone the repository

```bash
git clone https://github.com/Sinavgram/sinavgram.admin.git

cd sinavgram.admin
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate the environment:

**Windows**

```bash
venv\Scripts\activate
```

**macOS / Linux**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Firebase

The application uses the Firebase Admin SDK to connect to Cloud Firestore.

You must provide your own Firebase service account credentials.

The application expects the credentials in:

```text
serviceAccountKey.json
```

Generate a service account key from your Firebase project's Google Cloud service account settings.

Do not commit real service account credentials to version control.

### 5. Configure email credentials

The application uses Gmail IMAP and SMTP to manage administrative email operations.

Email credentials are loaded from `config.json` after AES-GCM decryption.

The following configuration components must be supplied locally:

- Email encryption key.
- Encrypted Gmail address.
- Encrypted Gmail App Password.
- Corresponding AES-GCM nonces.

The repository contains placeholder values rather than the original production credentials.

### 6. Start the application

```bash
python app.py
```

The development server runs on:

```text
http://127.0.0.1:5000
```

## Security Considerations

This application has access to sensitive administrative operations and should only be deployed in a trusted environment.

Before running it:

- Replace placeholder Firebase credentials with your own service account.
- Configure a unique Flask secret key.
- Replace the placeholder AES encryption key.
- Keep Gmail credentials outside public repositories.
- Restrict access to the administrative interface.
- Review Firestore permissions and service account privileges.
- Avoid exposing the development server directly to the public internet.

The built-in Flask development server is intended for local development, not production deployment.

## Project Status

This repository preserves the administrative tooling developed for Sınavgram.

The project is part of the platform's source-code preservation effort.

It is not guaranteed to remain compatible with the original production infrastructure, and the original Firebase project and Gmail credentials are not provided.

## Related Repository

- [Sınavgram Mobile Application](https://github.com/Sinavgram/sinavgram)
- [Sınavgram Firebase Infrastructure](https://github.com/Sinavgram/sinavgram.firebase)
- [Legacy Sınavgram Backend](https://github.com/Sinavgram/sinavgram.backend.old)

## License

No explicit open-source license has been specified for this repository.

Public access to the source code does not automatically grant redistribution or commercial usage rights. Please check the repository's license information before reusing the code.

## Author

**Mehmet Alper Kocaoğlu**

- GitHub: [@mehmetalper04](https://github.com/mehmetalper04)
- Organization: [Sinavgram](https://github.com/Sinavgram)

---

*Administrative infrastructure developed as part of the Sınavgram educational platform.*
