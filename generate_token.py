# generate_token.py

import google.auth.transport.requests
from google_auth_oauthlib.flow import InstalledAppFlow
import json

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',  # Google CloudでDLしたJSON名
        scopes=['https://www.googleapis.com/auth/adwords']
    )

    creds = flow.run_console()

    print("\n✅ Access Token:", creds.token)
    print("🔁 Refresh Token:", creds.refresh_token)
    print("🆔 Client ID:", creds.client_id)
    print("🔒 Client Secret:", creds.client_secret)

    # 保存するならこんな形で
    with open('token_output.json', 'w') as f:
        json.dump({
            'refresh_token': creds.refresh_token,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret
        }, f, indent=2)

if __name__ == '__main__':
    main()
