#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Materiallar qo'shish skripti
Bu skript bazaga 10ta mahsulot qo'shadi
"""

import asyncio
import sys
import os
from decimal import Decimal

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.warehouse.materials import create_material

# 10ta mahsulot ma'lumotlari
PRODUCTS = [
    {
        "name": "Optik kabel (Fiber Optic Cable)",
        "price": Decimal("15000.00"),
        "description": "Yuksak tezlikli internet ulanishi uchun optik kabel. Uzunligi: 100m",
        "quantity": 50,
        "serial_number": "OPT-001"
    },
    {
        "name": "Router TP-Link Archer C7",
        "price": Decimal("250000.00"),
        "description": "Wi-Fi 6 router, 5 GHz va 2.4 GHz tezliklarida ishlaydi",
        "quantity": 25,
        "serial_number": "RT-TP-001"
    },
    {
        "name": "Switch 24-port Gigabit",
        "price": Decimal("180000.00"),
        "description": "24 portli Gigabit Ethernet switch, ofis tarmoqlari uchun",
        "quantity": 15,
        "serial_number": "SW-24-001"
    },
    {
        "name": "Kabel CAT6 UTP",
        "price": Decimal("8000.00"),
        "description": "CAT6 UTP kabel, 305m rulon, yuqori tezlikli ma'lumot uzatish uchun",
        "quantity": 100,
        "serial_number": "CAT6-001"
    },
    {
        "name": "Modem Huawei HG8245H",
        "price": Decimal("120000.00"),
        "description": "GPON modem, optik internet ulanishi uchun",
        "quantity": 30,
        "serial_number": "MD-HW-001"
    },
    {
        "name": "Access Point Ubiquiti UniFi",
        "price": Decimal("350000.00"),
        "description": "Wi-Fi access point, katta hududlarni qamrov qilish uchun",
        "quantity": 20,
        "serial_number": "AP-UB-001"
    },
    {
        "name": "RJ45 konnektorlar (100 dona)",
        "price": Decimal("15000.00"),
        "description": "RJ45 konnektorlar paketi, 100 dona",
        "quantity": 200,
        "serial_number": "RJ45-100"
    },
    {
        "name": "Patch panel 24-port",
        "price": Decimal("45000.00"),
        "description": "24 portli patch panel, server xonalari uchun",
        "quantity": 40,
        "serial_number": "PP-24-001"
    },
    {
        "name": "UPS APC Smart-UPS 1000VA",
        "price": Decimal("800000.00"),
        "description": "UPS qurilma, elektr uzilishlarida qurilmalarni himoya qilish uchun",
        "quantity": 10,
        "serial_number": "UPS-APC-001"
    },
    {
        "name": "Kabel kanal plastik (2m)",
        "price": Decimal("5000.00"),
        "description": "Plastik kabel kanal, 2 metr uzunlikda",
        "quantity": 500,
        "serial_number": "KC-2M-001"
    }
]

async def add_materials_to_database():
    """Bazaga materiallarni qo'shish funksiyasi"""
    print("🚀 Materiallar qo'shilmoqda...")
    print("=" * 50)
    
    success_count = 0
    error_count = 0
    
    for i, product in enumerate(PRODUCTS, 1):
        try:
            print(f"📦 {i}/10 - {product['name']} qo'shilmoqda...")
            
            result = await create_material(
                name=product["name"],
                price=product["price"],
                description=product["description"],
                quantity=product["quantity"],
                serial_number=product["serial_number"]
            )
            
            print(f"✅ Muvaffaqiyatli qo'shildi! ID: {result['id']}")
            print(f"   📊 Miqdor: {result['quantity']} dona")
            print(f"   💰 Narx: {result['price']} so'm")
            print()
            
            success_count += 1
            
        except Exception as e:
            print(f"❌ Xatolik: {product['name']} qo'shishda xatolik yuz berdi")
            print(f"   🔍 Xatolik tafsiloti: {str(e)}")
            print()
            error_count += 1
    
    print("=" * 50)
    print("📊 NATIJA:")
    print(f"✅ Muvaffaqiyatli qo'shilgan: {success_count} ta")
    print(f"❌ Xatolik bilan: {error_count} ta")
    print(f"📈 Jami: {len(PRODUCTS)} ta")
    
    if success_count == len(PRODUCTS):
        print("\n🎉 Barcha materiallar muvaffaqiyatli qo'shildi!")
    elif success_count > 0:
        print(f"\n⚠️  {success_count} ta material qo'shildi, {error_count} ta xatolik bilan")
    else:
        print("\n💥 Hech qanday material qo'shilmadi!")

async def main():
    """Asosiy funksiya"""
    print("🏭 ALFABOT - Materiallar qo'shish skripti")
    print("=" * 50)
    print(f"📋 Jami {len(PRODUCTS)} ta mahsulot qo'shiladi:")
    print()
    
    # Mahsulotlar ro'yxatini ko'rsatish
    for i, product in enumerate(PRODUCTS, 1):
        print(f"{i:2d}. {product['name']}")
        print(f"    💰 Narx: {product['price']} so'm")
        print(f"    📦 Miqdor: {product['quantity']} dona")
        print(f"    🔢 Seriya: {product['serial_number']}")
        print()
    
    # Tasdiqlash
    confirm = input("❓ Davom etishni xohlaysizmi? (y/n): ").lower().strip()
    if confirm not in ['y', 'yes', 'ha', 'h']:
        print("❌ Operatsiya bekor qilindi.")
        return
    
    # Materiallarni qo'shish
    await add_materials_to_database()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⏹️  Operatsiya foydalanuvchi tomonidan to'xtatildi.")
    except Exception as e:
        print(f"\n💥 Umumiy xatolik: {str(e)}")
        sys.exit(1)
