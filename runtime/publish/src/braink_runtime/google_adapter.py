"""Optional Google write adapter. Installed with: pip install .[google]
No credentials are bundled; deployment must provide user-owned OAuth credentials.
"""
from __future__ import annotations
from pathlib import Path

SCOPES=['https://www.googleapis.com/auth/spreadsheets','https://www.googleapis.com/auth/calendar','https://www.googleapis.com/auth/gmail.modify','https://www.googleapis.com/auth/drive.file']

def credentials(credentials_file:str, token_file:str):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    token=Path(token_file); creds=None
    if token.exists(): creds=Credentials.from_authorized_user_file(str(token),SCOPES)
    if creds and creds.expired and creds.refresh_token: creds.refresh(Request())
    if not creds or not creds.valid:
        flow=InstalledAppFlow.from_client_secrets_file(credentials_file,SCOPES); creds=flow.run_local_server(port=0)
    token.parent.mkdir(parents=True,exist_ok=True); token.write_text(creds.to_json())
    return creds

def build_services(credentials_file:str,token_file:str):
    from googleapiclient.discovery import build
    c=credentials(credentials_file,token_file)
    return {k:build(k,v,credentials=c) for k,v in {'sheets':'v4','calendar':'v3','gmail':'v1','drive':'v3'}.items()}
