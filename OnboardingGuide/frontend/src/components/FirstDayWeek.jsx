import { Calendar, Clock, Coffee, Users, Laptop, BookOpen, CheckCircle2 } from 'lucide-react'

const DAY_SCHEDULE = [
  {
    day: 'Day 1 — Welcome & Setup',
    icon: Coffee,
    color: 'bg-blue-50 text-blue-600',
    items: [
      'Arrive at the front desk by 8:30 AM',
      'Receive your badge, laptop, and welcome kit',
      'HR paperwork and benefits enrollment',
      'Manager introduction and team meet & greet',
      'Lunch with your onboarding buddy',
      'IT setup walkthrough (email, VPN, tools)',
    ],
  },
  {
    day: 'Day 2 — Company Overview',
    icon: BookOpen,
    color: 'bg-purple-50 text-purple-600',
    items: [
      'Company overview and history presentation',
      'Brand deep-dive: our five franchise concepts',
      'Compliance and security awareness training',
      'Building tour and facilities orientation',
    ],
  },
  {
    day: 'Day 3 — Your Department',
    icon: Users,
    color: 'bg-green-50 text-green-600',
    items: [
      'Department-specific training sessions',
      'Meet your mentor',
      'Review team processes and workflows',
      'Introduction to key tools and systems',
    ],
  },
  {
    day: 'Day 4 — Getting Started',
    icon: Laptop,
    color: 'bg-amber-50 text-amber-600',
    items: [
      'Deeper systems and tools training',
      'Begin role-specific tasks with guidance',
      'Shadow a team member on their daily work',
      'Review 30/60/90-day goals with manager',
    ],
  },
  {
    day: 'Day 5 — Check-In',
    icon: CheckCircle2,
    color: 'bg-pink-50 text-pink-600',
    items: [
      'Weekly wrap-up with your manager',
      'Q&A session — ask anything!',
      'Complete first-week survey',
      'Set up recurring 1:1 meetings',
      'Casual Friday — enjoy the relaxed dress code!',
    ],
  },
]

export default function FirstDayWeek() {
  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Calendar className="w-6 h-6 text-winmark-500" />
          <h1 className="text-2xl font-bold text-slate-800">Your First Day & Week</h1>
        </div>
        <p className="text-slate-500">Here's what to expect during your first week at Winmark.</p>
      </div>

      {/* What to Bring */}
      <div className="bg-winmark-50 rounded-xl p-5 border border-winmark-100 mb-8">
        <h2 className="font-semibold text-winmark-700 mb-2">What to Bring on Day 1</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {[
            'Government-issued photo ID',
            'Voided check or bank details for direct deposit',
            'Completed I-9 documentation',
            'A positive attitude!',
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-winmark-600">
              <CheckCircle2 className="w-4 h-4 text-winmark-500 flex-shrink-0" />
              {item}
            </div>
          ))}
        </div>
      </div>

      {/* Day-by-Day Schedule */}
      <div className="space-y-4">
        {DAY_SCHEDULE.map((day, index) => {
          const Icon = day.icon
          return (
            <div key={index} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center gap-3 p-4 border-b border-slate-100">
                <div className={`p-2 rounded-lg ${day.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <h3 className="font-semibold text-slate-800">{day.day}</h3>
              </div>
              <div className="p-4">
                <ul className="space-y-2">
                  {day.items.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                      <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
