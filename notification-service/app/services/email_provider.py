import logging
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

class EmailProvider:
    """Provider for sending email notifications."""
    
    def __init__(self):
        self.host = settings.SMTP_HOST
        self.port = settings.SMTP_PORT
        self.username = settings.SMTP_USER
        self.password = settings.SMTP_PASSWORD
        self.from_email = settings.EMAIL_FROM
        self.from_name = settings.EMAIL_FROM_NAME
    
    async def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str, 
        text_content: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
        """
        Send an email notification.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            text_content: Plain text content (optional)
            cc: Carbon copy recipients (optional)
            bcc: Blind carbon copy recipients (optional)
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        # Skip if email configuration is missing
        if not self.username or not self.password or not self.from_email:
            logger.warning("Email configuration is incomplete. Cannot send email.")
            return False
        
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["From"] = f"{self.from_name} <{self.from_email}>"
            message["To"] = to_email
            message["Subject"] = subject
            
            # Add CC if provided
            if cc:
                message["Cc"] = ", ".join(cc)
                
            # Add plain text version
            if text_content:
                message.attach(MIMEText(text_content, "plain", "utf-8"))
            else:
                # Generate plain text from HTML
                text_version = html_content.replace("<br>", "\n").replace("<br/>", "\n").replace("<p>", "\n").replace("</p>", "\n")
                message.attach(MIMEText(text_version, "plain", "utf-8"))
            
            # Add HTML version
            message.attach(MIMEText(html_content, "html", "utf-8"))
            
            # Build recipient list
            recipients = [to_email]
            if cc:
                recipients.extend(cc)
            if bcc:
                recipients.extend(bcc)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=True
            )
            
            logger.info(f"Email sent to {to_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

# Create a singleton instance
email_provider = EmailProvider()