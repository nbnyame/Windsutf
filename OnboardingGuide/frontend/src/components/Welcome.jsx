import { Sparkles, ArrowRight, BookOpen, Monitor, Heart, Building } from 'lucide-react'

const QUICK_LINKS = [
  {
    id: 'firstday',
    title: 'First Day & Week',
    description: 'Know what to expect and prepare for your first days',
    icon: BookOpen,
    color: 'bg-blue-50 text-blue-600',
  },
  {
    id: 'itsetup',
    title: 'IT & Technology',
    description: 'Email setup, VPN, software, and tech support',
    icon: Monitor,
    color: 'bg-purple-50 text-purple-600',
  },
  {
    id: 'hrbenefits',
    title: 'HR & Benefits',
    description: 'PTO, insurance, payroll, and company policies',
    icon: Heart,
    color: 'bg-pink-50 text-pink-600',
  },
  {
    id: 'facilities',
    title: 'Office & Facilities',
    description: 'Parking, break room, office hours, and more',
    icon: Building,
    color: 'bg-amber-50 text-amber-600',
  },
]

export default function Welcome({ setCurrentPage }) {
  return (
    <div>
      {/* Hero Section */}
      <div className="bg-gradient-to-br from-winmark-500 to-winmark-700 rounded-2xl p-8 md:p-12 text-white mb-8">
        <div className="flex items-center gap-2 mb-4">
          <Sparkles className="w-5 h-5 text-yellow-300" />
          <span className="text-sm font-medium text-winmark-100">Welcome aboard!</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold mb-3">
          Welcome to Winmark Corporation
        </h1>
        <p className="text-winmark-100 text-lg max-w-2xl">
          We're thrilled to have you on the team! This onboarding guide will help you get
          settled and answer your most common questions. Explore the sections below or chat
          with our onboarding assistant anytime.
        </p>
      </div>

      {/* Quick Links Grid */}
      <h2 className="text-xl font-semibold text-slate-800 mb-4">Quick Start Guide</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        {QUICK_LINKS.map((link) => {
          const Icon = link.icon
          return (
            <button
              key={link.id}
              onClick={() => setCurrentPage(link.id)}
              className="group bg-white rounded-xl p-5 border border-slate-200 hover:border-winmark-200 hover:shadow-md transition-all text-left"
            >
              <div className="flex items-start gap-4">
                <div className={`p-2.5 rounded-lg ${link.color}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-slate-800">{link.title}</h3>
                    <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-winmark-500 transition-colors" />
                  </div>
                  <p className="text-sm text-slate-500 mt-1">{link.description}</p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {/* About Winmark */}
      <div className="bg-white rounded-xl p-6 border border-slate-200">
        <h2 className="text-xl font-semibold text-slate-800 mb-3">About Winmark Corporation</h2>
        <p className="text-slate-600 leading-relaxed mb-4">
          Winmark Corporation is a leading franchisor of five value-oriented retail store concepts:
          <strong> Plato's Closet</strong>, <strong>Once Upon A Child</strong>,
          <strong> Play It Again Sports</strong>, <strong>Style Encore</strong>, and
          <strong> Music Go Round</strong>. Headquartered in Minneapolis, Minnesota, we are publicly
          traded on NASDAQ under the ticker <strong>WIN</strong>.
        </p>
        <p className="text-slate-600 leading-relaxed">
          Our mission is to provide quality, value-driven franchise opportunities while promoting
          sustainability through the resale of gently used merchandise. With over 1,250 franchised
          stores across North America, we're proud of the community we've built.
        </p>
      </div>
    </div>
  )
}
