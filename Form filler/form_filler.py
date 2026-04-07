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

def format_field_value(value):
    """Format field values, especially dates and times, for form input"""
    if pd.isna(value) or value is None:
        return value
    
    # Handle Excel date/time values (they come as floats)
    if isinstance(value, (int, float)):
        try:
            # If it's a whole number, it's probably just a date
            if value == int(value):
                dt = pd.Timestamp('1899-12-30') + pd.Timedelta(days=value)
                return dt.strftime('%m/%d/%Y')
            # Otherwise it's a datetime with time component
            else:
                dt = pd.Timestamp('1899-12-30') + pd.Timedelta(days=value)
                # If the time is exactly midnight, it's probably just a date
                if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                    return dt.strftime('%m/%d/%Y')
                # Otherwise format as time only
                return dt.strftime('%-I:%M %p').lower()
        except:
            pass
    
    # Convert to string and strip whitespace
    str_value = str(value).strip()
    
    # Check if the value looks like a date or time string
    try:
        # Try to parse as datetime
        dt = pd.to_datetime(str_value, errors='coerce')
        if pd.notna(dt):
            # If it's a date field (no time component or time is midnight)
            if dt.time() == pd.Timestamp.min.time():
                return dt.strftime('%m/%d/%Y')
            # If it's a time field (date is 1900-01-01)
            elif dt.date() == pd.Timestamp('1900-01-01').date():
                return dt.strftime('%-I:%M %p').lower()
            # If it's a full datetime
            else:
                return dt.strftime('%m/%d/%Y %-I:%M %p').lower()
    except:
        pass
        
    return str_value

