import re
import asyncio
import time
import random
import json
from playwright.async_api import async_playwright
from urllib.parse import urlparse

async def solve_recaptcha_v2(page, sitekey, api_key=None):
    """
    Solve reCAPTCHA v2 using 2Captcha service or automated approach
    """
    if api_key:
        # Use 2Captcha service
        try:
            import requests
            import base64
            
            # Submit captcha to 2Captcha
            submit_url = "http://2captcha.com/in.php"
            submit_data = {
                'key': api_key,
                'method': 'userrecaptcha',
                'googlekey': sitekey,
                'pageurl': page.url,
                'json': 1
            }
            
            response = requests.post(submit_url, data=submit_data)
            result = response.json()
            
            if result['status'] == 1:
                captcha_id = result['request']
                
                # Wait for solution
                for _ in range(30):  # Wait up to 5 minutes
                    await asyncio.sleep(10)
                    check_url = f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1"
                    check_response = requests.get(check_url)
                    check_result = check_response.json()
                    
                    if check_result['status'] == 1:
                        solution = check_result['request']
                        # Inject solution
                        await page.evaluate(f"""
                            document.getElementById('g-recaptcha-response').innerHTML = '{solution}';
                            if (typeof window.grecaptchaCallback === 'function') {{
                                window.grecaptchaCallback('{solution}');
                            }}
                        """)
                        return True
            return False
        except Exception as e:
            print(f"2Captcha error: {e}")
            return False
    else:
        # Automated approach - try to manipulate reCAPTCHA
        try:
            # Wait for reCAPTCHA to load
            await page.wait_for_selector('.g-recaptcha', timeout=10000)
            
            # Try multiple bypass techniques
            techniques = [
                # Technique 1: Direct callback injection
                """
                var callback = window.grecaptchaCallback || function() {};
                var response = 'fake-response-for-testing';
                document.getElementById('g-recaptcha-response').innerHTML = response;
                callback(response);
                """,
                
                # Technique 2: Trigger success event
                """
                var event = new Event('recaptcha-success');
                document.dispatchEvent(event);
                """,
                
                # Technique 3: Mock grecaptcha object
                """
                window.grecaptcha = {
                    getResponse: function() { return 'fake-response'; },
                    reset: function() {}
                };
                var forms = document.querySelectorAll('form');
                forms.forEach(form => form.submit());
                """
            ]
            
            for technique in techniques:
                try:
                    await page.evaluate(technique)
                    await asyncio.sleep(2)
                    
                    # Check if CAPTCHA was solved
                    solved = await page.evaluate("""
                        var response = document.getElementById('g-recaptcha-response');
                        return response && response.innerHTML.length > 50;
                    """)
                    
                    if solved:
                        return True
                except:
                    continue
            
            return False
        except:
            return False

