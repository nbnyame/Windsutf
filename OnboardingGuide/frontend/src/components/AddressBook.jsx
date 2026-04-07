import { BookOpen, ExternalLink } from 'lucide-react'

export default function AddressBook() {
  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <BookOpen className="w-6 h-6 text-winmark-500" />
          <h1 className="text-2xl font-bold text-slate-800">Address Book</h1>
        </div>
        <p className="text-slate-500">
          Look up employee contact information, phone extensions, and departments.
        </p>
      </div>

      {/* Quick Access Link */}
      <div className="bg-winmark-50 rounded-xl p-4 border border-winmark-100 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-winmark-700 text-sm">Winmark Phone Directory</h3>
            <p className="text-xs text-winmark-600 mt-1">
              Search by name or department to find contact details.
            </p>
          </div>
          <a
            href="https://addressbook.winmarkcorporation.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 bg-winmark-500 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-winmark-600 transition-colors"
          >
            Open Directory
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Embedded Address Book */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="bg-slate-50 px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-600">Phone Directory</span>
          <a
            href="https://addressbook.winmarkcorporation.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-winmark-500 hover:text-winmark-600 flex items-center gap-1"
          >
            Open in new tab <ExternalLink className="w-3 h-3" />
          </a>
        </div>
        <iframe
          src="https://addressbook.winmarkcorporation.com"
          title="Winmark Phone Directory"
          className="w-full border-0"
          style={{ height: '600px' }}
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>

      {/* Fallback Info */}
      <div className="mt-4 bg-slate-50 rounded-xl p-4 border border-slate-100">
        <p className="text-xs text-slate-500">
          If the directory doesn't load above, you can access it directly at{' '}
          <a
            href="https://addressbook.winmarkcorporation.com"
            target="_blank"
            rel="noopener noreferrer"
            className="text-winmark-500 underline"
          >
            addressbook.winmarkcorporation.com
          </a>
          . For urgent lookups, contact the front desk at extension 0.
        </p>
      </div>
    </div>
  )
}
