import os
import base64
import re
import logging
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
from django.db.models import Q
from .models import Recipient, EmailReply

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GmailService:
    def __init__(self, user_id="me"):
        self.SCOPES = [
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.send'
        ]
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
            try:
                creds = Credentials.from_authorized_user_file(self.TOKEN_PATH, self.SCOPES)
                # Validate credentials
                if not creds.valid:
                    if creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        creds = None
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
                creds = None
        
        # If no valid credentials, authenticate
        if not creds or not creds.valid:
            if not os.path.exists(self.CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Google OAuth credentials not found at {self.CREDENTIALS_PATH}. "
                    "Please download from Google Cloud Console."
                )
            
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.CREDENTIALS_PATH, self.SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                raise
            
            # Save the credentials
            with open(self.TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        return build('gmail', 'v1', credentials=creds)

    def get_message(self, message_id):
        """Get a message by its ID"""
        try:
            return self.service.users().messages().get(
                userId=self.user_id,
                id=message_id,
                format='full'
            ).execute()
        except HttpError as error:
            logger.error(f'Error getting message: {error}')
            raise

    def get_thread_messages(self, thread_id):
        """Get all messages in a thread"""
        try:
            thread = self.service.users().threads().get(
                userId=self.user_id,
                id=thread_id,
                format='full'
            ).execute()
            return thread.get('messages', [])
        except HttpError as error:
            logger.error(f'Error getting thread: {error}')
            raise

    def _extract_message_content(self, message):
        """Extract text content from a message"""
        parts = message['payload'].get('parts', [])
        for part in parts:
            if part['mimeType'] == 'text/plain':
                data = part['body']['data']
                return base64.urlsafe_b64decode(data).decode('utf-8')
        return ""

    def _extract_email(self, email_header):
        """Extract clean email address from header"""
        # Handle cases like "Name <email@domain.com>"
        match = re.search(r'[\w\.-]+@[\w\.-]+', email_header)
        return match.group(0).lower() if match else email_header.lower()

    def _find_recipient(self, campaign, sender_email):
        """Find recipient with flexible email matching"""
        try:
            # Try exact match first
            return Recipient.objects.get(
                campaign=campaign,
                email__iexact=sender_email
            )
        except Recipient.DoesNotExist:
            try:
                # Try matching just the local part before @
                local_part = sender_email.split('@')[0]
                return Recipient.objects.get(
                    campaign=campaign,
                    email__icontains=local_part
                )
            except Recipient.DoesNotExist:
                return None

    def process_replies_for_campaign(self, campaign):
        """Check for replies to a specific campaign with improved matching"""
        try:
            subject = campaign.generated_email.subject
            clean_subject = re.sub(r'[^a-zA-Z0-9 ]', '', subject)  # Clean special chars
            
            # More flexible search query
            query = f'(subject:{clean_subject} OR "Re: {clean_subject}") in:inbox from:-me'
            
            results = self.service.users().messages().list(
                userId=self.user_id,
                q=query,
                maxResults=50
            ).execute()
            
            messages = results.get('messages', [])
            processed_count = 0
            
            for msg in messages:
                try:
                    message = self.get_message(msg['id'])
                    thread_messages = self.get_thread_messages(message['threadId'])
                    
                    if len(thread_messages) < 2:
                        continue
                        
                    original_msg = thread_messages[0]
                    reply_msg = thread_messages[-1]
                    
                    # Extract sender email more robustly
                    sender_headers = [h for h in reply_msg['payload']['headers'] if h['name'].lower() == 'from']
                    if not sender_headers:
                        continue
                        
                    sender_email = self._extract_email(sender_headers[0]['value'])
                    
                    # Find recipient with flexible matching
                    recipient = self._find_recipient(campaign, sender_email)
                    if not recipient:
                        continue
                    
                    # Check if already processed
                    if EmailReply.objects.filter(reply_message_id=reply_msg['id']).exists():
                        continue
                        
                    # Save the reply
                    reply_content = self._extract_message_content(reply_msg)
                    EmailReply.objects.create(
                        campaign=campaign,
                        recipient=recipient,
                        original_message_id=original_msg['id'],
                        reply_message_id=reply_msg['id'],
                        reply_content=reply_content
                    )
                    processed_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing message {msg.get('id')}: {str(e)}")
                    continue
            
            logger.info(f"Processed {processed_count} new replies for campaign {campaign.id}")
            return processed_count
            
        except Exception as error:
            logger.error(f'Error processing replies: {error}')
            raise

    def send_email(self, sender, to, subject, body_text, body_html=None, attachments=None):
        """Send an email with optional attachments"""
        try:
            message = MIMEMultipart('mixed')
            message['to'] = to
            message['from'] = sender
            message['subject'] = subject
            
            msg_body = MIMEMultipart('alternative')
            msg_body.attach(MIMEText(body_text, 'plain'))
            msg_body.attach(MIMEText(body_html or body_text, 'html'))
            message.attach(msg_body)
            
            if attachments:
                for attachment in attachments:
                    try:
                        if hasattr(attachment, 'seek'):
                            attachment.seek(0)
                        
                        file_content = attachment.read()
                        maintype, subtype = self._get_mime_types(attachment.name)

                        part = MIMEBase(maintype, subtype)
                        part.set_payload(file_content)
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', 'attachment', filename=attachment.name)
                        message.attach(part)
                    except Exception as e:
                        logger.error(f"Failed to process attachment {attachment.name}: {str(e)}")
                        continue
            
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            result = self.service.users().messages().send(
                userId=self.user_id,
                body={'raw': raw_message}
            ).execute()
            
            logger.info(f"Email sent to {to} with message ID: {result['id']}")
            return result
            
        except HttpError as error:
            logger.error(f'Gmail API error occurred: {error}')
            raise
        except Exception as error:
            logger.error(f'Unexpected error occurred: {error}')
            raise

    def _get_mime_types(self, filename):
        """Determine MIME types for attachments"""
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

    def get_hardcoded_user_email(self):
        """Hardcoded sender email - should be configured in settings"""
        return getattr(settings, 'DEFAULT_FROM_EMAIL', 'your-email@example.com')