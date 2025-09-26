#!/usr/bin/env python3
import argparse, json, sys, time, os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

SIGNIN_URL = "https://members.helium10.com/user/signin"
CODE_REQUIRED_PATH = "/user/code-required"

KEYWORD_TRACKER_PATH = "https://members.helium10.com/keyword-tracker"
USER_EMAIL = "YOUR_EMAIL"
USER_PWD = "YOUR_PWD"

PROFILE_DIR = "{HELIUM 10 PROFILE CACHE PATH}"
DOWNLOAD_DIR = "{DOWNLOAD_DIRECTORY}"
TIMEOUT_SEC = 180   # how long to wait after 2FA

SHEET_CREDS = "{SERVICE ACCOUNT PATH}"  # put your downloaded creds file
SHEET_NAME  = "{SHEET NAME}"  # Google Sheet name

# configure your creds & sheet once
def init_gsheet(creds_path, sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    client = gspread.authorize(creds)
    return client.open(sheet_name).sheet1   # or .worksheet("YourTabName")

def append_to_sheet(sheet, asin, status_text):
    """Append a row [ASIN, status_text] to the sheet."""
    sheet.append_row([asin, status_text], value_input_option="USER_ENTERED")

def fill_with_fallbacks(page, value, selectors):
    # Try multiple selectors until one works.
    last_err = None
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=10_000)
            page.fill(sel, value)
            return True
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return False

def click_with_fallbacks(page, selectors):
    last_err = None
    for sel in selectors:
        try:
            page.locator(sel).first.wait_for(state="visible", timeout=10_000)
            page.locator(sel).first.click()
            return True
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err
    return False

def ensure_page(context):
    pages = context.pages
    if pages:
        return pages[0]
    return context.new_page()

def parse_asins(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return []
    # Accept JSON array or comma/space-separated text
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # fallback: comma/space separated
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p]


