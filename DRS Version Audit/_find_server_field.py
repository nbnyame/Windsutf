import sys, os
sys.path.insert(0, r'c:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\.env')
from crm_client import Dynamics365Client

crm = Dynamics365Client()
crm.authenticate()

r = crm._request('GET', 'accounts', params={
    '$filter': 'statecode eq 0',
    '$select': 'accountid,accountnumber',
    '$top': '1'
}).json()

acct_id = r['value'][0]['accountid']
acct_num = r['value'][0]['accountnumber']
print(f'Sample account: {acct_num} / {acct_id}')

# Get all fields on this account and look for anything server/hardware related
acct = crm._request('GET', f'accounts({acct_id})').json()
keywords = ['server', 'model', 'hardware', 'hw', 'gen', 'g10', 'g9', 'device']
print('\nPossible server model fields:')
for key, val in sorted(acct.items()):
    if any(k in key.lower() for k in keywords):
        print(f'  {key} = {repr(val)}')

print('\nAll win_ fields with values:')
for key, val in sorted(acct.items()):
    if key.startswith('win_') and val not in (None, ''):
        print(f'  {key} = {repr(val)}')
