import os
import time
import openpyxl
import hashlib
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException
import pandas as pd
import sys

def load_excel_data(file_path, sheet_name=0):
    """Load data from Excel file"""
    wb = openpyxl.load_workbook(file_path, data_only=True)
    sheet = wb[sheet_name] if isinstance(sheet_name, str) else wb.worksheets[sheet_name]
    
    # Get headers from first row
    headers = [cell.value for cell in sheet[1]]
    
    # Get data rows
    data = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        data.append(dict(zip(headers, row)))
    
    return data

def setup_driver():
    """Set up and return a WebDriver instance with proper options"""
    try:
        # Set up Edge options for headless mode
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--log-level=3')  # Only show fatal errors
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Disable automation flags that might trigger bot detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        
        # Set up service with suppressed output
        service = Service(EdgeChromiumDriverManager().install())
        service.creationflags = 0x08000000  # Suppress command window in Windows
        
        # Initialize the Edge driver
        driver = webdriver.Edge(service=service, options=options)
        driver.set_page_load_timeout(30)
        
        # Additional settings to minimize logs
        driver.execute_cdp_cmd('Network.setBlockedURLs', {"urls": ["*"]})
        driver.execute_cdp_cmd('Network.enable', {})
        
        return driver
            
    except Exception as e:
        print("Error initializing WebDriver, attempting fallback...")
        try:
            # Fallback to system WebDriver with minimal logging
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--disable-gpu')
            options.add_argument('--log-level=3')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            driver = webdriver.Edge(options=options)
            driver.set_page_load_timeout(30)
            return driver
        except Exception as e2:
            print(f"Failed to initialize WebDriver: {str(e2)}")
            raise

