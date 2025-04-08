from django.db import models
from django.contrib.auth.models import User

class EmailCampaign(models.Model):
    TONE_CHOICES = [
        ('professional', 'Professional'),
        ('friendly', 'Friendly'),
        ('urgent', 'Urgent'),
    ]
    
   
    name = models.CharField(max_length=255)
    topic = models.TextField()
    details = models.TextField()
    tone = models.CharField(max_length=100, choices=TONE_CHOICES, default='professional')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class Recipient(models.Model):
    campaign = models.ForeignKey(EmailCampaign, related_name='recipients', on_delete=models.CASCADE)
    email = models.EmailField()
    name = models.CharField(max_length=255, blank=True)
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('campaign', 'email')

class GeneratedEmail(models.Model):
    campaign = models.OneToOneField(EmailCampaign, related_name='generated_email', on_delete=models.CASCADE)
    subject = models.TextField()
    body_text = models.TextField()
    body_html = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)