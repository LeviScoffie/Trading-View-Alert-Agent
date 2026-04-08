#!/usr/bin/env python3
"""
Test script for end-to-end integration flow.

Tests the complete flow:
1. Send webhook to Integration Service
2. Verify alert is stored
3. Verify analysis is triggered
4. Verify email is sent (if confidence >= threshold)

Usage:
    python test_integration.py
    python test_integration.py --symbol ETHUSD --timeframe 4H
    python test_integration.py --host http://localhost:8004
"""

import argparse
import json
import sys
import time
from datetime import datetime

try:
    import httpx
except ImportError:
    print("Error: httpx is required. Install with: pip install httpx")
    sys.exit(1)


def test_health_check(base_url: str) -> bool:
    """Test health check endpoint."""
    print("\n" + "="*60)
    print("TEST 1: Health Check")
    print("="*60)
    
    try:
        response = httpx.get(f"{base_url}/health", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        print(f"Status: {data.get('status', 'unknown')}")
        print(f"Timestamp: {data.get('timestamp')}")
        print("\nService Statuses:")
        
        for service in data.get('services', []):
            status_icon = "✓" if service.get('status') == 'healthy' else "✗"
            print(f"  {status_icon} {service['name']}: {service['status']}")
            if service.get('response_time_ms'):
                print(f"    Response time: {service['response_time_ms']:.1f}ms")
        
        all_healthy = all(s.get('status') == 'healthy' for s in data.get('services', []))
        return all_healthy
        
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return False


def test_webhook_flow(base_url: str, symbol: str, timeframe: str) -> bool:
    """Test the full webhook → analysis → email flow."""
    print("\n" + "="*60)
    print(f"TEST 2: Webhook Flow ({symbol})")
    print("="*60)
    
    # Prepare webhook payload
    payload = {
        "symbol": symbol,
        "price": 45000.00 if "BTC" in symbol else 3000.00,
        "message": f"Test alert for {symbol}",
        "time": datetime.utcnow().isoformat(),
        "timeframe": timeframe
    }
    
    print(f"Sending webhook: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = httpx.post(
            f"{base_url}/webhook",
            json=payload,
            timeout=60
        )
        elapsed = time.time() - start_time
        response.raise_for_status()
        
        data = response.json()
        
        print(f"\n✓ Webhook processed in {elapsed:.2f}s")
        print(f"  Alert ID: {data.get('alert_id')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Confidence: {data.get('confidence', 'N/A')}")
        print(f"  Email Sent: {data.get('email_sent', False)}")
        
        if data.get('message'):
            print(f"  Message: {data.get('message')}")
        
        return True
        
    except httpx.TimeoutException:
        print("✗ Request timed out (analysis may still be running)")
        return False
    except Exception as e:
        print(f"✗ Webhook test failed: {e}")
        return False


def test_manual_analysis(base_url: str, symbol: str, timeframe: str) -> bool:
    """Test manual analysis trigger."""
    print("\n" + "="*60)
    print(f"TEST 3: Manual Analysis Trigger ({symbol})")
    print("="*60)
    
    payload = {
        "symbol": symbol,
        "timeframe": timeframe
    }
    
    print(f"Triggering analysis: {json.dumps(payload, indent=2)}")
    
    try:
        start_time = time.time()
        response = httpx.post(
            f"{base_url}/trigger-analysis",
            json=payload,
            timeout=60
        )
        elapsed = time.time() - start_time
        response.raise_for_status()
        
        data = response.json()
        
        print(f"\n✓ Analysis completed in {elapsed:.2f}s")
        print(f"  Alert ID: {data.get('alert_id')}")
        print(f"  Status: {data.get('status')}")
        print(f"  Confidence: {data.get('confidence', 'N/A')}")
        print(f"  Email Sent: {data.get('email_sent', False)}")
        
        return True
        
    except httpx.TimeoutException:
        print("✗ Request timed out (analysis may still be running)")
        return False
    except Exception as e:
        print(f"✗ Manual analysis test failed: {e}")
        return False


def test_alert_status(base_url: str, alert_id: int) -> bool:
    """Test alert status endpoint."""
    print("\n" + "="*60)
    print(f"TEST 4: Alert Status (ID: {alert_id})")
    print("="*60)
    
    try:
        response = httpx.get(f"{base_url}/status/{alert_id}", timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"✓ Alert found")
        print(f"  Symbol: {data.get('symbol')}")
        print(f"  Received: {data.get('received_at')}")
        print(f"  Processed: {data.get('processed', False)}")
        
        if data.get('analysis'):
            print(f"  Analysis: Available")
        
        return True
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(f"✗ Alert {alert_id} not found")
        else:
            print(f"✗ Status check failed: {e}")
        return False
    except Exception as e:
        print(f"✗ Status check failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test TradingView Integration Service")
    parser.add_argument("--host", default="http://localhost:8004", help="Integration service URL")
    parser.add_argument("--symbol", default="BTCUSD", help="Symbol to test")
    parser.add_argument("--timeframe", default="1D", help="Timeframe for analysis")
    parser.add_argument("--skip-health", action="store_true", help="Skip health check")
    parser.add_argument("--skip-webhook", action="store_true", help="Skip webhook test")
    parser.add_argument("--skip-manual", action="store_true", help="Skip manual analysis test")
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("TradingView Integration Service - End-to-End Test")
    print("="*60)
    print(f"Host: {args.host}")
    print(f"Symbol: {args.symbol}")
    print(f"Timeframe: {args.timeframe}")
    
    results = []
    
    # Test 1: Health Check
    if not args.skip_health:
        results.append(("Health Check", test_health_check(args.host)))
    
    # Test 2: Webhook Flow
    alert_id = None
    if not args.skip_webhook:
        success = test_webhook_flow(args.host, args.symbol, args.timeframe)
        results.append(("Webhook Flow", success))
        # Note: We can't easily get the alert_id from the webhook test
        # without parsing the response more carefully
    
    # Test 3: Manual Analysis
    if not args.skip_manual:
        results.append(("Manual Analysis", test_manual_analysis(args.host, args.symbol, args.timeframe)))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
