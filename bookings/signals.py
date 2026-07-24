from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import HallBooking, BarBooking
from telegram_bot.tasks import send_new_booking_notification

@receiver(post_save, sender=HallBooking)
def notify_hall_owner_on_booking_creation(sender, instance, created, **kwargs):
    """
    Sends a Telegram notification to the Wedding Hall owner when a booking is created (PENDING).
    """
    if created and instance.status == 'PENDING':
        print(f"[BOT DEBUG] Yangi bron yaratildi, xabar yuborish boshlanmoqda... Booking ID: {instance.id}")
        
        # Sync fallback for DEBUG mode
        if getattr(settings, 'DEBUG', False):
            send_new_booking_notification('hall', instance.id)
        else:
            send_new_booking_notification.delay('hall', instance.id)

@receiver(post_save, sender=BarBooking)
def notify_bar_owner_on_booking_creation(sender, instance, created, **kwargs):
    """
    Sends a Telegram notification to the Bar owner when a booking is created (PENDING).
    """
    if created and instance.status == 'PENDING':
        print(f"[BOT DEBUG] Yangi bron yaratildi, xabar yuborish boshlanmoqda... Booking ID: {instance.id}")
        
        # Sync fallback for DEBUG mode
        if getattr(settings, 'DEBUG', False):
            send_new_booking_notification('bar', instance.id)
        else:
            send_new_booking_notification.delay('bar', instance.id)
