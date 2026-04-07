import {
  Home,
  Calendar,
  Monitor,
  Heart,
  Building,
  BookOpen,
  CheckSquare,
  ChevronLeft,
  ChevronRight,
  Menu,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'welcome', label: 'Welcome', icon: Home },
  { id: 'firstday', label: 'First Day & Week', icon: Calendar },
  { id: 'itsetup', label: 'IT & Technology', icon: Monitor },
  { id: 'hrbenefits', label: 'HR & Benefits', icon: Heart },
  { id: 'facilities', label: 'Facilities', icon: Building },
  { id: 'addressbook', label: 'Address Book', icon: BookOpen },
  { id: 'checklist', label: 'My Checklist', icon: CheckSquare },
]

export default function Sidebar({ currentPage, setCurrentPage, sidebarOpen, setSidebarOpen }) {
  return (
    <>
      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white rounded-lg shadow-md"
      >
        <Menu className="w-5 h-5 text-slate-600" />
      </button>

      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } lg:translate-x-0 fixed lg:static inset-y-0 left-0 z-40 w-64 bg-white border-r border-slate-200 shadow-sm transition-transform duration-300 flex flex-col`}
      >
        {/* Logo */}
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-winmark-500 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">W</span>
            </div>
            <div>
              <h1 className="font-bold text-slate-800 text-sm">Winmark Corp</h1>
              <p className="text-xs text-slate-500">Onboarding Guide</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = currentPage === item.id
            return (
              <button
                key={item.id}
                onClick={() => {
                  setCurrentPage(item.id)
                  if (window.innerWidth < 1024) setSidebarOpen(false)
                }}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-winmark-50 text-winmark-600 border border-winmark-100'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'
                }`}
              >
                <Icon className={`w-4.5 h-4.5 ${isActive ? 'text-winmark-500' : 'text-slate-400'}`} />
                {item.label}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100">
          <div className="bg-winmark-50 rounded-lg p-3">
            <p className="text-xs text-winmark-700 font-medium">Need help?</p>
            <p className="text-xs text-winmark-600 mt-1">
              Click the chat icon in the bottom right to ask questions!
            </p>
          </div>
        </div>
      </aside>
    </>
  )
}
