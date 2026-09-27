"""
Database seed management command for Toyxona platform.
Populates exactly 10 realistic Wedding Halls and 10 Bars/Lounges with
Uzbekistan (Tashkent) context, pricing, amenities, shifts, packages, and gallery images.

Usage:
    python manage.py seed_venues
    python manage.py seed_venues --clear
"""

from datetime import time
from decimal import Decimal
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from bookings.models import BarBooking, HallBooking
from venues.models import (
    Bar,
    Decoration,
    District,
    Media,
    Package,
    Region,
    Shift,
    ShiftBlock,
    WeddingHall,
)

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds database with exactly 10 realistic Tashkent Wedding Halls and 10 Bars/Lounges"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing wedding halls, bars, and their bookings before seeding",
        )

    def handle(self, *args, **options):
        clear_existing = options.get("clear", False)

        self.stdout.write(self.style.NOTICE("==> Starting Venue Seeding Process..."))

        with transaction.atomic():
            # 1. Resolve Region & Districts
            toshkent_region = Region.objects.filter(name__icontains="Toshkent shahri").first()
            if not toshkent_region:
                toshkent_region, _ = Region.objects.get_or_create(
                    name="Toshkent shahri",
                    defaults={"order": 1},
                )
            self.stdout.write(f"✓ Region: {toshkent_region.name} (id={toshkent_region.id})")

            def get_or_make_district(name_query: str) -> District:
                dist = District.objects.filter(region=toshkent_region, name__icontains=name_query).first()
                if not dist:
                    dist = District.objects.create(
                        region=toshkent_region,
                        name=f"{name_query.title()} tumani",
                        order=1,
                    )
                return dist

            # 2. Get or Create Dedicated Venue Owners
            owner_hall, _ = User.objects.get_or_create(
                phone_number="+998901112233",
                defaults={
                    "first_name": "Ahror",
                    "last_name": "Umarov",
                    "role": User.Role.VENUE_OWNER,
                    "is_verified": True,
                },
            )
            if not owner_hall.has_usable_password():
                owner_hall.set_password("toyxona2026")
                owner_hall.save()

            owner_bar, _ = User.objects.get_or_create(
                phone_number="+998904445566",
                defaults={
                    "first_name": "Sardor",
                    "last_name": "Karimov",
                    "role": User.Role.VENUE_OWNER,
                    "is_verified": True,
                },
            )
            if not owner_bar.has_usable_password():
                owner_bar.set_password("toyxona2026")
                owner_bar.save()

            self.stdout.write("✓ Venue owner accounts verified.")

            # 3. Optional Cleanup
            if clear_existing:
                self.stdout.write(self.style.WARNING("Clearing existing venues and bookings (--clear requested)..."))
                HallBooking.objects.all().delete()
                BarBooking.objects.all().delete()
                ShiftBlock.objects.all().delete()
                Decoration.objects.all().delete()
                Package.objects.all().delete()
                Shift.objects.all().delete()
                Media.objects.all().delete()
                WeddingHall.objects.all().delete()
                Bar.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("✓ Old venue data successfully removed."))

            # 4. Realistic 10 Wedding Halls Dataset
            halls_data: List[Dict[str, Any]] = [
                {
                    "name": "Yakkasaroy Wedding Hall",
                    "district": "Yakkasaroy",
                    "address": "Toshkent sh., Yakkasaroy tumani, Shota Rustaveli ko'chasi, 84-uy",
                    "description": "Toshkent markazida joylashgan eng nufuzli va muhtasham to'yxonalardan biri. Sharqona hashamat va zamonaviy Yevropa arxitekturasi uyg'unligi, billur lyustralar va baland shiftlar to'yingizga betakror shukuh bag'ishlaydi.",
                    "max_capacity": 800,
                    "required_deposit": Decimal("5000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1200&q=80",
                        "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "Katta LED ekran (P3)",
                        "Professional L-Acoustics ovoz tizimi",
                        "Avtoturargoh (200 o'rin)",
                        "Qizil yo'lak",
                        "Konditsioner & ventilyatsiya",
                        "Yuqori tezlikdagi Wi-Fi",
                        "Yorug'lik effektlari",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(13, 0)},
                        {"name": "Kechki to'y bazmi", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 400, "price": Decimal("56000000.00"), "desc": "Klassik to'y paketi: milliy va Yevropa taomlari, shirinliklar, xizmat ko'rsatish"},
                        {"guests": 600, "price": Decimal("84000000.00"), "desc": "Premium tantana paketi: keng assortiment, sarxil mevalar, maxsus servis"},
                        {"guests": 800, "price": Decimal("112000000.00"), "desc": "Royal VIP paketi: barcha xizmatlar, individual menyu va yuqori darajadagi xizmat"},
                    ],
                    "decorations": [
                        {"name": "Klassik oltin arka va billur shamdonlar", "price": Decimal("3000000.00")},
                        {"name": "Jonli gullardan premium kompozitsiya", "price": Decimal("5500000.00")},
                    ],
                },
                {
                    "name": "Versal To'yxonasi",
                    "district": "Shayxontohur",
                    "address": "Toshkent sh., Shayxontohur tumani, Sebzor ko'chasi, 2-uy",
                    "description": "Versal saroyi uslubidagi hashamatli dekorlar, oltin zarhallangan ustunlar va keng raqs maydoni. Yuqori martabali mehmonlar va unutilmas tantanalar uchun ideal maskan.",
                    "max_capacity": 700,
                    "required_deposit": Decimal("4000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1545232979-8bf68ee9b1af?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?auto=format&fit=crop&w=1200&q=80",
                        "https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov maxsus xonasi",
                        "2 ta ulkan LED ekran",
                        "Konsert ovoz tizimi",
                        "VIP mehmonlar zali",
                        "Avtoturargoh (180 o'rin)",
                        "Qizil yo'lak",
                        "Konditsioner",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 30), "end": time(13, 0)},
                        {"name": "Kechki bazm", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 300, "price": Decimal("42000000.00"), "desc": "Standart to'y menyusi va to'liq servis"},
                        {"guests": 500, "price": Decimal("70000000.00"), "desc": "Versal Lüks to'y paketi"},
                        {"guests": 700, "price": Decimal("98000000.00"), "desc": "Grand Royal tantana paketi"},
                    ],
                    "decorations": [
                        {"name": "Billur lyustralar va oq gullar arkasi", "price": Decimal("4000000.00")},
                        {"name": "Neoklassik zamonaviy dizayn", "price": Decimal("3000000.00")},
                    ],
                },
                {
                    "name": "Osiyo Grand",
                    "district": "Yunusobod",
                    "address": "Toshkent sh., Yunusobod tumani, Yangi shahar ko'chasi, 15-uy",
                    "description": "Yunusobod tumanidagi zamonaviy va keng tantanalar saroyi. Akustikasi a'lo darajada ishlangan bo'lib, har bir marosimni shohona o'tishini kafolatlaydi.",
                    "max_capacity": 650,
                    "required_deposit": Decimal("3500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "P4 LED ekran",
                        "Professional yoritish tizimi",
                        "Avtoturargoh (150 o'rin)",
                        "Garderob",
                        "Konditsioner",
                        "Bolalar maydonchasi",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(12, 30)},
                        {"name": "Kechki to'y", "start": time(18, 0), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 350, "price": Decimal("45000000.00"), "desc": "Klassik tantana menyusi"},
                        {"guests": 500, "price": Decimal("65000000.00"), "desc": "Osiyo Grand maxsus to'y paketi"},
                        {"guests": 650, "price": Decimal("85000000.00"), "desc": "VIP to'liq tantana menyusi"},
                    ],
                    "decorations": [
                        {"name": "Jonli atirgullar va shaffof stollar", "price": Decimal("3500000.00")},
                        {"name": "Sharqona milliy naqshlar dekoratsiyasi", "price": Decimal("2500000.00")},
                    ],
                },
                {
                    "name": "Mumtoz Tantanalar Saroyi",
                    "district": "Chilonzor",
                    "address": "Toshkent sh., Chilonzor tumani, Bunyodkor shoh ko'chasi, 28-uy",
                    "description": "Toshkentdagi eng katta va ko'rkam to'yxonalardan biri. 900 kishigacha bo'lgan to'y va katta marosimlar uchun qulay infratuzilma va keng zal.",
                    "max_capacity": 900,
                    "required_deposit": Decimal("6000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1464366400600-7168b8af9bc3?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "2 ta kelin-kuyov xonasi",
                        "Katta multimedia sahnasi",
                        "Avtoturargoh (300 o'rin)",
                        "Maxsus liftlar",
                        "Konditsioner",
                        "Ona-bola xonasi",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(13, 0)},
                        {"name": "Kechki to'y bazmi", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 450, "price": Decimal("67500000.00"), "desc": "Mumtoz saroy paketi"},
                        {"guests": 700, "price": Decimal("105000000.00"), "desc": "Shohona to'y paketi"},
                        {"guests": 900, "price": Decimal("135000000.00"), "desc": "Imperial Grand paketi"},
                    ],
                    "decorations": [
                        {"name": "Oq gulli arkalar va panno", "price": Decimal("4500000.00")},
                        {"name": "Podium va xiyobon yoritgichlari", "price": Decimal("3000000.00")},
                    ],
                },
                {
                    "name": "Navro'z Saroyi",
                    "district": "Mirobod",
                    "address": "Toshkent sh., Mirobod tumani, Shahrisabz ko'chasi, 40-uy",
                    "description": "Mirobod markazida, shahar manzarasiga ega muhtasham saroy. Milliy an'analar va yevropacha servis uyg'unlashgan fayzli maskan.",
                    "max_capacity": 550,
                    "required_deposit": Decimal("4000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1527529482837-4698179dc6ce?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "LED ekran",
                        "Jonli orkestr maydoni",
                        "Avtoturargoh (120 o'rin)",
                        "Konditsioner",
                        "Wi-Fi",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(12, 30)},
                        {"name": "Kechki tantana", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 250, "price": Decimal("35000000.00"), "desc": "Ixcham to'y paketi"},
                        {"guests": 400, "price": Decimal("56000000.00"), "desc": "Navro'z maxsus menyusi"},
                        {"guests": 550, "price": Decimal("77000000.00"), "desc": "Lüks to'y paketi"},
                    ],
                    "decorations": [
                        {"name": "Zarhal gulli kompozitsiya", "price": Decimal("3200000.00")},
                        {"name": "Zamonaviy minimalist arka", "price": Decimal("2200000.00")},
                    ],
                },
                {
                    "name": "Ezidiyor To'yxonasi",
                    "district": "Shayxontohur",
                    "address": "Toshkent sh., Shayxontohur tumani, Labzak ko'chasi, 114-uy",
                    "description": "Labzak hududidagi eng mashhur va obro'li to'yxonalardan biri. Keng ustunsiz zal, zamonaviy ventilyatsiya va yuqori darajali oshpazlar jamoasi.",
                    "max_capacity": 850,
                    "required_deposit": Decimal("5000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1519167758481-83f550bb49b3?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "Katta LED ekran",
                        "Qizil yo'lak",
                        "Avtoturargoh (220 o'rin)",
                        "Yuqori darajadagi konditsioner",
                        "Fotozona",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(13, 0)},
                        {"name": "Nikoh oqshomi", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 400, "price": Decimal("58000000.00"), "desc": "Ezidiyor standart paketi"},
                        {"guests": 600, "price": Decimal("87000000.00"), "desc": "Ezidiyor tantanasi"},
                        {"guests": 850, "price": Decimal("123000000.00"), "desc": "Grand Ezidiyor VIP"},
                    ],
                    "decorations": [
                        {"name": "Yaltiroq shisha dekoratsiyalar", "price": Decimal("4000000.00")},
                        {"name": "Oq orxideyalar arkasi", "price": Decimal("5000000.00")},
                    ],
                },
                {
                    "name": "Shohona Saroy",
                    "district": "Uchtepa",
                    "address": "Toshkent sh., Uchtepa tumani, Lutfiy ko'chasi, 79-uy",
                    "description": "Sharqona nafislik va zamonaviy uslubda bezatilgan shinam zal. Shirin xotiralar va quvonchli lahzalar uchun eng maqbul maskan.",
                    "max_capacity": 600,
                    "required_deposit": Decimal("3500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1544078751-58fee2d8a03b?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "LED ekran",
                        "Akustik ovoz tizimi",
                        "Avtoturargoh (120 o'rin)",
                        "Konditsioner",
                        "Qizil gilam",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 30), "end": time(13, 0)},
                        {"name": "Nikoh bazmi", "start": time(18, 0), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 300, "price": Decimal("39000000.00"), "desc": "Klassik to'y menyusi"},
                        {"guests": 450, "price": Decimal("58500000.00"), "desc": "Shohona maxsus paketi"},
                        {"guests": 600, "price": Decimal("78000000.00"), "desc": "Premium to'y paketi"},
                    ],
                    "decorations": [
                        {"name": "Sharqona naqshli gul arkasi", "price": Decimal("2800000.00")},
                        {"name": "Yorug'likli fotoramkalar", "price": Decimal("1800000.00")},
                    ],
                },
                {
                    "name": "Zarafshon Grand Hall",
                    "district": "Mirzo Ulug'bek",
                    "address": "Toshkent sh., Mirzo Ulug'bek tumani, Mustaqillik shoh ko'chasi, 55-uy",
                    "description": "Toshkent markazida joylashgan tarixiy va muhtasham zal. Katta tantanalar, konsertlar va yuqori darajadagi nikoh to'ylari uchun mo'ljallangan.",
                    "max_capacity": 750,
                    "required_deposit": Decimal("4500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1544078751-58fee2d8a03b?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1511285560929-80b456fea0bc?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "Katta LED ekran",
                        "Konsert ovoz tizimi",
                        "Avtoturargoh (200 o'rin)",
                        "VIP qabulxona",
                        "Konditsioner",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(12, 30)},
                        {"name": "Kechki bazm", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 350, "price": Decimal("52500000.00"), "desc": "Zarafshon standart"},
                        {"guests": 550, "price": Decimal("82500000.00"), "desc": "Zarafshon Premium"},
                        {"guests": 750, "price": Decimal("112500000.00"), "desc": "Royal Grand menyusi"},
                    ],
                    "decorations": [
                        {"name": "Oltin shamdonlar va billur bezaklar", "price": Decimal("3800000.00")},
                        {"name": "Zamonaviy shou yoritish bezaklari", "price": Decimal("4200000.00")},
                    ],
                },
                {
                    "name": "Oqsaroy Banquet Hall",
                    "district": "Olmazor",
                    "address": "Toshkent sh., Olmazor tumani, Qorasaroy ko'chasi, 203-uy",
                    "description": "Oq va kumush ranglar jilosida yaratilgan qulay tantanalar saroyi. Oila a'zolari va yaqinlar bilan go'zal to'y o'tkazish uchun ajoyib maskan.",
                    "max_capacity": 500,
                    "required_deposit": Decimal("3000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1532712938310-34cb3982ef74?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "LED ekran",
                        "Musiqiy apparatura",
                        "Avtoturargoh (100 o'rin)",
                        "Konditsioner",
                        "Qizil yo'lak",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(12, 30)},
                        {"name": "Kechki to'y", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 250, "price": Decimal("32500000.00"), "desc": "Ixcham to'y paketi"},
                        {"guests": 380, "price": Decimal("49400000.00"), "desc": "Oqsaroy bayramona paketi"},
                        {"guests": 500, "price": Decimal("65000000.00"), "desc": "To'liq VIP to'y menyusi"},
                    ],
                    "decorations": [
                        {"name": "Oq gullar va shaffof arka", "price": Decimal("2500000.00")},
                        {"name": "Klassik fotosessiya zonasi", "price": Decimal("1500000.00")},
                    ],
                },
                {
                    "name": "Sayram Wedding Hall",
                    "district": "Sergeli",
                    "address": "Toshkent sh., Sergeli tumani, Yangi Sergeli ko'chasi, 42-uy",
                    "description": "Sergeli tumanidagi eng yirik to'y maskanlaridan biri. Keng yoritilgan zal, yangi bezaklar va professional servis jamoasi xizmatingizda.",
                    "max_capacity": 700,
                    "required_deposit": Decimal("4000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1519225429878-577e38318464?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1545232979-8bf68ee9b1af?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Kelin-kuyov xonasi",
                        "LED ekran",
                        "Professional ovoz tizimi",
                        "Avtoturargoh (200 o'rin)",
                        "Konditsioner",
                        "Bolalar xonasi",
                    ],
                    "shifts": [
                        {"name": "Nahor oshi", "start": time(6, 0), "end": time(13, 0)},
                        {"name": "Nikoh oqshomi", "start": time(17, 30), "end": time(23, 0)},
                    ],
                    "packages": [
                        {"guests": 300, "price": Decimal("39000000.00"), "desc": "Sayram standart to'y paketi"},
                        {"guests": 500, "price": Decimal("65000000.00"), "desc": "Sayram tantanasi"},
                        {"guests": 700, "price": Decimal("91000000.00"), "desc": "Lüks to'y paketi"},
                    ],
                    "decorations": [
                        {"name": "Gulli arka va billur chiroqlar", "price": Decimal("3000000.00")},
                        {"name": "Podium va shou dekoratsiyasi", "price": Decimal("2200000.00")},
                    ],
                },
            ]

            # 5. Realistic 10 Bars & Lounges Dataset
            bars_data: List[Dict[str, Any]] = [
                {
                    "name": "Steam Bar & Lounge",
                    "district": "Mirobod",
                    "address": "Toshkent sh., Mirobod tumani, Nukus ko'chasi, 29-uy",
                    "description": "Steam-punk uslubidagi interyerga ega zamonaviy bar. Mualliflik kokteyllari, mazali Yevropa taomlari va har hafta oxiri jonli DJ chiqishlari.",
                    "capacity": 80,
                    "price_per_hour": Decimal("450000.00"),
                    "required_deposit": Decimal("1500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Craft ichimliklar",
                        "DJ booth",
                        "Kalyan (Shisha)",
                        "Jonli musiqa",
                        "Wi-Fi",
                        "Bar peshtaxtasi",
                        "VIP xona",
                    ],
                },
                {
                    "name": "The Irish Pub Tashkent",
                    "district": "Yakkasaroy",
                    "address": "Toshkent sh., Yakkasaroy tumani, Shota Rustaveli ko'chasi, 22-uy",
                    "description": "Haqiqiy Irlandiya pubi muhiti. Jonli rok va bluz musiqasi, sport musobaqalari translyatsiyasi va keng turdagi xalqaro ichimliklar.",
                    "capacity": 110,
                    "price_per_hour": Decimal("400000.00"),
                    "required_deposit": Decimal("1000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Jonli musiqa",
                        "Katta sport ekranlari",
                        "Craft pivo",
                        "Dart va bilyard",
                        "Wi-Fi",
                        "Ochiq terasa",
                    ],
                },
                {
                    "name": "Sky Lounge Tashkent",
                    "district": "Mirzo Ulug'bek",
                    "address": "Toshkent sh., Mirzo Ulug'bek tumani, Mustaqillik shoh ko'chasi, 107-uy (18-qavat)",
                    "description": "Shahar panoramasi kaftdek ko'rinadigan hashamatli rooftop bar. Romantik kechki ovqatlar, korporativ uchrashuvlar va maxsus oqshomlar maskani.",
                    "capacity": 120,
                    "price_per_hour": Decimal("850000.00"),
                    "required_deposit": Decimal("2500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1578474846511-04ba529f0b88?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Rooftop panorama",
                        "Mualliflik kokteyllari",
                        "Jonli saksofon musiqasi",
                        "VIP zallar",
                        "Kalyan menyusi",
                        "Valet parking",
                    ],
                },
                {
                    "name": "Black Bear Pub",
                    "district": "Mirobod",
                    "address": "Toshkent sh., Mirobod tumani, Taras Shevchenko ko'chasi, 38-uy",
                    "description": "Toshkentning eng sevimli gastropublaridan biri. Mazali steyklar, mualliflik pivo menyusi va samimiy do'stona muhit.",
                    "capacity": 90,
                    "price_per_hour": Decimal("380000.00"),
                    "required_deposit": Decimal("1000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1551024709-8f23befc6f87?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1572116469696-31de0f17cc34?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Craft ichimliklar",
                        "Grill va steyklar",
                        "Jonli akustik musiqa",
                        "Wi-Fi",
                        "Yozgi maydoncha",
                    ],
                },
                {
                    "name": "Panorama Rooftop Bar",
                    "district": "Shayxontohur",
                    "address": "Toshkent sh., Shayxontohur tumani, Navoiy shoh ko'chasi, 1A-uy",
                    "description": "Poytaxt markazidagi hashamatli rooftop barlardan biri. Ochiq osmon ostidagi kechalar, eng yaxshi DJlar to'plami va nafis taomnoma.",
                    "capacity": 140,
                    "price_per_hour": Decimal("750000.00"),
                    "required_deposit": Decimal("2000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1578474846511-04ba529f0b88?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Rooftop ochiq maydon",
                        "DJ booth",
                        "Kalyan (Shisha)",
                        "Kokteyl bar",
                        "Lounge zonalar",
                        "Yuqori tezlikdagi Wi-Fi",
                    ],
                },
                {
                    "name": "Coda Lounge Bar",
                    "district": "Yunusobod",
                    "address": "Toshkent sh., Yunusobod tumani, Amir Temur shoh ko'chasi, 60-uy",
                    "description": "Zamonaviy neoklassik uslubdagi shinam lounge bar. Tinch suhbatlar, qulay yumshoq mebellar va keng turdagi kalyan hamda ichimliklar.",
                    "capacity": 75,
                    "price_per_hour": Decimal("500000.00"),
                    "required_deposit": Decimal("1500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1525268323446-0505b6fe7778?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1543007630-9710e4a00a20?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Premium kalyan",
                        "Shinam divanlar",
                        "Fonga musiqa",
                        "VIP kabinalar",
                        "Wi-Fi",
                        "Konditsioner",
                    ],
                },
                {
                    "name": "Studio Cafe & Lounge",
                    "district": "Yakkasaroy",
                    "address": "Toshkent sh., Yakkasaroy tumani, Bobur ko'chasi, 45-uy",
                    "description": "Ijodiy muhitga ega bo'lgan loft uslubidagi lounge. Qahva ixlosmandlari, do'stona davralar va kichik tug'ilgan kun tadbirlari uchun ideal.",
                    "capacity": 65,
                    "price_per_hour": Decimal("350000.00"),
                    "required_deposit": Decimal("1000000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1543007630-9710e4a00a20?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1525268323446-0505b6fe7778?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Qahva bari",
                        "Lounge musiqa",
                        "Stol o'yinlari",
                        "Wi-Fi",
                        "Konditsioner",
                        "Ochiq balkon",
                    ],
                },
                {
                    "name": "The Bar Tashkent",
                    "district": "Mirobod",
                    "address": "Toshkent sh., Mirobod tumani, Sodiq Azimov ko'chasi, 52-uy",
                    "description": "Poytaxtning gavjum markazida joylashgan premium bar. Jahon standartlaridagi bar xizmati, professional miksologlar va jonli jazz oqshomlari.",
                    "capacity": 95,
                    "price_per_hour": Decimal("600000.00"),
                    "required_deposit": Decimal("1800000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1560624052-449f5ddf0c31?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Jonli jazz musiqa",
                        "Premium kokteyllar",
                        "Katta bar peshtaxtasi",
                        "Wi-Fi",
                        "Yopiq VIP zal",
                    ],
                },
                {
                    "name": "Sette Restaurant & Bar",
                    "district": "Chilonzor",
                    "address": "Toshkent sh., Chilonzor tumani, Muqimiy ko'chasi, 166-uy",
                    "description": "Italiya va O'rta yer dengizi oshxonasi uyg'unlashgan zamonaviy bar-restoran. Yirik oilaviy tantanalar, yubileylar va do'stona yig'inlar uchun qulay.",
                    "capacity": 130,
                    "price_per_hour": Decimal("550000.00"),
                    "required_deposit": Decimal("1500000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1560624052-449f5ddf0c31?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "Italiya oshxonasi",
                        "Sharob kartasi",
                        "Jonli musiqa",
                        "Bolalar burchagi",
                        "Avtoturargoh",
                        "Wi-Fi",
                    ],
                },
                {
                    "name": "One More Bar & Lounge",
                    "district": "Yunusobod",
                    "address": "Toshkent sh., Yunusobod tumani, Osiyo ko'chasi, 17-uy",
                    "description": "Yunusobod markazidagi yoshlar va do'stona kompaniyalar uchun eng sevimli maskan. Energetik musiqa, mazali burger va snecklar hamda ajoyib atmosfera.",
                    "capacity": 85,
                    "price_per_hour": Decimal("420000.00"),
                    "required_deposit": Decimal("1200000.00"),
                    "cover_image": "https://images.unsplash.com/photo-1574096079513-d8259312b785?auto=format&fit=crop&w=1200&q=80",
                    "gallery": [
                        "https://images.unsplash.com/photo-1514933651103-005eec06c04b?auto=format&fit=crop&w=1200&q=80",
                    ],
                    "amenities": [
                        "DJ kechalari",
                        "PlayStation zonasi",
                        "Kalyan menyusi",
                        "Craft ichimliklar",
                        "Wi-Fi",
                        "Konditsioner",
                    ],
                },
            ]

            # 6. Execute Idempotent Wedding Hall Seeding
            self.stdout.write("--> Seeding Wedding Halls...")
            for hall_info in halls_data:
                dist = get_or_make_district(hall_info["district"])
                hall, created = WeddingHall.objects.update_or_create(
                    name=hall_info["name"],
                    defaults={
                        "owner": owner_hall,
                        "region": toshkent_region,
                        "district": dist,
                        "address": hall_info["address"],
                        "description": hall_info["description"],
                        "max_capacity": hall_info["max_capacity"],
                        "required_deposit": hall_info["required_deposit"],
                        "cover_image": hall_info["cover_image"],
                        "amenities": hall_info["amenities"],
                    },
                )
                action_str = "Created" if created else "Updated"
                self.stdout.write(f"   [Hall] {action_str}: {hall.name} ({hall.max_capacity} o'rin, {dist.name})")

                # Shifts
                for shift_info in hall_info.get("shifts", []):
                    Shift.objects.update_or_create(
                        hall=hall,
                        name=shift_info["name"],
                        defaults={
                            "start_time": shift_info["start"],
                            "end_time": shift_info["end"],
                            "is_active": True,
                        },
                    )

                # Packages
                for pkg_info in hall_info.get("packages", []):
                    Package.objects.update_or_create(
                        hall=hall,
                        guest_count=pkg_info["guests"],
                        defaults={
                            "price": pkg_info["price"],
                            "description": pkg_info["desc"],
                        },
                    )

                # Decorations
                for dec_info in hall_info.get("decorations", []):
                    Decoration.objects.update_or_create(
                        hall=hall,
                        name=dec_info["name"],
                        defaults={
                            "additional_price": dec_info["price"],
                        },
                    )

                # Gallery Media
                for pos, img_url in enumerate(hall_info.get("gallery", []), start=1):
                    Media.objects.update_or_create(
                        hall=hall,
                        position=pos,
                        defaults={
                            "image": img_url,
                            "type": "image",
                            "is_main": (pos == 1),
                        },
                    )

            # 7. Execute Idempotent Bar Seeding
            self.stdout.write("--> Seeding Bars & Lounges...")
            for bar_info in bars_data:
                dist = get_or_make_district(bar_info["district"])
                bar, created = Bar.objects.update_or_create(
                    name=bar_info["name"],
                    defaults={
                        "owner": owner_bar,
                        "region": toshkent_region,
                        "district": dist,
                        "address": bar_info["address"],
                        "description": bar_info["description"],
                        "capacity": bar_info["capacity"],
                        "price_per_hour": bar_info["price_per_hour"],
                        "required_deposit": bar_info["required_deposit"],
                        "cover_image": bar_info["cover_image"],
                        "amenities": bar_info["amenities"],
                    },
                )
                action_str = "Created" if created else "Updated"
                self.stdout.write(f"   [Bar]  {action_str}: {bar.name} ({bar.capacity} o'rin, {bar.price_per_hour} UZS/soat)")

                # Gallery Media
                for pos, img_url in enumerate(bar_info.get("gallery", []), start=1):
                    Media.objects.update_or_create(
                        bar=bar,
                        position=pos,
                        defaults={
                            "image": img_url,
                            "type": "image",
                            "is_main": (pos == 1),
                        },
                    )

        # 8. Verification & Terminal Report
        hall_count = WeddingHall.objects.count()
        bar_count = Bar.objects.count()
        shift_count = Shift.objects.count()
        package_count = Package.objects.count()
        decoration_count = Decoration.objects.count()
        media_count = Media.objects.count()

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("DATABASE SEED COMPLETED SUCCESSFULLY!"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"• Wedding Halls (To'y zallari): {hall_count}")
        self.stdout.write(f"• Bars & Lounges:             {bar_count}")
        self.stdout.write(f"• Hall Shifts (Smenalar):     {shift_count}")
        self.stdout.write(f"• Pricing Packages:           {package_count}")
        self.stdout.write(f"• Decoration Addons:          {decoration_count}")
        self.stdout.write(f"• Media Gallery Items:        {media_count}")
        self.stdout.write("=" * 60 + "\n")
