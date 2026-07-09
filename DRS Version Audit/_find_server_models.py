import sys
sys.path.insert(0, r'c:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\nnyamekye\CascadeProjects\windsurf-project\Dynamics365CRM\.env')
from crm_client import Dynamics365Client

crm = Dynamics365Client()
crm.authenticate()

options = crm.get_option_set_values('account', 'win_servermodel')
print(f'{len(options)} server model options:')
for label, code in sorted(options.items(), key=lambda x: x[1]):
    print(f'  [{code}]  {label}')
