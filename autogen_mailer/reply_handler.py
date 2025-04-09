import logging
from openai import OpenAI
from django.conf import settings
from .models import EmailReply, Recipient
from .gmail_service import GmailService

logger = logging.getLogger(__name__)

class ReplyHandler:
    def __init__(self):
        self.client = OpenAI(api_key="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")
        self.gmail = GmailService()
        print("self.gmail")
        print(self.gmail)
        
    
    def generate_reply(self, email_reply):
        print(f"Recipient ID: {email_reply.recipient.id}")
        """Generate a personalized reply using AI"""
        try:
            print("replyhandler")
            # Verify recipient still exists
            if not Recipient.objects.filter(pk=email_reply.recipient.id).exists():
                return None
                
            prompt = f"""
            Campaign: {email_reply.campaign.name}
            Original Email: {email_reply.campaign.generated_email.body_text}
            Received Reply: {email_reply.reply_content}
            
            Please compose a professional response that:
            1. Acknowledges their reply
            2. Addresses any questions/points they raised
            3. Maintains a {email_reply.campaign.tone} tone
            4. Is concise (under 150 words)
            """
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating reply: {str(e)}")
            raise
    
    def process_pending_replies_for_campaign(self, campaign):
        """Process and reply to pending messages for a campaign"""
        pending_replies = EmailReply.objects.filter(
            campaign=campaign,
            processed=False
        )
        print(pending_replies.count())
        print("pending_replies.count()")
        results = {
        'total': pending_replies.count(),
        'success': 0,
        'failed': 0,
        'details': []
        }
        for reply in pending_replies:
            try:
                ai_reply = self.generate_reply(reply)
                if not ai_reply:
                    logger.warning(f"No reply generated for {reply.id}")
                    results['details'].append({
                        'reply_id': reply.id,
                        'status': 'skipped',
                        'reason': 'no_reply_generated'
                    })
                    continue
                reply_text_with_breaks = ai_reply.replace('\n', '<br>')
                html_content = f"<p>{reply_text_with_breaks}</p>"
                
                self.gmail.send_email(
                    sender=self.gmail.get_hardcoded_user_email(),
                    to=reply.recipient.email,
                    subject=f"Re: {reply.campaign.generated_email.subject}",
                    body_text=ai_reply,
                    body_html=html_content
                    )
                
                reply.processed = True
                reply.reply_sent = True
                reply.save()
                results['success'] += 1
                results['details'].append({
                    'reply_id': reply.id,
                    'status': 'sent',
                    'recipient': reply.recipient.email,
                    'message': 'Reply sent successfully'
                })
            except Exception as e:
                logger.error(f"Failed to process reply: {str(e)}")
                reply.processed = True  # Mark as processed to avoid retrying
                reply.save()
                results['failed'] += 1
                results['details'].append({
                    'reply_id': reply.id,
                    'status': 'failed',
                    'error': str(e),
                    'error_type': type(e).__name__
                })
        
        logger.info(f"Reply processing completed: {results['success']} sent, {results['failed']} failed")
        return results