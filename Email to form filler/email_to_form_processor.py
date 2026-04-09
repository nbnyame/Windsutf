import os
import re
import json
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import win32com.client
from openai import OpenAI
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.common.exceptions import WebDriverException, TimeoutException

class OutlookEmailProcessor:
    def __init__(self, api_key: str, form_url: str, folder_name: str = "Inbox", poll_interval: int = 60):
        self.api_key = api_key
        self.form_url = form_url
        self.folder_name = folder_name
        self.poll_interval = poll_interval
        self.processed_emails = set()
        self.case_types = self._load_case_types()
        self.client = OpenAI(api_key=api_key)
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
                raise FileNotFoundError("No valid case types found in Cases.txt")
                
            print("Loaded case types:")
            for case, subcases in case_types.items():
                print(f"- {case}: {', '.join(subcases) if subcases else 'No subcases'}")
                
        except Exception as e:
            print(f"Error loading case types: {str(e)}")
            case_types = {"Other": ["General"]}
            
        return case_types

    def _extract_with_gpt4(self, email_subject: str, email_body: str) -> Dict[str, str]:
        """Extract information from email using GPT-4"""
        try:
            case_selection_text = ""
            for case, subcases in self.case_types.items():
                if subcases:
                    subcase_text = "\n    " + "\n    ".join([f"- {subcase}" for subcase in subcases])
                    case_selection_text += f"- {case}:{subcase_text}\n"
                else:
                    case_selection_text += f"- {case} (No subcases)\n"
            
            prompt = f"""Extract the following information from this email. Pay close attention to both the email subject and body, as important context may be in either location. If information is not found, use the default values provided:

1. Store Number: A 5-digit number starting with 1, 2, 4, 6, or 8. If not found, use 89999.
2. Contact Person: First name only. If not found, use "Staff".
3. Callback Phone Number: Any phone number in the email. If not found, leave empty.
4. Case: Select the SINGLE MOST APPROPRIATE case from this EXACT list (case-sensitive):
{case_selection_text}
5. Case Type: For the selected case, choose the SINGLE MOST APPROPRIATE subcase from the indented list under that case. If no subcase matches, leave this empty.
6. Summary: A concise summary in 8 words or less, incorporating key information from both subject and body.
7. Origin: Set to 'v' if this is a Zoom voicemail, otherwise set to 'e'.

Email Subject: {email_subject}
Email Body: {email_body[:4000]}

Return the response in JSON format with these exact keys: store_number, contact_person, phone_number, case, case_type, summary, origin.

IMPORTANT RULES:
- The 'case' field MUST be EXACTLY one of the main cases shown above (case-sensitive)
- The 'case_type' field MUST be EXACTLY one of the subcases listed under the selected case, or an empty string if none match
- DO NOT make up or modify any case names or subcase names
- If the email doesn't clearly match any case, use the first case as default
- If the email doesn't clearly match any subcase, leave case_type as an empty string
- Pay special attention to the email subject as it may contain critical information like store numbers, case types, or urgency indicators"""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            try:
                data = json.loads(result)
                default_values = self._get_default_values()
                for key in ['store_number', 'contact_person', 'phone_number', 'case', 'case_type', 'summary', 'origin']:
                    # If key doesn't exist or value is empty/whitespace, use default
                    if key not in data or not str(data[key]).strip():
                        data[key] = default_values.get(key, '')
                
                # Validate that case_type is a valid subcase of the selected case
                if data.get('case') in self.case_types and data.get('case_type'):
                    valid_subcases = [subcase.lower().replace('subcase: ', '').strip() for subcase in self.case_types[data['case']]]
                    current_case = data['case_type'].lower().strip()
                    
                    # Check if the case_type matches any valid subcase (case-insensitive and ignoring 'Subcase: ' prefix)
                    if not any(current_case == subcase.lower() or 
                             current_case == f'subcase: {subcase}'.lower() or
                             current_case in subcase.lower() or
                             f'subcase: {current_case}'.lower() in subcase.lower()
                             for subcase in valid_subcases):
                        # Store the invalid subcase in a separate field for reference
                        data['invalid_case_type'] = data['case_type']
                        data['case_type'] = ''
                
                return data
            except json.JSONDecodeError:
                print("Warning: Failed to parse GPT-4 response as JSON, using fallback extraction")
                return self._extract_from_text(result, email_subject, email_body)
                
        except Exception as e:
            print(f"Error processing email with GPT-4: {str(e)}")
            return self._get_default_values()

    def _extract_from_text(self, text: str, subject: str, body: str) -> Dict[str, str]:
        """Fallback method to extract information from text if JSON parsing fails"""
        result = self._get_default_values()
        
        store_match = re.search(r'\b([12468]\d{4})\b', subject + " " + body)
        if store_match:
            result['store_number'] = store_match.group(1)
            
        contact_match = re.search(r'(?:Contact|From)[:\s]+(\w+)', body, re.IGNORECASE)
        if contact_match:
            result['contact_person'] = contact_match.group(1)
            
        phone_match = re.search(r'(\d{3}[-.]?\d{3}[-.]?\d{4})', body)
        if phone_match:
            result['phone_number'] = phone_match.group(1)
            
        for case_type in self.case_types:
            if case_type.lower() in body.lower() or case_type.lower() in subject.lower():
                result['case_type'] = case_type
                break
                
        now = datetime.now()
        result['summary'] = f"{subject[:100]}..."
            
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
            'summary': 'Unable to process email content',
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
                    driver = webdriver.Edge(service=service, options=options)
                except Exception as e:
                    print(f"Warning: Could not use WebDriverManager, trying system WebDriver: {str(e)}")
                    driver = webdriver.Edge(options=options)
                
                driver.set_page_load_timeout(30)
                print("WebDriver initialized successfully")
                return driver
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    print(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    print("Max retries reached. Could not initialize WebDriver.")
                    return None

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

    def process_email(self, mail_item) -> bool:
        """Process a single email and submit to form"""
        try:
            email_id = mail_item.EntryID
            if email_id in self.processed_emails:
                return False
                
            print(f"\nProcessing email: {mail_item.Subject}")
            
            subject = mail_item.Subject or "No Subject"
            body = mail_item.Body or ""
            
            # Process with GPT-4
            result = self._extract_with_gpt4(subject, body)
            
            if not result:
                return False
                
            # Add email metadata with the email's received time
            received_time = mail_item.ReceivedTime
            result['date'] = received_time.strftime('%m/%d/%y')
            result['time'] = received_time.strftime('%I:%M %p').lstrip('0')
            result['email_id'] = email_id
            result['subject'] = subject
            
            # Mark as read
            mail_item.UnRead = False
            mail_item.Save()
            
            # Submit to form
            form_submitted = self.submit_to_form(result)
            
            if form_submitted:
                self.processed_emails.add(email_id)
                print(f"Successfully processed email: {subject}")
                return True
            else:
                print(f"Failed to submit form for email: {subject}")
                return False
                
        except Exception as e:
            print(f"Error processing email: {str(e)}")
            return False

    def monitor_emails(self):
        """Monitor the specified Outlook folder for new emails"""
        print(f"Starting to monitor '{self.folder_name}' folder...")
        
        try:
            outlook = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
            
            if self.folder_name.lower() == "inbox":
                folder = outlook.GetDefaultFolder(6)  # 6 is the Inbox
            else:
                inbox = outlook.GetDefaultFolder(6)
                folder = inbox.Folders[self.folder_name]
                
            print(f"Monitoring folder: {folder.Name}")
            
            # Initial load of existing emails (mark as processed without processing)
            messages = folder.Items
            for message in messages:
                self.processed_emails.add(message.EntryID)
            
            print(f"Found {len(self.processed_emails)} existing emails. Monitoring for new ones...")
            
            try:
                while True:
                    try:
                        messages = folder.Items
                        messages.Sort("[ReceivedTime]", True)
                        new_emails = 0
                        
                        for message in messages:
                            if message.UnRead:
                                success = self.process_email(message)
                                if success:
                                    new_emails += 1
                        
                        if new_emails > 0:
                            print(f"Processed {new_emails} new email(s).")
                            print(f"Waiting for new emails (checking every {self.poll_interval} seconds)...")
                        
                        time.sleep(self.poll_interval)
                        
                    except KeyboardInterrupt:
                        print("\nStopping email monitor...")
                        break
                    except Exception as e:
                        print(f"Error in monitoring loop: {str(e)}")
                        time.sleep(60)
                        
            finally:
                # Clean up WebDriver when done
                if hasattr(self, 'driver') and self.driver:
                    try:
                        self.driver.quit()
                        self.driver = None
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error setting up Outlook: {str(e)}")
            print("Make sure Outlook is installed and running.")
        finally:
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
            print("Email monitoring stopped.")

def main():
    print("Outlook Email to Form Processor")
    print("-----------------------------")
    
    # Configuration
    api_key = ""  # Replace with your actual API key
    form_url = "https://forms.office.com/Pages/ResponsePage.aspx?id=PnN2LDxIMk2U0Qan3ue_VElmSxo66JhEmrwPDm5FxfVUMk83RFpEUkpNUFBZSVNORVJRMklDU0hHUi4u"  # Replace with your form URL
    folder_name = "Generated Responses"  # Or specify your folder name
    poll_interval = 15  # Check for new emails every 60 seconds
    
    if not api_key or api_key == "your_openai_api_key_here":
        print("Error: Please provide a valid OpenAI API key in the script.")
        return
    
    if not form_url or "YOUR_FORM_ID" in form_url:
        print("Error: Please provide a valid Microsoft Form URL in the script.")
        return
    
    # Create and start the email processor
    try:
        processor = OutlookEmailProcessor(
            api_key=api_key,
            form_url=form_url,
            folder_name=folder_name,
            poll_interval=poll_interval
        )
        
        print("\nStarting email monitoring. Press Ctrl+C to stop.")
        processor.monitor_emails()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Make sure all dependencies are installed and Outlook is running.")
    
    print("Program ended.")

if __name__ == "__main__":
    main()
