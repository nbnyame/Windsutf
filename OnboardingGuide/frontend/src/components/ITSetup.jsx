import { Monitor, Mail, Shield, Key, Wrench, MessageSquare, ExternalLink } from 'lucide-react'

const IT_SECTIONS = [
  {
    title: 'Email (Microsoft 365)',
    icon: Mail,
    color: 'bg-blue-50 text-blue-600',
    content: [
      'Your corporate email will be pre-configured on your laptop.',
      'Access webmail at https://outlook.office365.com',
      'Sign in with your company credentials (provided by IT on Day 1).',
      'Mobile setup: Download Outlook from App Store or Google Play.',
    ],
  },
  {
    title: 'VPN (GlobalProtect)',
    icon: Shield,
    color: 'bg-green-50 text-green-600',
    content: [
      'Open the GlobalProtect VPN client (pre-installed).',
      'Portal address: vpn.winmarkcorporation.com',
      'Sign in with your network credentials.',
      'Required when working remotely to access internal systems.',
    ],
  },
  {
    title: 'Password Management',
    icon: Key,
    color: 'bg-amber-50 text-amber-600',
    content: [
      'Reset at: https://passwordreset.winmarkcorporation.com',
      'Or press Ctrl+Alt+Delete → Change Password on your laptop.',
      'Minimum 12 characters with upper/lowercase, numbers, and symbols.',
      'Passwords expire every 90 days.',
    ],
  },
  {
    title: 'Standard Software',
    icon: Wrench,
    color: 'bg-purple-50 text-purple-600',
    content: [
      'Microsoft 365 (Outlook, Word, Excel, PowerPoint, Teams)',
      'GlobalProtect VPN',
      'Adobe Acrobat Reader',
      'Department-specific tools (your manager will guide you).',
      'Request additional software via IT Help Desk.',
    ],
  },
  {
    title: 'Microsoft Teams',
    icon: MessageSquare,
    color: 'bg-pink-50 text-pink-600',
    content: [
      'Primary tool for chat, meetings, and collaboration.',
      'Pre-installed on laptop; also available on mobile.',
      'Your manager will add you to relevant team channels.',
      'Use it for direct messages, group chats, and video calls.',
    ],
  },
]

export default function ITSetup() {
  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Monitor className="w-6 h-6 text-winmark-500" />
          <h1 className="text-2xl font-bold text-slate-800">IT & Technology Setup</h1>
        </div>
        <p className="text-slate-500">Everything you need to get your tech up and running.</p>
      </div>

      {/* IT Help Desk Banner */}
      <div className="bg-gradient-to-r from-winmark-500 to-winmark-600 rounded-xl p-5 text-white mb-8">
        <h2 className="font-semibold text-lg mb-1">IT Help Desk</h2>
        <p className="text-winmark-100 text-sm mb-3">
          For any technical issues or questions, contact the IT Help Desk:
        </p>
        <div className="flex flex-wrap gap-4 text-sm">
          <span className="bg-white/20 px-3 py-1 rounded-full">Extension: 4357</span>
          <span className="bg-white/20 px-3 py-1 rounded-full">helpdesk@winmarkcorporation.com</span>
        </div>
      </div>

      {/* IT Sections */}
      <div className="space-y-4">
        {IT_SECTIONS.map((section, index) => {
          const Icon = section.icon
          return (
            <div key={index} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg ${section.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <h3 className="font-semibold text-slate-800">{section.title}</h3>
              </div>
              <ul className="space-y-2 ml-11">
                {section.content.map((item, i) => (
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
