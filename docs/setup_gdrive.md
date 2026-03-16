# Google Drive MCP Setup Guide

To enable Google Drive integration for the Agentic Engineering System, follow these steps:

## 1. Create a Google Cloud Project
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click "Select a project" > "New Project".
3. Give it a name like `agentic-rag-system`.

## 2. Enable APIs
1. In the sidebar, go to **APIs & Services > Library**.
2. Search for and enable:
   - **Google Drive API**
   - **Google Docs API** (optional but recommended for better parsing)

## 3. Create Credentials (Service Account)
1. Go to **APIs & Services > Credentials**.
2. Click **+ Create Credentials > Service Account**.
3. Name it `rag-fetcher`.
4. Skip optional steps and click **Done**.
5. Click on the newly created service account.
6. Go to the **Keys** tab.
7. Click **Add Key > Create new key**.
8. Select **JSON** and click **Create**.
9. Save this file as `secrets/google_creds.json` in your project root.

## 4. Share the Document
1. Open the target Google Doc/Folder.
2. Click **Share**.
3. Add the Service Account email (e.g., `rag-fetcher@project-id.iam.gserviceaccount.com`) as a **Viewer**.

## 5. Update Configuration
Ensure your `.env` or `src/core/config.py` reflects the path:
```env
GOOGLE_SERVICE_ACCOUNT_JSON_PATH="secrets/google_creds.json"
```
