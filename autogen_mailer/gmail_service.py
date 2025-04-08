import os
import base64
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.conf import settings
import logging

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GmailService:
    def __init__(self, user_id="me"):
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.send']
        self.CREDENTIALS_PATH = getattr(settings, 'GOOGLE_OAUTH_CREDENTIALS_PATH', 
                                      os.path.join(Path.home(), '.gmail_autogen', 'credentials.json'))
        self.TOKEN_PATH = getattr(settings, 'GOOGLE_OAUTH_TOKEN_PATH', 
                                 os.path.join(Path.home(), '.gmail_autogen', 'token.json'))
        self.user_id = user_id
        self.service = self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0"""
        creds = None
        
        # Create credentials directory if it doesn't exist
        Path(self.CREDENTIALS_PATH).parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing credentials if available
        if os.path.exists(self.TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(self.TOKEN_PATH, self.SCOPES)
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.CREDENTIALS_PATH):
                    raise FileNotFoundError(
                        f"Google OAuth credentials not found at {self.CREDENTIALS_PATH}. "
                        "Please download from Google Cloud Console."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CREDENTIALS_PATH, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials
            with open(self.TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)

    def send_email(self, sender: str, to: str, subject: str, body_text: str, body_html: str = None, attachments=None):
        """Send an email using Gmail API with optional attachments"""
        try:
            message = MIMEMultipart('mixed')
            message['to'] = to
            message['from'] = sender
            message['subject'] = subject
            
            # Create the body container
            msg_body = MIMEMultipart('alternative')
            msg_body.attach(MIMEText(body_text, 'plain'))
            msg_body.attach(MIMEText(body_html or body_text, 'html'))
            message.attach(msg_body)
            
            # Handle attachments
            if attachments:
                print("entered")
                for attachment in attachments:
                    # Ensure we're at the start of the file
                    try:
                        if hasattr(attachment, 'seek'):
                            attachment.seek(0)
                        
                        # Get the file content
                        file_content = attachment.read()
                        
                        # Determine MIME type
                        maintype, subtype = self._get_mime_types(attachment.name)

                        # Create attachment part
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(file_content)
                        encoders.encode_base64(part)
                         # Set headers
                        part.add_header(
                            'Content-Disposition',
                            'attachment',
                            filename=attachment.name
                        )
                        part.add_header(
                            'Content-ID',
                            f'<{attachment.name}>'
                        )
                        message.attach(part)
                        print("attachement.name")
                        print(attachement.name)
                    except Exception as e:
                        logger.error(f"Failed to process attachment {attachment.name}: {str(e)}")
                        continue
                        
                        
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = self.service.users().messages().send(
                userId=self.user_id,
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent to {to} with message ID: {result['id']}")
            print(result)
            return result
            
        except HttpError as error:
            logger.error(f'Gmail API error occurred: {error}')
            raise
        except Exception as error:
            logger.error(f'Unexpected error occurred: {error}')
            raise
    def _get_mime_types(self, filename):
        """Helper method to determine MIME types"""
        filename = filename.lower()
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            return 'image', filename.split('.')[-1]
        elif filename.endswith('.pdf'):
            return 'application', 'pdf'
        elif filename.endswith('.docx'):
            return 'application', 'vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif filename.endswith('.doc'):
            return 'application', 'msword'
        elif filename.endswith(('.xls', '.xlsx')):
            return 'application', 'vnd.ms-excel'
        elif filename.endswith('.txt'):
            return 'text', 'plain'
        return 'application', 'octet-stream'