async def check_pta_device(imei: str, captcha_api_key=None):
    """
    Check PTA device status with automated reCAPTCHA bypass.
    """
    # Clean IMEI
    imei_clean = re.sub(r"\D", "", imei)
    
    async with async_playwright() as p:
        # Launch browser with stealth settings
        browser = await p.chromium.launch(
            headless=False,
            args=[
                '--start-maximized',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            ignore_https_errors=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            window.chrome = {runtime: {}};
        """)
        
        page = await context.new_page()
        
        try:
            # Navigate to PTA DIRBS homepage
            print("🌐 Navigating to PTA DIRBS portal...")
            await page.goto(
                "https://dirbs.pta.gov.pk/dirs-web/",
                wait_until="networkidle",
                timeout=60000
            )
            
            # Click on "Check Device" link/button
            print("🔍 Clicking 'Check Device' option...")
            
            # Try multiple possible selectors for the check device link
            check_device_selectors = [
                "a:has-text('Check Device')",
                "button:has-text('Check Device')",
                "a[href*='check']",
                ".check-device-btn",
                "text=Check Your Device"
            ]
            
            for selector in check_device_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    print(f"✅ Clicked using selector: {selector}")
                    break
                except:
                    continue
            
            # Wait for the IMEI input page to load
            await page.wait_for_timeout(3000)
            
            # Fill IMEI - try multiple possible input selectors
            print(f"⌨️ Entering IMEI: {imei_clean}")
            
            imei_selectors = [
                "input[name='imei']",
                "input[placeholder*='IMEI']",
                "input#imei",
                "input[type='text']",
                "input.form-control"
            ]
            
            entered = False
            for selector in imei_selectors:
                try:
                    await page.fill(selector, imei_clean, timeout=5000)
                    print(f"✅ IMEI entered using selector: {selector}")
                    entered = True
                    break
                except:
                    continue
            
            if not entered:
                print("❌ Could not find IMEI input field. Manual entry required.")
            
            # Wait for reCAPTCHA to load
            print("🤖 Waiting for reCAPTCHA to load...")
            await page.wait_for_timeout(3000)
            
            # Try to find reCAPTCHA sitekey
            sitekey = None
            try:
                sitekey = await page.evaluate("""
                    var recaptcha = document.querySelector('.g-recaptcha');
                    if (recaptcha) {
                        return recaptcha.getAttribute('data-sitekey');
                    }
                    return null;
                """)
                print(f"� Found reCAPTCHA sitekey: {sitekey}")
            except:
                print("⚠️ Could not extract reCAPTCHA sitekey")
            
            # Attempt to solve reCAPTCHA
            print("🔓 Attempting to bypass reCAPTCHA...")
            captcha_solved = await solve_recaptcha_v2(page, sitekey, captcha_api_key)
            
            if captcha_solved:
                print("✅ reCAPTCHA bypassed successfully!")
                await page.wait_for_timeout(2000)
            else:
                print("⚠️ Automatic reCAPTCHA bypass failed. Manual intervention may be required.")
                print("📋 Instructions:")
                print("1. Complete the reCAPTCHA manually in the browser")
                print("2. The script will continue automatically")
                
                # Wait a bit for manual completion
                await page.wait_for_timeout(10000)
            
            # Try to find and click submit button
            print("🔍 Looking for submit button...")
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Check')",
                "button:has-text('Submit')",
                "button:has-text('Verify')",
                ".btn-submit",
                "#submit-btn"
            ]
            
            submitted = False
            for selector in submit_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    print(f"✅ Clicked submit using selector: {selector}")
                    submitted = True
                    break
                except:
                    continue
            
            if not submitted:
                print("⚠️ Could not find submit button. Trying form submission...")
                try:
                    await page.evaluate("document.querySelector('form').submit()")
                    submitted = True
                    print("✅ Form submitted via JavaScript")
                except:
                    print("❌ Form submission failed")
            
            if submitted:
                # Wait for results to load
                print("⏳ Waiting for results page...")
                await page.wait_for_timeout(5000)
            
            # Take screenshot for debugging
            await page.screenshot(path='pta_result.png', full_page=True)
            print("📸 Screenshot saved as 'pta_result.png'")
            
            # Try to extract result from the page
            print("🔍 Extracting results...")
            
            # Try multiple approaches to get result
            result_text = ""
            
            # Method 1: Look for alert/success boxes
            alert_selectors = [
                ".alert",
                ".alert-success",
                ".alert-info",
                ".result-message",
                ".status-message",
                "div:has-text('compliant'), div:has-text('blocked'), div:has-text('registered')"
            ]
            
            for selector in alert_selectors:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.text_content()
                    if text and len(text.strip()) > 10:  # Reasonable length
                        result_text = text.strip()
                        break
                if result_text:
                    break
            
            # Method 2: Look for specific text patterns
            if not result_text:
                page_content = await page.content()
                # Search for common PTA status messages
                patterns = [
                    r"Device is.*?compliant",
                    r"Device.*?blocked",
                    r"IMEI.*?registered",
                    r"Device.*?not found",
                    r"Grey traffic",
                    r"Non-compliant"
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, page_content, re.IGNORECASE)
                    if match:
                        result_text = match.group(0)
                        break
            
            # Method 3: Get all text and filter
            if not result_text:
                body_text = await page.text_content("body")
                lines = body_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if any(keyword in line.lower() for keyword in ['compliant', 'blocked', 'registered', 'not found', 'grey']):
                        result_text = line
                        break
            
            # Determine status
            status = "Unknown"
            if result_text:
                msg = result_text.lower()
                if "grey" in msg and "traffic" in msg:
                    status = "Blocked (Grey Traffic)"
                elif "blocked" in msg:
                    status = "Blocked"
                elif "compliant" in msg:
                    status = "Compliant"
                elif "non-compliant" in msg or "non compliant" in msg:
                    status = "Non-Compliant"
                elif "not found" in msg:
                    status = "Not Found"
                elif "registered" in msg:
                    status = "Registered"
            else:
                result_text = "Could not extract status message"
            
            # Create result dictionary
            result = {
                "imei": imei_clean,
                "raw_message": result_text,
                "status": status,
                "url": page.url,
                "screenshot": "pta_result.png"
            }
            
            print("\n" + "="*70)
            print("✅ PTA CHECK COMPLETED")
            print("="*70)
            print(f"IMEI: {result['imei']}")
            print(f"Status: {result['status']}")
            print(f"URL: {result['url']}")
            if result_text:
                print(f"Message: {result_text[:200]}{'...' if len(result_text) > 200 else ''}")
            print("="*70)
            
            # Ask user if they want to close browser
            keep_open = input("\nKeep browser open for inspection? (y/n): ").lower()
            if keep_open != 'y':
                await browser.close()
            else:
                print("Browser will remain open. Close manually when done.")
                # Keep script running
                await asyncio.sleep(3600)  # Keep open for 1 hour
            
            return result
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            await page.screenshot(path='error_screenshot.png')
            print("📸 Error screenshot saved as 'error_screenshot.png'")
            await browser.close()
            return None

if __name__ == "__main__":
    # Get IMEI from user
    imei = input("Enter IMEI to check: ").strip()
    if not imei:
        imei = "123456789012345"  # Default test IMEI
    
    # Optional: Get 2Captcha API key
    captcha_api_key = input("Enter 2Captcha API key (optional, press Enter to skip): ").strip()
    if not captcha_api_key:
        captcha_api_key = None
    
    print(f"Checking IMEI: {imei}")
    asyncio.run(check_pta_device(imei, captcha_api_key))