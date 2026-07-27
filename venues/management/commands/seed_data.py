from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import time, date, timedelta
from decimal import Decimal
from venues.models import Region, District, WeddingHall, Bar, Shift, Package, Decoration, ShiftBlock
from bookings.models import HallBooking, BarBooking

User = get_user_model()

class Command(BaseCommand):
    help = "Seeds database with initial test data for Restoran & Bar Booking system"

    def handle(self, *args, **options):
        self.stdout.write("Seeding data...")

        # 1. Clear existing data to prevent conflicts
        self.stdout.write("Cleaning database...")
        HallBooking.objects.all().delete()
        BarBooking.objects.all().delete()
        ShiftBlock.objects.all().delete()
        Decoration.objects.all().delete()
        Package.objects.all().delete()
        Shift.objects.all().delete()
        WeddingHall.objects.all().delete()
        Bar.objects.all().delete()
        District.objects.all().delete()
        Region.objects.all().delete()
        User.objects.all().delete()

        # 2. Seed Regions & Districts of Uzbekistan
        self.stdout.write("Seeding Uzbekistan Regions & Districts...")
        UZ_REGIONS_DATA = {
            "Toshkent shahri": ["Yunusobod", "Chilonzor", "Mirzo Ulug'bek", "Yakkasaroy", "Mirobod", "Shayxontohur", "Olmazor", "Sergeli", "Yashnobod"],
            "Toshkent viloyati": ["Keles", "Chirchiq", "Olmaliq", "Angren", "Yangiyo'l", "Qibray", "Zangiota"],
            "Samarqand": ["Samarqand sh.", "Pastdarg'om", "Jomboy", "Toyloq", "Kattaqo'rg'on"],
            "Buxoro": ["Buxoro sh.", "G'ijduvon", "Kogon", "Romitsh"],
            "Farg'ona": ["Farg'ona sh.", "Marg'ilon", "Qo'qon", "Oltiariq"],
            "Namangan": ["Namangan sh.", "Chust", "Pop", "Kosonsoy"],
            "Andijon": ["Andijon sh.", "Asaka", "Shahrixon", "Xo'jaobod"],
        }

        created_districts = {}
        for reg_order, (reg_name, dist_list) in enumerate(UZ_REGIONS_DATA.items(), start=1):
            region_obj = Region.objects.create(name=reg_name, order=reg_order)
            for dist_order, dist_name in enumerate(dist_list, start=1):
                dist_obj = District.objects.create(region=region_obj, name=dist_name, order=dist_order)
                created_districts[f"{reg_name}-{dist_name}"] = dist_obj

        toshkent_sh = Region.objects.get(name="Toshkent shahri")
        chilonzor_dist = created_districts.get("Toshkent shahri-Chilonzor")
        yunusobod_dist = created_districts.get("Toshkent shahri-Yunusobod")

        # 3. Create Users
        self.stdout.write("Creating users...")
        # Superadmin
        admin = User.objects.create_superuser(phone_number="+998901234567", password="1")
        admin.first_name = "Super"
        admin.last_name = "Admin"
        admin.save()

        # Venue Owner 1 (Wedding Hall Owner)
        owner1 = User.objects.create_user(
            phone_number="+998901112233", 
            password="1", 
            role="VENUE_OWNER", 
            telegram_chat_id="123456789"
        )
        owner1.first_name = "Ahror"
        owner1.last_name = "Umarov"
        owner1.save()

        # Venue Owner 2 (Bar Owner)
        owner2 = User.objects.create_user(
            phone_number="+998904445566", 
            password="1", 
            role="VENUE_OWNER"
        )
        owner2.first_name = "Sardor"
        owner2.last_name = "Karimov"
        owner2.save()

        # Client 1
        client1 = User.objects.create_user(
            phone_number="+998907778899", 
            password="1", 
            role="CLIENT"
        )
        client1.first_name = "Diyor"
        client1.last_name = "Aliyev"
        client1.save()

        # 4. Create Wedding Hall
        self.stdout.write("Creating wedding hall...")
        hall = WeddingHall.objects.create(
            owner=owner1,
            region=toshkent_sh,
            district=chilonzor_dist,
            name="Yulduz To'yxonasi",
            address="Toshkent sh., Chilonzor tumani, 9-kvartal",
            description="300-500 kishilik hashamatli to'y zali. Barcha qulayliklar va zamonaviy akustika tizimi mavjud.",
            max_capacity=500,
            required_deposit=Decimal("5000000.00")
        )

        # 5. Create Shifts for Wedding Hall
        self.stdout.write("Creating shifts...")
        shift_lunch = Shift.objects.create(
            hall=hall, 
            name="Tushlik (Lunch)", 
            start_time=time(11, 0), 
            end_time=time(15, 0)
        )
        shift_dinner = Shift.objects.create(
            hall=hall, 
            name="Kechki (Dinner)", 
            start_time=time(18, 0), 
            end_time=time(23, 0)
        )

        # 6. Create Packages for Wedding Hall
        self.stdout.write("Creating packages...")
        pkg300 = Package.objects.create(
            hall=hall, 
            guest_count=300, 
            price=Decimal("45000000.00"), 
            description="300 kishilik standart to'y paketi (taom va shirinliklar bilan)."
        )
        pkg400 = Package.objects.create(
            hall=hall, 
            guest_count=400, 
            price=Decimal("60000000.00"), 
            description="400 kishilik lyuks to'y paketi (pre-cooked salatlar, premium menyu)."
        )

        # 7. Create Decoration
        self.stdout.write("Creating decorations...")
        dec_gold = Decoration.objects.create(
            hall=hall, 
            name="Oltin kuz dekoratsiyasi", 
            additional_price=Decimal("5000000.00")
        )

        # 8. Create Bar
        self.stdout.write("Creating bar...")
        bar = Bar.objects.create(
            owner=owner2,
            region=toshkent_sh,
            district=yunusobod_dist,
            name="Retro Bar & Lounge",
            address="Toshkent sh., Yunusobod tumani, Amir Temur ko'chasi",
            description="Kuyov navkar va do'stlar yig'ilishi uchun soatlik ijaraga beriladigan shinam bar.",
            capacity=50,
            price_per_hour=Decimal("300000.00"),
            required_deposit=Decimal("1000000.00")
        )

        # 9. Create Bookings
        self.stdout.write("Creating test bookings...")
        # Confirmed Hall Booking (10 days from now)
        hb = HallBooking.objects.create(
            user=client1,
            hall=hall,
            shift=shift_dinner,
            package=pkg300,
            decoration=dec_gold,
            date=date.today() + timedelta(days=10),
            total_price=Decimal("50000000.00"),  # pkg300 (45M) + dec_gold (5M)
            deposit_amount=Decimal("5000000.00"),
            is_deposit_paid=True,
            status="CONFIRMED"
        )

        # Pending Bar Booking (5 days from now, from 18:00 to 22:00)
        bb = BarBooking.objects.create(
            user=client1,
            bar=bar,
            date=date.today() + timedelta(days=5),
            start_time=time(18, 0),
            end_time=time(22, 0),
            total_price=Decimal("1200000.00"),  # 4 hours * 300 000
            deposit_amount=Decimal("1000000.00"),
            is_deposit_paid=False,
            status="PENDING"
        )

        self.stdout.write(self.style.SUCCESS("Database successfully seeded with test data including Regions & Districts!"))