def main():
    ap = argparse.ArgumentParser(description="Helium10 login via Playwright (Chrome).")
    ap.add_argument("--asins", required=True, help="JSON array or comma-separated ASINs")
    args = ap.parse_args()

    sheet = init_gsheet(SHEET_CREDS, SHEET_NAME)

    asins = parse_asins(args.asins)
    if not asins:
        print(json.dumps({"status":"error","message":"No ASINs provided"}))
        sys.exit(1)

    with sync_playwright() as p:
        # Launch Chrome with persistent profile (cookies reused here)
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            channel="chrome",          # forces actual Chrome
            headless=False,            # must be headed so user can type 2FA
            args=["--start-maximized"]
        )

        page = ensure_page(context)
        page.bring_to_front()

        # Go to sign-in
        page.goto(SIGNIN_URL, wait_until="domcontentloaded")
        # Extra settle: wait for either email field or code-required page
        try:
            page.wait_for_selector('input[name="LoginForm[email]"], input#email, input[type="text"]', timeout=10_000)
        except Exception:
            pass
        page.wait_for_timeout(500)  # half-second settle

       # If still on the sign-in form --> fill login
        if "signin" in page.url:
            try:
                fill_with_fallbacks(page, USER_EMAIL, [
                    'input[name="LoginForm[email]"]', 'input#email', 'input[type="text"]'
                ])
                page.wait_for_timeout(300)  # small pause between fields
                fill_with_fallbacks(page, USER_PWD, [
                    'input[name="LoginForm[password]"]', 'input#password', 'input[type="password"]'
                ])
                page.wait_for_timeout(300)
                click_with_fallbacks(page, [
                    'button[type="submit"]', 'button:has-text("Sign in")', 'button:has-text("Log in")'
                ])
                # Give the post-submit navigation time
                page.wait_for_load_state("domcontentloaded", timeout=30_000)
                page.wait_for_timeout(1000)
                # Then a broader settle
                try:
                    page.wait_for_load_state("networkidle", timeout=30_000)
                except Exception:
                    # Some SPAs never go fully idle; brief fallback wait
                    page.wait_for_timeout(1500)
            except Exception as e:
                print(json.dumps({"status": "error", "message": str(e)}))
                sys.exit(1)

        # Handle code-required (2FA)
        if CODE_REQUIRED_PATH in page.url:
            print(json.dumps({
                "status": "2fa_required",
                "message": "Enter the code manually in the Chrome window. Press Resume in Inspector or Enter in terminal when done."
            }), flush=True)
            try:
                page.pause()  # gives you control until you resume
            except Exception:
                input("After entering the 2FA code in the browser, press Enter here to continue...")

        # Wait for dashboard
        try:
            page.wait_for_url("**/dashboard*", timeout=TIMEOUT_SEC * 1000)
            # Allow widgets to finish initial XHRs
           # try:
           #     page.wait_for_load_state("networkidle", timeout=10_000)
           # except Exception:
            page.wait_for_timeout(1500)
        except PWTimeoutError:
            print(json.dumps({
                "status": "timeout",
                "final_url": page.url,
                "profile_dir": PROFILE_DIR
            }))

        # Small pause before navigating to KT
        page.wait_for_timeout(1000)

        # Go to keyword-tracker
        page.goto(KEYWORD_TRACKER_PATH, wait_until="domcontentloaded")
        # Wait for KT search UI to mount
        try:
            page.wait_for_selector('input[type="search"], input[name="search"], .kt-search input, #search, input[name="q"]', timeout=15_000)
        except Exception:
            pass
        page.wait_for_timeout(500)  # settle

        page.wait_for_timeout(1000)  # Wait before searching for 1s

        # Locate search box once
        search_box = page.locator(
            'input[type="search"], input[name="search"], .kt-search input, #search, input[name="q"]'
        ).first

        for asin in asins:
            asin = asin.strip()
            if not asin:
                continue

            # Clear search, type ASIN, submit
            try:
                search_box.wait_for(state="visible", timeout=10_000)
            except Exception:
                print(json.dumps({"status":"error","asin":asin,"message":"Search box not visible"}), flush=True)
                continue

            search_box.click()
            modifier = "Meta" if sys.platform == "darwin" else "Control"
            page.keyboard.press(f"{modifier}+A")
            page.keyboard.press("Backspace")
            search_box.fill(asin)
            page.keyboard.press("Enter")

            # Wait for results to load or determine NOT FOUND
            page.wait_for_timeout(3000)
            # Try waiting for a row; if none in time, mark not found
            found = True
            try:
                page.locator('tr.kt-orders-row').first.wait_for(state="visible", timeout=20_000)
            except Exception:
                found = False

            if not found:
                print(json.dumps({"status":"not_found","asin":asin}), flush=True)
                
                # UPDATE IN SHEETs THAT ASIN NOT FOUND
                append_to_sheet(sheet, asin, "Not Found")

                # tiny pause between ASINs
                page.wait_for_timeout(1000)
                continue

            page.wait_for_timeout(1000)

            
            # Wait a tiny bit before clicking the first item
            row_locator = page.locator('tr.kt-orders-row').first
            page.wait_for_timeout(1000)  # 1s
            row_locator.scroll_into_view_if_needed()
            page.wait_for_timeout(200)
            row_locator.click()
            page.wait_for_timeout(500)  # let expand animation run

            # Wait until the Export button is actually visible before clicking
            try:
                page.locator('tr.kt-keywords-row:not(.hide)').first.wait_for(state="visible", timeout=10_000)
            except Exception:
                page.wait_for_timeout(500)

            # A robust proxy: wait until the Export button becomes visible
            export_btn_candidates = [
                'button:has-text("Export")',
                'button.btn.btn-success.btn-sm.dropdown-toggle',
                'button:has(i.fas.fa-table)'
            ]

            # ensure visibility first to avoid racing
            try:
                page.locator(export_btn_candidates[0] + "," + export_btn_candidates[1] + "," + export_btn_candidates[2]).first.wait_for(state="visible", timeout=10_000)
            except Exception:
                page.wait_for_timeout(300)

            click_with_fallbacks(page, export_btn_candidates)  # opens the dropdown
            page.wait_for_timeout(300)  # let dropdown mount

            # Click "Current result" in the dropdown and capture the download
            with page.expect_download() as dl_info:
                # Prefer exact class; fall back to text contains
                cur_res_candidates = [
                    'a.dropdown-item.action-export-cur-res',
                    'a:has-text("Current result")',
                    'a >> text=Current result'
                ]
                # ensure item is visible first
                try:
                    page.locator(cur_res_candidates[0] + "," + cur_res_candidates[1] + "," + cur_res_candidates[2]).first.wait_for(state="visible", timeout=10_000)
                except Exception:
                    page.wait_for_timeout(200)
                click_with_fallbacks(page, cur_res_candidates)
            download = dl_info.value

            # Save the file where you want (keep original suggested name)
            suggested_name = download.suggested_filename
            save_path = os.path.join(DOWNLOAD_DIR, suggested_name)
            download.save_as(save_path)

            print(json.dumps({
                "status": "ok",
                "asin": asin,
                "final_url": page.url,
                "download_path": save_path,
                "profile_dir": PROFILE_DIR
            }), flush=True)

            # UPDATE IN SHEETs THAT ASIN NOT FOUND
            append_to_sheet(sheet, asin, "Success")

            # small pause between ASINs
            page.wait_for_timeout(800)

        # Close the browser after all ASINs are done
        context.close()

if __name__ == "__main__":
    sys.exit(main())