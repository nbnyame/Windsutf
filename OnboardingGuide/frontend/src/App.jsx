import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Welcome from './components/Welcome'
import FirstDayWeek from './components/FirstDayWeek'
import ITSetup from './components/ITSetup'
import HRBenefits from './components/HRBenefits'
import Facilities from './components/Facilities'
import AddressBook from './components/AddressBook'
import Checklist from './components/Checklist'
import ChatBot from './components/ChatBot'
import { MessageCircle, X } from 'lucide-react'

const PAGES = {
  welcome: Welcome,
  firstday: FirstDayWeek,
  itsetup: ITSetup,
  hrbenefits: HRBenefits,
  facilities: Facilities,
  addressbook: AddressBook,
  checklist: Checklist,
}

export default function App() {
  const [currentPage, setCurrentPage] = useState('welcome')
  const [chatOpen, setChatOpen] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  const PageComponent = PAGES[currentPage] || Welcome

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <Sidebar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
      />

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8">
          <PageComponent setCurrentPage={setCurrentPage} />
        </div>
      </main>

      {/* Chat Bot Toggle Button */}
      <button
        onClick={() => setChatOpen(!chatOpen)}
        className={`fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-lg flex items-center justify-center transition-all duration-300 ${
          chatOpen
            ? 'bg-slate-600 hover:bg-slate-700'
            : 'bg-winmark-500 hover:bg-winmark-600'
        }`}
      >
        {chatOpen ? (
          <X className="w-6 h-6 text-white" />
        ) : (
          <MessageCircle className="w-6 h-6 text-white" />
        )}
      </button>

      {/* Chat Bot Panel */}
      {chatOpen && (
        <div className="fixed bottom-24 right-6 z-40 w-[400px] h-[560px] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden animate-in">
          <ChatBot />
        </div>
      )}
    </div>
  )
}
