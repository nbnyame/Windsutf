import os
import re
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import win32com.client
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException

class OutlookEmailProcessor:
    def __init__(self, form_url: str, folder_name: str = "Inbox", poll_interval: int = 15):
        """
        Initialize the email processor without GPT-4 dependency.
        
        Args:
            form_url: URL of the form to submit data to
            folder_name: Name of the Outlook folder to monitor (default: "Inbox")
            poll_interval: How often to check for new emails in seconds (default: 60)
        """
        self.form_url = form_url
        self.folder_name = folder_name
        self.poll_interval = poll_interval
        self.processed_emails = set()
        self.case_types = self._load_case_types()
        self.driver = None
        
    def _load_case_types(self) -> Dict[str, List[str]]:
        """Load case types from Cases.txt file"""
        case_types = {}
        current_case = None
        
        try:
            cases_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Cases.txt')
            if os.path.exists(cases_file):
                with open(cases_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('Case:'):
                            current_case = line[5:].strip()
                            case_types[current_case] = []
                        elif current_case and line and not line.startswith('Case Type:'):
                            if line and not line.startswith('Case Type:'):
                                case_types[current_case].append(line.strip())
            
            if not case_types:
                print("Warning: No valid case types found in Cases.txt, using default")
                case_types = {"Other": ["General"]}
                
            print("Loaded case types:")
            for case, subcases in case_types.items():
                print(f"- {case}: {', '.join(subcases) if subcases else 'No subcases'}")
                
        except Exception as e:
            print(f"Error loading case types: {str(e)}")
            case_types = {"Other": ["General"]}
            
        return case_types

    def extract_email_data(self, email_subject: str, email_body: str) -> Dict[str, str]:
        """
        Extract structured data from email using regex patterns.
        
        Args:
            email_subject: The subject line of the email
            email_body: The body content of the email
            
        Returns:
            Dictionary containing extracted fields:
            - store_number: 5-digit store number (default: 89999)
            - contact_person: First name (default: 'Staff')
            - phone_number: Extracted phone number (default: 'store')
            - case: Matched case from Cases.txt (default: first case)
            - case_type: Matched subcase (default: empty string)
            - summary: Short summary from subject
            - origin: 'v' for voicemail, 'e' for email
        """
        result = self._extract_from_text(email_subject, email_body)
        
        # Set default values for any missing fields
        defaults = self._get_default_values()
        for key in defaults:
            if not result.get(key):
                result[key] = defaults[key]
        
        # Ensure case_type is valid for the selected case
        if result['case'] in self.case_types and result['case_type']:
            valid_subcases = [s.lower() for s in self.case_types[result['case']]]
            if result['case_type'].lower() not in valid_subcases:
                result['case_type'] = ''
        
        return result

    def _extract_from_text(self, subject: str, body: str) -> Dict[str, str]:
        """Extract information from text using regex patterns"""
        result = self._get_default_values()
        full_text = f"{subject} {body}".lower()
        
        # Extract store number (5 digits starting with 1,2,4,6, or 8)
        store_match = re.search(r'\b([12468]\d{4})\b', full_text)
        if store_match:
            result['store_number'] = store_match.group(1)
        
        # Extract contact person (look for common patterns)
        contact_match = re.search(
            r'(?:contact|from|name)[:\s]+([a-zA-Z]+(?: [a-zA-Z]+)?)',
            full_text, 
            re.IGNORECASE
        )
        if contact_match:
            result['contact_person'] = contact_match.group(1).strip().split()[0]  # First name only
        
        # Extract phone number (various formats)
        phone_patterns = [
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # 123-456-7890 or 123.456.7890 or 1234567890
            r'\(\d{3}\)\s*\d{3}[-.]?\d{4}',    # (123) 456-7890
        ]
        for pattern in phone_patterns:
            phone_match = re.search(pattern, full_text)
            if phone_match:
                result['phone_number'] = phone_match.group(0)
                break
        
        # Determine case and case_type
        text_lower = full_text.lower()
        for case, subcases in self.case_types.items():
            if case.lower() in text_lower:
                result['case'] = case
                # Try to find a matching subcase
                for subcase in subcases:
                    if subcase.lower() in text_lower:
                        result['case_type'] = subcase
                        break
                break
        
        # Create a simple summary from subject and first 50 chars of body
        summary = subject
        if len(summary) > 50:
            summary = summary[:47] + '...'
        result['summary'] = summary
        
        # Set origin (v for voicemail, e for email)
        result['origin'] = 'v' if any(word in text_lower for word in ['voicemail', 'voice mail', 'vm']) else 'e'
        
        return result

    def _get_default_values(self) -> Dict[str, str]:
        """Return default values for all fields"""
        default_case = next(iter(self.case_types.keys()), 'Other')
        default_case_type = self.case_types.get(default_case, [''])[0] if self.case_types.get(default_case) else ''
        
        return {
            'store_number': '89999',
            'contact_person': 'Staff',
            'phone_number': 'store',
            'case': default_case,
            'case_type': '',
            'summary': 'No summary available',
            'origin': 'e'  # Default to 'e' for email
        }

    def setup_webdriver(self):
        """Set up and return a WebDriver instance with proper options"""
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                options = Options()
                options.add_argument('--headless')
                options.add_argument('--disable-gpu')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-extensions')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--log-level=3')
                options.add_experimental_option('excludeSwitches', ['enable-logging'])
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option('useAutomationExtension', False)
                
                # Try to use the installed driver first
                try:
                    service = Service(EdgeChromiumDriverManager().install())
                    service.creationflags = 0x08000000
                    self.driver = webdriver.Edge(service=service, options=options)
                except Exception as e:
                    print(f"Warning: Could not use WebDriverManager: {e}")
                    # Fallback to system PATH
                    self.driver = webdriver.Edge(options=options)
                
                # Set a reasonable page load timeout
                self.driver.set_page_load_timeout(30)
                return True
                
            except WebDriverException as e:
                print(f"WebDriver setup attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Max retries reached. Could not initialize WebDriver.")
                    return False
    def submit_to_form(self, form_data: Dict[str, str]) -> bool:
        """Submit data to Microsoft Form"""
        if not hasattr(self, 'driver') or self.driver is None:
            self.driver = self.setup_webdriver()
            if self.driver is None:
                print("Error: Could not initialize WebDriver")
                return False
        
        try:
            # Create a copy of form_data without email_id for printing
            print_data = {k: v for k, v in form_data.items() if k != 'email_id'}
            print(f"\nSubmitting form data: {print_data}")
            
            self.driver.get(self.form_url)
            print("Waiting for form to load...")
            time.sleep(5)  # Wait for form to load
            
            # Get all input fields on the page
            all_inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input, textarea, [role="textbox"]')
            print(f"Found {len(all_inputs)} input fields on the page")
            
            if not all_inputs:
                print("No input fields found. Saving page source for debugging...")
                with open('form_page.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print("Saved form page source to form_page.html")
                return False
            
            # Map of field names to their values
            field_mapping = {
                'store_number': form_data.get('store_number', ''),
                'contact_person': form_data.get('contact_person', ''),
                'phone_number': form_data.get('phone_number', ''),
                'case': form_data.get('case', ''),
                'case_type': form_data.get('case_type', ''),
                'summary': form_data.get('summary', ''),
                'date': form_data.get('date', ''),
                'time': form_data.get('time', ''),
                'origin': form_data.get('origin', 'e')  # Default to 'e' if not provided
            }
            
            # Fill each field in order
            for i, field in enumerate(all_inputs, 1):
                try:
                    # Get the field value based on position
                    field_value = ''
                    if i == 1:
                        field_value = str(field_mapping['store_number'])
                    elif i == 2:
                        field_value = str(field_mapping['contact_person'])
                    elif i == 3:
                        field_value = str(field_mapping['phone_number'])
                    elif i == 4:
                        field_value = str(field_mapping['case'])
                    elif i == 5:
                        field_value = str(field_mapping['case_type'])
                        if not field_value and 'case' in form_data and form_data['case'] in self.case_types:
                            valid_subcases = self.case_types[form_data['case']]
                            if valid_subcases:  # Only show warning if there are valid subcases available
                                invalid_subcase = form_data.get('invalid_case_type', 'not provided')
                                warning_msg = (
                                    f"Warning: Invalid subcase '{invalid_subcase}' for case '{form_data['case']}'. "
                                    f"Leaving subcase field empty."
                                )
                                print(warning_msg)
                    elif i == 6:
                        field_value = str(field_mapping['date'])
                    elif i == 7:
                        field_value = str(field_mapping['time'])
                    elif i == 8:
                        field_value = str(field_mapping['summary'])
                    elif i == 9:
                        field_value = str(field_mapping['origin'])
                    
                    if field_value:
                        field.clear()
                        field.send_keys(field_value)
                        print(f"Filled field {i} with: {field_value}")
                        time.sleep(0.5)  # Small delay between fields
                        
                except Exception as e:
                    print(f"Error filling field {i}: {str(e)}")
                    continue
            
            # Try to find and click the submit button
            submit_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(., 'Submit') or contains(., 'Submit form') or @type='submit']"
            )
            
            if submit_buttons:
                try:
                    submit_buttons[0].click()
                    print("Form submitted successfully")
                    time.sleep(2)
                    return True
                except Exception as e:
                    print(f"Error clicking submit button: {str(e)}")
            else:
                print("Could not find submit button. Available buttons:")
                buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                for i, btn in enumerate(buttons, 1):
                    btn_text = btn.text or btn.get_attribute('aria-label') or btn.get_attribute('value') or 'No text'
                    print(f"Button {i}: {btn_text}")
                return False
                
        except Exception as e:
            print(f"Error submitting form: {str(e)}")
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"form_error_{timestamp}.png"
                self.driver.save_screenshot(screenshot_path)
                print(f"Screenshot saved as {screenshot_path}")
                
                # Save page source for debugging
                with open(f'form_error_{timestamp}.html', 'w', encoding='utf-8') as f:
                    f.write(self.driver.page_source)
                print(f"Page source saved as form_error_{timestamp}.html")
                
            except Exception as screenshot_error:
                print(f"Could not save debug information: {str(screenshot_error)}")
            return False

    def process_email(self, email_subject: str, email_body: str) -> bool:
        """
        Process a single email and submit its data to the form
        
        Args:
            email_subject: The subject line of the email
            email_body: The body content of the email
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            print("\n" + "="*50)
            print(f"Processing email: {email_subject[:100]}...")
            
            # Extract data from email
            extracted_data = self.extract_email_data(email_subject, email_body)
            print("Extracted data:", json.dumps(extracted_data, indent=2))
            
            # Submit to form (you'll need to implement this part)
            submit_success = self.submit_to_form(extracted_data)
            if not submit_success:
                print("Failed to submit form data")
                return False
                
            print("Email processed successfully")
            return True
            
        except Exception as e:
            print(f"Error processing email: {str(e)}")
            return False

def main():
    # Initialize the processor with your form URL
    form_url = "https://forms.office.com/Pages/ResponsePage.aspx?id=PnN2LDxIMk2U0Qan3ue_VElmSxo66JhEmrwPDm5FxfVUMk83RFpEUkpNUFBZSVNORVJRMklDU0hHUi4u"
    
    print("Starting Email to Form Processor (No GPT-4)")
    print("Monitoring Outlook Inbox...")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    
    try:
        # Initialize the processor
        processor = OutlookEmailProcessor(form_url=form_url)
        
        # Set up the web driver
        if not processor.setup_webdriver():
            print("Failed to initialize WebDriver. Exiting...")
            return
        
        # Connect to Outlook
        outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        inbox = None
 
        try:
            # First get the default mailbox
            inbox = outlook.GetDefaultFolder(6)  # 6 is the Inbox
            print(f"Accessing folder: {inbox.Name}")
    
            # Navigate to the "Generated Responses" folder
            for folder in inbox.Folders:
                print(f"Found folder: {folder.Name}")
                if folder.Name.lower() == "generated responses":
                    inbox = folder
                    print(f"Successfully accessed folder: {folder.Name}")
                    break
    
            if inbox is None or inbox.Name.lower() != "generated responses":
                print("Error: 'Generated Responses' folder not found. Available folders:")
                for folder in outlook.Folders:
                    print(f"- {folder.Name}")
                print("Exiting program.")
                return  # This will exit the main function and terminate the program
 
        except Exception as e:
            print(f"Error accessing Outlook folders: {str(e)}")
            print("Exiting program due to error.")
            return  # This will exit the main function and terminate the program
        
        print("\nMonitoring for new emails...")
        
        try:
            while True:
                # Get all unread emails
                unread_emails = inbox.Items.Restrict("[UnRead] = true")
                
                for email in unread_emails:
                    try:
                        # Get email details
                        email_subject = email.Subject or "No Subject"
                        email_body = email.Body or ""
                        email_id = f"{email.Subject}_{email.ReceivedTime}"
                        
                        # Skip if we've already processed this email
                        if email_id in processor.processed_emails:
                            continue
                            
                        print(f"\nFound new email: {email_subject}")
                        
                        # Process the email
                        if processor.process_email(email_subject, email_body):
                            # Mark as read
                            email.UnRead = False
                            # Save the email ID to avoid reprocessing
                            processor.processed_emails.add(email_id)
                            print("Email processed and marked as read")
                        else:
                            print("Failed to process email")
                            
                    except Exception as e:
                        print(f"Error processing email: {str(e)}")
                        continue
                
                # Wait before checking for new emails again
                time.sleep(processor.poll_interval)
                
        except KeyboardInterrupt:
            print("\nStopping email monitoring...")
            
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        # Clean up
        if hasattr(processor, 'driver') and processor.driver:
            processor.driver.quit()
        print("Processor stopped")

if __name__ == "__main__":
    main()
