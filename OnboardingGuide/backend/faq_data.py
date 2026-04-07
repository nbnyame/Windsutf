"""
FAQ Knowledge Base for Winmark Corporation Onboarding Guide.
Each entry has: question patterns (keywords), a canonical question, and an answer.
"""

FAQ_ENTRIES = [
    # --- Company Overview ---
    {
        "keywords": ["company", "winmark", "about", "what does", "overview", "history", "mission"],
        "question": "What is Winmark Corporation?",
        "answer": (
            "Winmark Corporation is a leading franchisor of five retail store concepts: "
            "Plato's Closet, Once Upon A Child, Play It Again Sports, Style Encore, and Music Go Round. "
            "We are headquartered in Minneapolis, Minnesota and are publicly traded on NASDAQ under the ticker WIN. "
            "Our mission is to provide quality, value-driven franchise opportunities."
        ),
    },
    {
        "keywords": ["brands", "franchises", "stores", "concepts", "plato", "once upon", "play it again", "style encore", "music go round"],
        "question": "What brands does Winmark operate?",
        "answer": (
            "Winmark Corporation franchises five retail brands:\n"
            "• **Plato's Closet** – Teen and young adult clothing resale\n"
            "• **Once Upon A Child** – Children's clothing, toys, and equipment resale\n"
            "• **Play It Again Sports** – New and used sporting goods\n"
            "• **Style Encore** – Women's clothing and accessories resale\n"
            "• **Music Go Round** – New and used musical instruments and gear"
        ),
    },
    # --- First Day / Week ---
    {
        "keywords": ["first day", "day one", "what to expect", "arrive", "show up", "start"],
        "question": "What should I expect on my first day?",
        "answer": (
            "On your first day:\n"
            "1. Arrive at the front desk by 8:30 AM — a team member will greet you.\n"
            "2. You'll receive your badge, laptop, and welcome kit.\n"
            "3. HR will walk you through paperwork and benefits enrollment.\n"
            "4. Your manager will introduce you to your team.\n"
            "5. You'll have a lunch buddy assigned to show you around!\n\n"
            "Dress code for your first day is business casual."
        ),
    },
    {
        "keywords": ["first week", "week one", "onboarding schedule", "orientation"],
        "question": "What does the first week look like?",
        "answer": (
            "Your first week typically includes:\n"
            "• **Day 1** – Welcome, paperwork, IT setup, team introductions\n"
            "• **Day 2** – Company overview presentation, compliance training\n"
            "• **Day 3** – Department-specific training, meet your mentor\n"
            "• **Day 4** – Systems & tools training, begin role-specific tasks\n"
            "• **Day 5** – Check-in with your manager, Q&A session\n\n"
            "Your manager will share a detailed schedule with you."
        ),
    },
    # --- IT & Technology ---
    {
        "keywords": ["email", "outlook", "mail", "email setup"],
        "question": "How do I set up my email?",
        "answer": (
            "Your corporate email (Outlook/Microsoft 365) will be pre-configured on your laptop. "
            "You'll receive your credentials from IT on your first day. "
            "To access webmail, go to https://outlook.office365.com and sign in with your company credentials. "
            "If you have any issues, contact the IT Help Desk at extension 4357 or email helpdesk@winmarkcorporation.com."
        ),
    },
    {
        "keywords": ["vpn", "remote", "work from home", "connect remotely"],
        "question": "How do I connect to the VPN?",
        "answer": (
            "To connect to the company VPN:\n"
            "1. Open the GlobalProtect VPN client (pre-installed on your laptop).\n"
            "2. Enter the portal address: vpn.winmarkcorporation.com\n"
            "3. Sign in with your network credentials.\n"
            "4. Click 'Connect'.\n\n"
            "VPN is required when working remotely to access internal systems. "
            "Contact IT Help Desk at ext. 4357 if you need assistance."
        ),
    },
    {
        "keywords": ["password", "reset", "login", "credentials", "account"],
        "question": "How do I reset my password?",
        "answer": (
            "To reset your password:\n"
            "1. Go to https://passwordreset.winmarkcorporation.com\n"
            "2. Enter your username and follow the prompts.\n"
            "3. You can also press Ctrl+Alt+Delete on your laptop and select 'Change Password'.\n\n"
            "Passwords must be at least 12 characters with a mix of upper/lowercase, numbers, and symbols. "
            "Passwords expire every 90 days."
        ),
    },
    {
        "keywords": ["software", "install", "programs", "applications", "tools", "apps"],
        "question": "What software will I have access to?",
        "answer": (
            "Standard software on your laptop includes:\n"
            "• Microsoft 365 (Outlook, Word, Excel, PowerPoint, Teams)\n"
            "• GlobalProtect VPN\n"
            "• Adobe Acrobat Reader\n"
            "• Your department-specific tools\n\n"
            "To request additional software, submit a ticket to IT via the Help Desk portal "
            "or email helpdesk@winmarkcorporation.com."
        ),
    },
    {
        "keywords": ["teams", "microsoft teams", "chat", "meetings", "video call"],
        "question": "How do I use Microsoft Teams?",
        "answer": (
            "Microsoft Teams is our primary communication and collaboration tool. "
            "It's pre-installed on your laptop and available on mobile.\n\n"
            "• **Chat** – Direct message colleagues or create group chats\n"
            "• **Meetings** – Schedule and join video/audio meetings\n"
            "• **Channels** – Join your team's channels for project collaboration\n"
            "• **Files** – Share and co-edit documents in real-time\n\n"
            "Your manager will add you to the relevant team channels."
        ),
    },
    # --- HR & Benefits ---
    {
        "keywords": ["pto", "vacation", "time off", "paid time", "days off", "leave"],
        "question": "What is the PTO policy?",
        "answer": (
            "Winmark's PTO policy:\n"
            "• **0-2 years** – 15 days PTO per year\n"
            "• **3-5 years** – 20 days PTO per year\n"
            "• **6+ years** – 25 days PTO per year\n\n"
            "PTO requests should be submitted through Workday at least 2 weeks in advance. "
            "PTO accrues per pay period and can be carried over up to 5 days into the next year."
        ),
    },
    {
        "keywords": ["benefits", "health", "insurance", "medical", "dental", "vision", "401k", "retirement"],
        "question": "What benefits does Winmark offer?",
        "answer": (
            "Winmark offers a comprehensive benefits package:\n"
            "• **Medical** – Multiple plan options (PPO and HDHP)\n"
            "• **Dental & Vision** – Coverage for you and dependents\n"
            "• **401(k)** – Company match up to 4% of salary\n"
            "• **Life Insurance** – Basic coverage provided, supplemental available\n"
            "• **HSA/FSA** – Tax-advantaged health savings accounts\n"
            "• **Employee Discount** – Discounts at all Winmark franchise brands\n"
            "• **Wellness Program** – Gym reimbursement and wellness incentives\n\n"
            "Benefits enrollment must be completed within 30 days of your start date."
        ),
    },
    {
        "keywords": ["payroll", "pay", "paycheck", "direct deposit", "payday", "salary"],
        "question": "When and how do I get paid?",
        "answer": (
            "Winmark pays bi-weekly on Fridays. Direct deposit is set up during your first-day HR session. "
            "You can view pay stubs and tax documents through Workday (https://workday.winmarkcorporation.com). "
            "If you have payroll questions, contact the Payroll team at payroll@winmarkcorporation.com."
        ),
    },
    {
        "keywords": ["dress code", "attire", "what to wear", "clothing", "casual"],
        "question": "What is the dress code?",
        "answer": (
            "Winmark's dress code is **business casual** Monday through Thursday, "
            "and **casual Friday** at the end of the week.\n\n"
            "Business casual includes slacks, blouses, collared shirts, and closed-toe shoes. "
            "Jeans are acceptable on Fridays. Please avoid athletic wear, flip-flops, or overly casual attire."
        ),
    },
    # --- Facilities ---
    {
        "keywords": ["parking", "park", "lot", "garage", "car"],
        "question": "Where do I park?",
        "answer": (
            "Free parking is available in the company parking lot adjacent to the building. "
            "No parking permit is required. Visitor parking is in the front row. "
            "During winter, please be mindful of snow removal schedules posted in the lobby."
        ),
    },
    {
        "keywords": ["lunch", "cafeteria", "food", "eat", "kitchen", "break room", "vending"],
        "question": "Is there a cafeteria or break room?",
        "answer": (
            "Yes! The break room is on the 1st floor and includes:\n"
            "• Full kitchen with refrigerator, microwave, and coffee maker\n"
            "• Vending machines with snacks and beverages\n"
            "• Complimentary coffee, tea, and water\n\n"
            "There are also several restaurants within walking distance. "
            "Your lunch buddy can show you the best spots!"
        ),
    },
    {
        "keywords": ["office", "building", "location", "address", "headquarters", "where"],
        "question": "Where is the office located?",
        "answer": (
            "Winmark Corporation headquarters is located at:\n"
            "605 Highway 169 North, Suite 400\n"
            "Minneapolis, MN 55441\n\n"
            "The office is accessible from Highway 169. Main entrance is on the east side of the building."
        ),
    },
    {
        "keywords": ["hours", "work hours", "schedule", "work schedule", "start time", "end time", "flexible"],
        "question": "What are the office hours?",
        "answer": (
            "Core office hours are **8:00 AM – 5:00 PM**, Monday through Friday. "
            "Winmark offers flexible scheduling — talk to your manager about adjusting your hours. "
            "The building is accessible from 6:00 AM to 8:00 PM with your badge."
        ),
    },
    # --- Address Book / Directory ---
    {
        "keywords": ["address book", "directory", "phone", "contact", "find someone", "employee list", "coworker", "colleague", "phone number", "extension"],
        "question": "How do I find a coworker's contact info?",
        "answer": (
            "You can look up any employee's contact information in the **Winmark Phone Directory**:\n"
            "👉 https://addressbook.winmarkcorporation.com\n\n"
            "Search by name or department to find phone extensions, email addresses, and office locations. "
            "You can also access it from the 'Address Book' section in this onboarding app."
        ),
    },
    # --- Training ---
    {
        "keywords": ["training", "learning", "courses", "development", "grow", "education"],
        "question": "What training opportunities are available?",
        "answer": (
            "Winmark invests in employee development:\n"
            "• **Required Training** – Compliance, security awareness, and harassment prevention (due in first 30 days)\n"
            "• **LinkedIn Learning** – Free access to thousands of online courses\n"
            "• **Tuition Reimbursement** – Up to $5,250/year for approved programs\n"
            "• **Mentorship Program** – Pair with a senior team member\n"
            "• **Lunch & Learns** – Monthly knowledge-sharing sessions\n\n"
            "Talk to your manager about creating a personal development plan."
        ),
    },
    # --- Policies ---
    {
        "keywords": ["policy", "policies", "handbook", "rules", "guidelines", "compliance"],
        "question": "Where can I find company policies?",
        "answer": (
            "The Employee Handbook and all company policies are available on the intranet:\n"
            "https://intranet.winmarkcorporation.com/policies\n\n"
            "Key policies to review in your first week:\n"
            "• Code of Conduct\n"
            "• Information Security Policy\n"
            "• Anti-Harassment Policy\n"
            "• Remote Work Policy\n"
            "• Social Media Policy\n\n"
            "Your HR representative can answer any questions about specific policies."
        ),
    },
    {
        "keywords": ["expense", "reimburse", "reimbursement", "receipt", "travel", "spending"],
        "question": "How do I submit expense reports?",
        "answer": (
            "Expense reports are submitted through Concur:\n"
            "1. Log in to Concur via https://concur.winmarkcorporation.com\n"
            "2. Create a new expense report\n"
            "3. Attach receipts (photo or PDF)\n"
            "4. Submit for manager approval\n\n"
            "Reports should be submitted within 30 days of the expense. "
            "Reimbursements are processed with the next payroll cycle."
        ),
    },
    # --- Support ---
    {
        "keywords": ["help", "support", "who to contact", "question", "issue", "problem", "stuck"],
        "question": "Who should I contact for help?",
        "answer": (
            "Here are your key contacts:\n"
            "• **IT Help Desk** – ext. 4357 or helpdesk@winmarkcorporation.com\n"
            "• **HR Department** – ext. 2100 or hr@winmarkcorporation.com\n"
            "• **Facilities** – ext. 3200 or facilities@winmarkcorporation.com\n"
            "• **Payroll** – payroll@winmarkcorporation.com\n"
            "• **Your Manager** – Check the Phone Directory for their extension\n\n"
            "You can also find anyone's contact info at https://addressbook.winmarkcorporation.com"
        ),
    },
    {
        "keywords": ["mentor", "buddy", "onboarding buddy"],
        "question": "Will I have a mentor or onboarding buddy?",
        "answer": (
            "Yes! Every new hire is assigned:\n"
            "• **Onboarding Buddy** – A peer who will help you navigate your first few weeks, "
            "show you around, and answer day-to-day questions.\n"
            "• **Mentor** (optional) – A senior team member for longer-term career guidance.\n\n"
            "Your manager will introduce you to your buddy on Day 1."
        ),
    },
    # --- Catch-all greeting ---
    {
        "keywords": ["hello", "hi", "hey", "greetings", "good morning", "good afternoon"],
        "question": "Hello!",
        "answer": (
            "Hello and welcome to Winmark Corporation! 👋\n\n"
            "I'm your onboarding assistant. I can help you with:\n"
            "• Company information & culture\n"
            "• IT setup (email, VPN, software)\n"
            "• HR policies & benefits\n"
            "• Office facilities & parking\n"
            "• Finding coworkers in the directory\n"
            "• Training & development\n\n"
            "What would you like to know?"
        ),
    },
]
