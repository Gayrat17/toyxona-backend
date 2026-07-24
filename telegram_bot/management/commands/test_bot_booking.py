from django.core.management.base import BaseCommand, CommandError
from bookings.models import HallBooking, BarBooking
from telegram_bot.tasks import send_new_booking_notification

class Command(BaseCommand):
    help = "Test booking notification transmission to Telegram Bot for a specific booking ID."

    def add_arguments(self, parser):
        parser.add_argument(
            '--booking_id',
            type=int,
            required=True,
            help='ID of the booking to test'
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['hall', 'bar'],
            help='Type of the booking (hall or bar). If omitted, attempts to find in both.'
        )

    def handle(self, *args, **options):
        booking_id = options['booking_id']
        booking_type = options['type']
        
        booking = None
        detected_type = None

        if booking_type:
            detected_type = booking_type
            if booking_type == 'hall':
                booking = HallBooking.objects.filter(id=booking_id).first()
            else:
                booking = BarBooking.objects.filter(id=booking_id).first()
        else:
            # Auto-detect
            booking = HallBooking.objects.filter(id=booking_id).first()
            if booking:
                detected_type = 'hall'
            else:
                booking = BarBooking.objects.filter(id=booking_id).first()
                if booking:
                    detected_type = 'bar'

        if not booking:
            raise CommandError(f"Booking with ID {booking_id} not found in database.")

        self.stdout.write(self.style.SUCCESS(f"Found {detected_type.upper()} Booking (ID: {booking_id})"))
        
        # Display owner info
        if detected_type == 'hall':
            owner = booking.hall.owner
            venue_name = booking.hall.name
        else:
            owner = booking.bar.owner
            venue_name = booking.bar.name

        self.stdout.write(f"Venue Name: {venue_name}")
        self.stdout.write(f"Owner Username/Phone: {owner.phone_number} (ID: {owner.id})")
        self.stdout.write(f"Owner telegram_chat_id: {owner.telegram_chat_id}")

        self.stdout.write("Running notification trigger synchronously...")
        
        # Run send_new_booking_notification sync
        result = send_new_booking_notification(detected_type, booking_id)
        
        if result == "SUCCESS":
            self.stdout.write(self.style.SUCCESS("RESULT: Notification sent successfully!"))
        else:
            self.stdout.write(self.style.ERROR(f"RESULT: Notification failed. Reason/Status: {result}"))
