# Student Assistant Bot - Local Testing Guide

This guide explains how to run the project locally using Docker, allowing you to access the database and AI functionality via a web interface (Streamlit) without needing a Telegram bot token.

## Prerequisites
- Docker & Docker Compose installed.

## Setup & Run
1.  **Configure Environment**:
    - Ensure you have a `.env` file in the root directory.
    - Copy `example.env` if needed: `cp example.env .env`
    - **Note:** For this local test, you **do not** need a valid `BOT_TOKEN` if you are only using the web admin panel. However, you **do need** a valid `GROQ_API_KEY` for AI features.

2.  **Start Services**:
    Run the following command in your terminal:
    ```bash
    docker compose up --build
    ```
    This will start:
    - **db**: PostgreSQL database with `pgvector`.
    - **admin**: Streamlit web interface.

3.  **Access Admin Panel**:
    Open your browser and go to: [http://localhost:8501](http://localhost:8501)

## Features (Web Admin)
The Admin Panel allows you to test all core functionalities:

### 1. 📝 Knowledge Base (FAQ)
- **View**: See all Q&A entries currently in the database.
- **Add**: Create new knowledge items (Topic, Keywords, Content).
- **Edit/Delete**: Modify or remove existing entries.
*This data is used by the RAG system to answer user queries.*

### 2. 📂 Files
- View all files (documents/photos) indexed in the database.
- *Note:* Indexing new files typically happens via Telegram, but you can view what's already there.

### 3. 👥 Users
- View registered users.
- Check their **Quota** status (`requests_left`) and reset times.

### 4. 🧠 RAG Playground (AI Test)
- **Simulate User Queries**: Type a question in the input box.
- **See RAG Process**:
    - The system will search the Knowledge Base (Vector Search).
    - It will show the retrieved **Context** (with similarity scores).
    - It will generate and display the **AI Answer**.

## Troubleshooting
- **Database Connection Error**: Ensure the `db` container is healthy (`docker ps`).
- **AI Error**: Check your `GROQ_API_KEY` in `.env`.
