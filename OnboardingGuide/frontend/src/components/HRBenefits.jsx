import { Heart, Clock, DollarSign, Shield, Shirt, FileText, Gift } from 'lucide-react'

const BENEFITS = [
  {
    title: 'Paid Time Off (PTO)',
    icon: Clock,
    color: 'bg-blue-50 text-blue-600',
    details: [
      '0–2 years: 15 days per year',
      '3–5 years: 20 days per year',
      '6+ years: 25 days per year',
      'Submit requests through Workday, at least 2 weeks in advance.',
      'Up to 5 days can be carried over into the next year.',
    ],
  },
  {
    title: 'Health Insurance',
    icon: Shield,
    color: 'bg-green-50 text-green-600',
    details: [
      'Medical: Multiple plan options (PPO and HDHP)',
      'Dental & Vision: Coverage for you and dependents',
      'HSA/FSA: Tax-advantaged health savings accounts',
      'Life Insurance: Basic coverage provided, supplemental available',
      'Enrollment must be completed within 30 days of start date.',
    ],
  },
  {
    title: 'Retirement — 401(k)',
    icon: DollarSign,
    color: 'bg-amber-50 text-amber-600',
    details: [
      'Company match up to 4% of your salary',
      'Immediate vesting on your own contributions',
      'Company match vests over 3 years',
      'Enroll through Workday or contact HR for help.',
    ],
  },
  {
    title: 'Payroll',
    icon: DollarSign,
    color: 'bg-purple-50 text-purple-600',
    details: [
      'Paid bi-weekly on Fridays',
      'Direct deposit set up during first-day HR session',
      'View pay stubs at https://workday.winmarkcorporation.com',
      'Questions? Contact payroll@winmarkcorporation.com',
    ],
  },
  {
    title: 'Dress Code',
    icon: Shirt,
    color: 'bg-pink-50 text-pink-600',
    details: [
      'Business casual: Monday – Thursday',
      'Casual Friday: Jeans are acceptable',
      'Includes slacks, blouses, collared shirts, closed-toe shoes',
      'Avoid athletic wear, flip-flops, or overly casual attire.',
    ],
  },
  {
    title: 'Additional Perks',
    icon: Gift,
    color: 'bg-teal-50 text-teal-600',
    details: [
      'Employee discounts at all Winmark franchise brands',
      'Wellness Program: Gym reimbursement and wellness incentives',
      'Tuition Reimbursement: Up to $5,250/year for approved programs',
      'LinkedIn Learning: Free access to thousands of courses',
      'Mentorship Program: Pair with a senior team member',
    ],
  },
]

export default function HRBenefits() {
  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Heart className="w-6 h-6 text-winmark-500" />
          <h1 className="text-2xl font-bold text-slate-800">HR & Benefits</h1>
        </div>
        <p className="text-slate-500">Your compensation, benefits, and company policies at a glance.</p>
      </div>

      {/* Enrollment Reminder */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-8">
        <div className="flex items-start gap-3">
          <FileText className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-semibold text-amber-800 text-sm">Important Reminder</h3>
            <p className="text-sm text-amber-700 mt-1">
              Benefits enrollment must be completed within <strong>30 days</strong> of your start date.
              Contact HR at <strong>hr@winmarkcorporation.com</strong> or ext. 2100 if you need help.
            </p>
          </div>
        </div>
      </div>

      {/* Benefits Grid */}
      <div className="space-y-4">
        {BENEFITS.map((benefit, index) => {
          const Icon = benefit.icon
          return (
            <div key={index} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg ${benefit.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <h3 className="font-semibold text-slate-800">{benefit.title}</h3>
              </div>
              <ul className="space-y-2 ml-11">
                {benefit.details.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                    <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}