def fill_microsoft_form(form_url, form_data):
    """Fill Microsoft Form with provided data"""
    print(f"\n=== Starting form fill at {datetime.now().strftime('%H:%M:%S.%f')} ===")
    print(f"Form URL: {form_url}")
    print(f"Form data: {form_data}")
    
    driver = None
    form_submitted = False
    try:
        driver = setup_driver()
        
        # Navigate to the form
        driver.get(form_url)
        
        # Wait for the form to load completely
        print("Waiting for form to load...")
        time.sleep(5)  # Give it more time to load
        
        # Debug: Print page source for inspection
        with open('form_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("Saved page source to form_page.html for debugging")
        
        # Try to find form fields using different selectors
        form_fields = []
        
        # Try Microsoft Forms specific selectors first
        form_fields = driver.find_elements(By.CSS_SELECTOR, 
            'input[type="text"], ' \
            'input[type="email"], ' \
            'input[type="tel"], ' \
            'input[type="number"], ' \
            'textarea, ' \
            'div[role="textbox"], ' \
            'div[data-automation-id="textInputContainer"] input, ' \
            'div[data-automation-id="textItem"] input, ' \
            'div[data-automation-id="questionItem"] input',
        )
        
        # If no fields found, try more generic approach
        if not form_fields:
            print("No form fields found with specific selectors, trying generic approach...")
            form_fields = driver.find_elements(By.TAG_NAME, 'input')
            
            # Filter out non-text inputs
            form_fields = [f for f in form_fields if f.get_attribute('type') in 
                         ['text', 'email', 'tel', 'number', None] and 
                         not f.get_attribute('type') in ['hidden', 'submit', 'button', 'checkbox', 'radio']]
        
        # Get radio button containers
        radio_containers = driver.find_elements(By.CSS_SELECTOR, 
            'div[role="radiogroup"], ' \
            'div[data-automation-id="choiceGroup"], ' \
            'div.office-form-question-element',
        )
        
        print(f"Found {len(form_fields)} form fields and {len(radio_containers)} radio button groups")
        
        # Track if form has been submitted to prevent double submission
        form_submitted = False
        
        # Convert form data values to a list to maintain order
        field_values = list(form_data.values())
        
        # Fill in the form fields in order
        for i, field in enumerate(form_fields):
            if i < len(field_values):
                try:
                    value = field_values[i]
                    if pd.notna(value) and str(value).strip():  # Only fill non-empty, non-NaN values
                        field.clear()
                        field.send_keys(str(value).strip())
                        print(f"Filled field {i+1} with: {value}")
                    else:
                        print(f"Skipping empty field {i+1}")
                except Exception as e:
                    print(f"Error filling field {i+1}: {str(e)}")
        
        # Handle radio buttons (if any) - this is a simple implementation
        # For more complex forms, we might need to enhance this
        radio_index = 0
        for i, container in enumerate(radio_containers):
            if radio_index >= len(field_values):
                break
                
            try:
                # Try to find radio buttons in this container
                radio_buttons = container.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
                if not radio_buttons:
                    continue
                    
                # Get the value we want to match
                target_value = str(field_values[radio_index]).lower()
                radio_index += 1
                
                # Try to find a matching radio button
                selected = False
                for radio in radio_buttons:
                    try:
                        # Get the label text next to the radio button
                        label = radio.find_element(By.XPATH, "./following-sibling::span")
                        label_text = label.text.lower()
                        
                        # If the target value is in the label text, click the radio button
                        if target_value in label_text:
                            radio.click()
                            print(f"Selected radio button: {label_text}")
                            selected = True
                            break
                    except Exception as e:
                        continue
                
                if not selected:
                    print(f"Could not find matching radio button for: {target_value}")
                    
            except Exception as e:
                print(f"Error processing radio button group {i+1}: {str(e)}")
        
        # Submit the form automatically
        try:
            print("\n--- Attempting form submission ---")
            print(f"Current form_submitted flag: {form_submitted}")
            
            # Try to find and click the submit button
            submit_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Submit') or contains(., 'Submit form')]")
            print(f"Found {len(submit_buttons)} submit buttons")
            
            if not form_submitted and submit_buttons:
                print("Clicking submit button...")
                submit_buttons[0].click()
                form_submitted = True
                print(f"Form submitted successfully at {datetime.now().strftime('%H:%M:%S.%f')}")
                time.sleep(2)  # Wait for submission to complete
                print("--- Form submission completed ---\n")
            elif form_submitted:
                print("Form was already submitted, skipping duplicate submission")
            else:
                print("Warning: Could not find submit button. Please submit the form manually.")
                
        except Exception as e:
            print(f"Error submitting form: {str(e)}")
            print("Please submit the form manually.")
        
    except Exception as e:
        print(f"An error occurred while filling the form: {str(e)}")
        if driver:
            error_screenshot = f'form_error_{int(time.time())}.png'
            driver.save_screenshot(error_screenshot)
            print(f"Screenshot saved as '{error_screenshot}'")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                print(f"Error closing WebDriver: {str(e)}")

def get_file_hash(file_path):
    """Generate a hash of the file to detect changes"""
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def get_processed_rows(file_path):
    """Get the number of rows already processed"""
    try:
        with open('processed_rows.txt', 'r') as f:
            return int(f.read().strip() or 0)
    except (FileNotFoundError, ValueError):
        return 0

def update_processed_rows(count):
    """Update the count of processed rows"""
    with open('processed_rows.txt', 'w') as f:
        f.write(str(count))

def monitor_excel_file(excel_file, form_url, check_interval=5):
    """Monitor the Excel file for changes and process new rows"""
    print(f"\n=== Starting form filler monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Monitoring file: {excel_file}")
    print("Press Ctrl+C to stop monitoring\n")
    
    last_hash = None
    processed_rows = get_processed_rows(excel_file)
    processing_lock = False  # Lock to prevent concurrent processing
    
    try:
        while True:
            try:
                if processing_lock:
                    print("Processing in progress, waiting...")
                    time.sleep(check_interval)
                    continue
                    
                current_hash = get_file_hash(excel_file)
                
                if current_hash != last_hash or processing_lock:
                    if not processing_lock:
                        processing_lock = True
                        print(f"\n=== {datetime.now().strftime('%H:%M:%S.%f')} - File change detected ===")
                        print(f"Previous hash: {last_hash}")
                        print(f"Current hash:  {current_hash}")
                    
                    try:
                        # Load the Excel file fresh each time to get the latest data
                        df = pd.read_excel(excel_file, engine='openpyxl')
                        total_rows = len(df)
                        
                        if total_rows > processed_rows:
                            print(f"Found {total_rows - processed_rows} new row(s) to process")
                            
                            # Process only one row at a time
                            row_data = df.iloc[processed_rows].to_dict()
                            print(f"\n=== Processing row {processed_rows + 1}/{total_rows} ===")
                            print(f"Row data: {row_data}")
                            print(f"Current processed_rows: {processed_rows}")
                            print(f"Current time: {datetime.now().strftime('%H:%M:%S.%f')}")
                            
                            # Add a small delay before starting to fill the form
                            time.sleep(1)
                            
                            try:
                                fill_microsoft_form(form_url, row_data)
                                processed_rows += 1
                                update_processed_rows(processed_rows)
                                print(f"Successfully processed row {processed_rows}")
                                
                                # Update the hash after successful processing
                                last_hash = get_file_hash(excel_file)
                                
                                # Add a small delay before next check
                                print(f"Waiting 2 seconds before next check...")
                                time.sleep(2)
                                print("=== Row processing completed ===\n")
                                
                            except Exception as e:
                                print(f"Error processing row {processed_rows + 1}: {str(e)}")
                                # Don't update processed_rows count if there was an error
                                processing_lock = False
                                time.sleep(5)  # Wait longer on error before retry
                                continue
                        else:
                            print("No new rows to process")
                            last_hash = current_hash
                            
                    except Exception as e:
                        print(f"Error reading Excel file: {str(e)}")
                        processing_lock = False
                        time.sleep(5)  # Wait longer on error before retry
                        continue
                    
                    # Release the lock after processing one row
                    processing_lock = False
                    print(f"Waiting for next check in {check_interval} seconds...")
                
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"Error in monitoring loop: {str(e)}")
                processing_lock = False  # Ensure lock is released on error
                time.sleep(check_interval)
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


def main():
    excel_file = r"C:\Users\nnyamekye\CascadeProjects\windsurf-project\email_report.xlsx"
    form_url = "https://forms.office.com/Pages/ResponsePage.aspx?id=PnN2LDxIMk2U0Qan3ue_VElmSxo66JhEmrwPDm5FxfVUMk83RFpEUkpNUFBZSVNORVJRMklDU0hHUi4u"
    
    # Start monitoring the Excel file
    monitor_excel_file(excel_file, form_url)

if __name__ == "__main__":
    main()
