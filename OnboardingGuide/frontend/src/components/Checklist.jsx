import { useState, useEffect } from 'react'
import { CheckSquare, Circle, CheckCircle2, RotateCcw } from 'lucide-react'

const INITIAL_CHECKLIST = [
  {
    category: 'Day 1 — Arrival',
    items: [
      { id: 'arrive', label: 'Arrive at front desk by 8:30 AM' },
      { id: 'badge', label: 'Receive badge and welcome kit' },
      { id: 'laptop', label: 'Receive and set up laptop' },
      { id: 'hr-paperwork', label: 'Complete HR paperwork' },
      { id: 'meet-team', label: 'Meet your team' },
      { id: 'lunch-buddy', label: 'Lunch with onboarding buddy' },
    ],
  },
  {
    category: 'IT Setup',
    items: [
      { id: 'email', label: 'Set up corporate email (Outlook)' },
      { id: 'vpn', label: 'Configure VPN (GlobalProtect)' },
      { id: 'teams', label: 'Log into Microsoft Teams' },
      { id: 'password', label: 'Change default password' },
      { id: 'software', label: 'Verify all software is installed' },
    ],
  },
  {
    category: 'HR & Benefits',
    items: [
      { id: 'benefits', label: 'Enroll in benefits (within 30 days)' },
      { id: 'direct-deposit', label: 'Set up direct deposit' },
      { id: '401k', label: 'Review and enroll in 401(k)' },
      { id: 'handbook', label: 'Read employee handbook' },
    ],
  },
  {
    category: 'Training & Compliance',
    items: [
      { id: 'compliance', label: 'Complete compliance training' },
      { id: 'security', label: 'Complete security awareness training' },
      { id: 'harassment', label: 'Complete harassment prevention training' },
      { id: 'dept-training', label: 'Complete department-specific training' },
    ],
  },
  {
    category: 'First Week',
    items: [
      { id: 'mentor', label: 'Meet your mentor' },
      { id: 'goals', label: 'Review 30/60/90-day goals with manager' },
      { id: 'one-on-one', label: 'Schedule recurring 1:1 with manager' },
      { id: 'channels', label: 'Join relevant Teams channels' },
      { id: 'directory', label: 'Explore the Phone Directory' },
      { id: 'survey', label: 'Complete first-week feedback survey' },
    ],
  },
]

const STORAGE_KEY = 'winmark-onboarding-checklist'

export default function Checklist() {
  const [checked, setChecked] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : {}
    } catch {
      return {}
    }
  })

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(checked))
  }, [checked])

  const toggleItem = (id) => {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const resetAll = () => {
    setChecked({})
  }

  const totalItems = INITIAL_CHECKLIST.reduce((sum, cat) => sum + cat.items.length, 0)
  const completedItems = Object.values(checked).filter(Boolean).length
  const progressPercent = totalItems > 0 ? Math.round((completedItems / totalItems) * 100) : 0

  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <CheckSquare className="w-6 h-6 text-winmark-500" />
              <h1 className="text-2xl font-bold text-slate-800">My Onboarding Checklist</h1>
            </div>
            <p className="text-slate-500">Track your progress through the onboarding process.</p>
          </div>
          <button
            onClick={resetAll}
            className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors"
            title="Reset all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-slate-700">Overall Progress</span>
          <span className="text-sm font-semibold text-winmark-600">
            {completedItems} / {totalItems} ({progressPercent}%)
          </span>
        </div>
        <div className="w-full bg-slate-100 rounded-full h-3">
          <div
            className="bg-gradient-to-r from-winmark-400 to-winmark-600 h-3 rounded-full transition-all duration-500"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        {progressPercent === 100 && (
          <p className="text-sm text-green-600 font-medium mt-2">
            Congratulations! You've completed all onboarding tasks!
          </p>
        )}
      </div>

      {/* Checklist Categories */}
      <div className="space-y-4">
        {INITIAL_CHECKLIST.map((category, catIndex) => {
          const catCompleted = category.items.filter((item) => checked[item.id]).length
          const catTotal = category.items.length
          return (
            <div key={catIndex} className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 bg-slate-50 border-b border-slate-100">
                <h3 className="font-semibold text-slate-700 text-sm">{category.category}</h3>
                <span className="text-xs text-slate-400">
                  {catCompleted}/{catTotal}
                </span>
              </div>
              <div className="p-3">
                {category.items.map((item) => {
                  const isChecked = !!checked[item.id]
                  return (
                    <button
                      key={item.id}
                      onClick={() => toggleItem(item.id)}
                      className="w-full flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors text-left"
                    >
                      {isChecked ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                      ) : (
                        <Circle className="w-5 h-5 text-slate-300 flex-shrink-0" />
                      )}
                      <span
                        className={`text-sm ${
                          isChecked ? 'text-slate-400 line-through' : 'text-slate-700'
                        }`}
                      >
                        {item.label}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