def fill_microsoft_form(form_url, form_data):
    """Fill Microsoft Form with provided data"""
    print(f"\n=== Starting form fill at {datetime.now().strftime('%H:%M:%S.%f')} ===")
    print(f"Form URL: {form_url}")
    
    # Format all field values before processing
    formatted_data = {k: format_field_value(v) for k, v in form_data.items()}
    print(f"Form data: {formatted_data}")
    
    driver = None
    form_submitted = False
    try:
        driver = setup_driver()
        
        # Navigate to the form
        print(f"Navigating to form: {form_url}")
        driver.get(form_url)
        
        # Wait for the form to load completely - increased wait time
        print("Waiting for form to load...")
        time.sleep(10)  # Increased from 5 to 10 seconds
        
        # Save page source for debugging
        with open('form_page.html', 'w', encoding='utf-8') as f:
            f.write(driver.page_source)
        print("Saved page source to form_page.html for debugging")
        
        # Try to find all input fields - Microsoft Forms specific
        print("Looking for form fields...")
        
        # Find all input elements that are visible and enabled
        all_inputs = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 
                'input[type="text"], '
                'input[type="email"], '
                'input[type="tel"], '
                'input[type="number"], '
                'textarea, '
                'div[role="textbox"], '
                'div[data-automation-id="textInputContainer"] input, '
                'div[data-automation-id="textItem"] input, '
                'div[data-automation-id="questionItem"] input, '
                'div[role="textbox"], '
                'div[data-automation-id="textInput"]',
            ))
        )
        
        # Filter to only visible and enabled inputs
        form_fields = []
        for field in all_inputs:
            try:
                if field.is_displayed() and field.is_enabled():
                    form_fields.append(field)
            except:
                continue
        
        # Try a different approach if no fields found
        if not form_fields:
            print("No fields found with standard selectors, trying alternative approach...")
            form_fields = driver.find_elements(By.CSS_SELECTOR, 'input, textarea')
            form_fields = [f for f in form_fields if f.is_displayed() and f.is_enabled()]
        
        print(f"Found {len(form_fields)} form fields")
        
        # Find radio button groups
        radio_groups = driver.find_elements(By.CSS_SELECTOR, 
            'div[role="radiogroup"], '
            'div[data-automation-id="choiceGroup"], '
            'div.office-form-question-element',
        )
        
        print(f"Found {len(radio_groups)} radio button groups")
        
        # Convert form data values to a list to maintain order
        field_values = list(form_data.values())
        
        # Fill in the form fields in order
        for i, field in enumerate(form_fields):
            if i < len(field_values):
                try:
                    value = field_values[i]
                    if pd.notna(value) and str(value).strip():
                        # Scroll the field into view
                        driver.execute_script("arguments[0].scrollIntoView(true);", field)
                        time.sleep(0.5)  # Small delay for scrolling
                        
                        # Clear and fill the field
                        field.clear()
                        field.click()  # Focus the field
                        time.sleep(0.5)
                        
                        formatted_value = str(format_field_value(value)).strip()
                        field.send_keys(formatted_value)
                        print(f"Filled field {i+1} with: {formatted_value}")
                        time.sleep(0.5)  # Small delay between fields
                    else:
                        print(f"Skipping empty field {i+1}")
                except Exception as e:
                    print(f"Error filling field {i+1}: {str(e)}")
        
        # Handle radio buttons
        radio_index = 0
        for i, group in enumerate(radio_groups):
            if radio_index >= len(field_values):
                break
                
            try:
                target_value = str(field_values[radio_index]).lower()
                radio_index += 1
                
                # Find all radio buttons in this group
                radio_buttons = group.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
                if not radio_buttons:
                    continue
                
                # Try to find a matching radio button
                selected = False
                for radio in radio_buttons:
                    try:
                        # Get the label text next to the radio button
                        label = radio.find_element(By.XPATH, "./following-sibling::span")
                        label_text = label.text.lower()
                        
                        # If the target value is in the label text, click the radio button
                        if target_value in label_text or any(option in label_text for option in target_value.split()):
                            driver.execute_script("arguments[0].scrollIntoView(true);", radio)
                            time.sleep(0.5)
                            radio.click()
                            print(f"Selected radio button: {label_text}")
                            selected = True
                            time.sleep(0.5)
                            break
                    except Exception as e:
                        continue
                
                if not selected:
                    print(f"Could not find matching radio button for: {target_value}")
                    
            except Exception as e:
                print(f"Error processing radio button group {i+1}: {str(e)}")
        
        # Submit the form
        try:
            print("\n--- Attempting form submission ---")
            
            # Try different selectors for the submit button
            submit_selectors = [
                "button[type='submit']",
                "button:contains('Submit')",
                "div[role='button']:contains('Submit')",
                "//button[contains(., 'Submit') or contains(., 'Submit form')]"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    if selector.startswith('//'):
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            submit_button = element
                            break
                    
                    if submit_button:
                        break
                except:
                    continue
            
            if submit_button:
                print("Clicking submit button...")
                driver.execute_script("arguments[0].scrollIntoView(true);", submit_button)
                time.sleep(1)
                submit_button.click()
                form_submitted = True
                print(f"Form submitted successfully at {datetime.now().strftime('%H:%M:%S.%f')}")
                
                # Wait for submission to complete
                time.sleep(5)
                
                # Check if submission was successful
                try:
                    # Look for success message or confirmation
                    success_elements = driver.find_elements(By.XPATH, 
                        "//*[contains(., 'Thank you') or contains(., 'Response recorded') or contains(., 'Your response has been recorded')]")
                    if success_elements:
                        print("Form submission confirmed!")
                    else:
                        print("Form submission may not have been successful. Please verify manually.")
                except:
                    print("Could not verify form submission status. Please check manually.")
                
                print("--- Form submission completed ---\n")
            else:
                print("Warning: Could not find a clickable submit button. Please submit the form manually.")
                
        except Exception as e:
            print(f"Error submitting form: {str(e)}")
            print("Please submit the form manually.")
        
    except Exception as e:
        print(f"An error occurred while filling the form: {str(e)}")
        if driver:
            error_screenshot = f'form_error_{int(time.time())}.png'
            driver.save_screenshot(error_screenshot)
            print(f"Screenshot saved as '{error_screenshot}'")
            
            # Save page source for debugging
            try:
                with open(f'form_error_{int(time.time())}.html', 'w', encoding='utf-8') as f:
                    f.write(driver.page_source)
                print("Saved error page source for debugging")
            except:
                print("Could not save error page source")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                passrint(f"Error closing WebDriver: {str(e)}")

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

def get_initial_processed_count(excel_file):
    """Get the initial count of processed rows from file.
    Returns 0 if no processed rows file exists or if it's corrupted.
    """
    processed_rows_file = 'processed_rows.txt'
    if os.path.exists(processed_rows_file):
        try:
            with open(processed_rows_file, 'r') as f:
                content = f.read().strip()
                if content.isdigit():
                    return int(content)
                return 0
        except (ValueError, FileNotFoundError, IOError):
            # If there's any error reading the file, start from 0
            return 0
    return 0  # If no file exists, start from 0

def update_processed_rows(count):
    """Update the count of processed rows"""
    try:
        with open('processed_rows.txt', 'w') as f:
            f.write(str(count))
    except IOError as e:
        print(f"Warning: Could not update processed rows count: {e}")

def monitor_excel_file(excel_file, form_url, check_interval=1):
    """Monitor the Excel file for changes and process new rows"""
    print(f"\n=== Starting form filler monitor at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    print(f"Monitoring file: {excel_file}")
    print("Press Ctrl+C to stop monitoring\n")
    
    # Track the last modification time and size of the file
    last_modified = os.path.getmtime(excel_file)
    last_size = os.path.getsize(excel_file)
    
    # Track processed row hashes to avoid reprocessing
    processed_hashes = set()
    processed_rows_file = 'processed_hashes.txt'
    
    # Load previously processed hashes if they exist
    if os.path.exists(processed_rows_file):
        try:
            with open(processed_rows_file, 'r') as f:
                processed_hashes = set(line.strip() for line in f if line.strip())
            print(f"Loaded {len(processed_hashes)} previously processed row hashes")
        except Exception as e:
            print(f"Warning: Could not load processed hashes: {str(e)}")
            processed_hashes = set()
    
    try:
        while True:
            try:
                # Check both modification time and size for better change detection
                current_modified = os.path.getmtime(excel_file)
                current_size = os.path.getsize(excel_file)
                
                # Check if file was modified or size changed
                file_changed = (current_modified > last_modified) or (current_size != last_size)
                
                if file_changed:
                    # Small delay to ensure the file is fully written
                    time.sleep(1)
                    last_modified = current_modified
                    last_size = current_size
                    
                    try:
                        # Load the Excel file
                        df = pd.read_excel(excel_file, engine='openpyxl')
                        print(f"\n=== File changed detected at {datetime.now().strftime('%H:%M:%S')} ===")
                        print(f"Total rows in file: {len(df)}")
                        
                        # Process new rows
                        new_rows_processed = 0
                        for i, row in df.iterrows():
                            # Create a hash of the row data to track processed rows
                            row_hash = hashlib.md5(str(row.values).encode('utf-8')).hexdigest()
                            
                            if row_hash not in processed_hashes:
                                row_data = row.to_dict()
                                print(f"\n=== Processing row {i + 1} ===")
                                print(f"Row data: {row_data}")
                                
                                try:
                                    fill_microsoft_form(form_url, row_data)
                                    processed_hashes.add(row_hash)
                                    new_rows_processed += 1
                                    
                                    # Save the updated hashes after each successful submission
                                    with open(processed_rows_file, 'a') as f:
                                        f.write(f"{row_hash}\n")
                                    
                                    print(f"Successfully processed row {i + 1}")
                                    time.sleep(1)  # Small delay between submissions
                                    
                                except Exception as e:
                                    print(f"Error processing row {i + 1}: {str(e)}")
                                    time.sleep(2)  # Short delay before retry
                                    break  # Exit the row processing loop on error
                        
                        if new_rows_processed > 0:
                            print(f"\n=== Processed {new_rows_processed} new row(s) ===")
                        else:
                            print("No new rows to process")
                            
                    except Exception as e:
                        print(f"Error reading Excel file: {str(e)}")
                        time.sleep(2)  # Short delay before retry
                
                # Use a more responsive sleep pattern
                for _ in range(10):  # Check 10 times per second
                    time.sleep(0.1)
                    try:
                        if (os.path.getmtime(excel_file) > last_modified or 
                            os.path.getsize(excel_file) != last_size):
                            break
                    except:
                        pass  # Ignore errors during the check
                
            except KeyboardInterrupt:
                raise
                
            except Exception as e:
                print(f"Error in monitoring loop: {str(e)}")
                time.sleep(2)  # Short delay on error
                
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"\nUnexpected error: {str(e)}")
    finally:
        print("\nForm filler monitor stopped")
        print(f"Unexpected error: {str(e)}")


def main():
    excel_file = r"C:\Users\nnyamekye\OneDrive - Winmark Corporation\Desktop\Excel report\email_report.xlsx"
    form_url = "https://forms.office.com/Pages/ResponsePage.aspx?id=PnN2LDxIMk2U0Qan3ue_VElmSxo66JhEmrwPDm5FxfVUMk83RFpEUkpNUFBZSVNORVJRMklDU0hHUi4u"
    
    # Start monitoring the Excel file
    monitor_excel_file(excel_file, form_url)

if __name__ == "__main__":
    main()
