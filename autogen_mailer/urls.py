from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmailCampaignViewSet, RecipientViewSet

router = DefaultRouter()
router.register(r'campaigns', EmailCampaignViewSet, basename='campaign')
router.register(r'recipients', RecipientViewSet, basename='recipient')

urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints
    path('campaigns/<int:pk>/import_recipients/', 
         EmailCampaignViewSet.as_view({'post': 'import_recipients'}), 
         name='import-recipients'),
    path('campaigns/<int:pk>/generate_content/', 
         EmailCampaignViewSet.as_view({'post': 'generate_content'}), 
         name='generate-content'),
    path('campaigns/<int:pk>/send_emails/', 
         EmailCampaignViewSet.as_view({'post': 'send_emails'}), 
         name='send-emails'),
    path('campaigns/<int:pk>/preview/', 
         EmailCampaignViewSet.as_view({'get': 'preview'}), 
         name='preview-email'),
    path('campaigns/<int:pk>/generate_and_send/',
     EmailCampaignViewSet.as_view({'post': 'generate_and_send'}),
     name='generate-and-send'),

     # NEW REPLY HANDLING ENDPOINTS
    path('campaigns/<int:pk>/reply_stats/',
         EmailCampaignViewSet.as_view({'get': 'reply_stats'}),
         name='reply-stats'),
    path('campaigns/<int:pk>/process_replies/',
         EmailCampaignViewSet.as_view({'post': 'process_replies'}),
         name='process-replies'),
    path('campaigns/<int:pk>/verify_replies/',
         EmailCampaignViewSet.as_view({'get': 'verify_replies'}),
         name='verify-replies')
]
