#!/usr/bin/env python3
"""
Script para probar el servicio desplegado en Render
"""

import requests
import json
import sys

def test_service(base_url):
    """Prueba los endpoints del servicio."""

    print(f"🧪 Probando servicio en: {base_url}\n")

    # Test 1: Health check
    print("=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"✅ Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()

    # Test 2: Status endpoint
    print("=" * 60)
    print("TEST 2: Bot Status")
    print("=" * 60)
    try:
        response = requests.get(f"{base_url}/status", timeout=10)
        print(f"✅ Status: {response.status_code}")
        if response.status_code == 200:
            status = response.json()
            print(f"   Bot Status: {status.get('status')}")
            print(f"   Last Run: {status.get('last_run')}")
            print(f"   Next Run: {status.get('next_scheduled_run')}")

            if status.get('last_run_stats'):
                stats = status['last_run_stats']
                print(f"\n   📊 Last Run Stats:")
                print(f"      Total Found: {stats.get('total_found', 'N/A')}")
                print(f"      New Listings: {stats.get('new_listings', 'N/A')}")
                print(f"      Errors: {stats.get('errors', 'N/A')}")
                print(f"      Duration: {stats.get('duration', 'N/A')}")
                if 'error' in stats:
                    print(f"      ⚠️ Error: {stats['error']}")
        else:
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print()

    # Test 3: Trigger manual run
    print("=" * 60)
    print("TEST 3: Manual Trigger (Optional)")
    print("=" * 60)
    trigger = input("¿Quieres disparar una ejecución manual? (y/N): ").strip().lower()

    if trigger == 'y':
        print("🚀 Disparando ejecución manual...")
        try:
            response = requests.get(f"{base_url}/run", timeout=10)
            print(f"✅ Status: {response.status_code}")
            if response.status_code == 202:
                print("   ✓ Bot iniciado. Espera 1-2 minutos y revisa /status")
            else:
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"❌ Error: {e}")
    else:
        print("⏭️ Saltado")

    print("\n" + "=" * 60)
    print("Tests completados")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Ingresa la URL de tu servicio Render (ej: https://real-estate-bot.onrender.com): ").strip()

    # Remove trailing slash
    url = url.rstrip('/')

    test_service(url)
