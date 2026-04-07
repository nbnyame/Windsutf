import { Building, MapPin, Clock, Car, Coffee, Phone } from 'lucide-react'

const FACILITIES_INFO = [
  {
    title: 'Office Location',
    icon: MapPin,
    color: 'bg-blue-50 text-blue-600',
    content: (
      <div>
        <p className="text-sm text-slate-600 mb-2">
          <strong>Winmark Corporation Headquarters</strong><br />
          605 Highway 169 North, Suite 400<br />
          Minneapolis, MN 55441
        </p>
        <p className="text-sm text-slate-500">
          Accessible from Highway 169. Main entrance is on the east side of the building.
        </p>
      </div>
    ),
  },
  {
    title: 'Office Hours',
    icon: Clock,
    color: 'bg-green-50 text-green-600',
    content: (
      <div>
        <p className="text-sm text-slate-600 mb-2">
          <strong>Core hours:</strong> 8:00 AM – 5:00 PM, Monday – Friday
        </p>
        <p className="text-sm text-slate-600 mb-2">
          <strong>Building access:</strong> 6:00 AM – 8:00 PM with your badge
        </p>
        <p className="text-sm text-slate-500">
          Flexible scheduling is available — talk to your manager about adjusting your hours.
        </p>
      </div>
    ),
  },
  {
    title: 'Parking',
    icon: Car,
    color: 'bg-amber-50 text-amber-600',
    content: (
      <div>
        <p className="text-sm text-slate-600 mb-2">
          Free parking is available in the company parking lot adjacent to the building.
        </p>
        <p className="text-sm text-slate-600 mb-2">
          No parking permit required. Visitor parking is in the front row.
        </p>
        <p className="text-sm text-slate-500">
          During winter, please be mindful of snow removal schedules posted in the lobby.
        </p>
      </div>
    ),
  },
  {
    title: 'Break Room & Kitchen',
    icon: Coffee,
    color: 'bg-pink-50 text-pink-600',
    content: (
      <div>
        <p className="text-sm text-slate-600 mb-2">The break room is on the 1st floor and includes:</p>
        <ul className="space-y-1 text-sm text-slate-600 ml-4">
          <li className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0" />
            Full kitchen with refrigerator, microwave, and coffee maker
          </li>
          <li className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0" />
            Vending machines with snacks and beverages
          </li>
          <li className="flex items-start gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-slate-300 mt-1.5 flex-shrink-0" />
            Complimentary coffee, tea, and water
          </li>
        </ul>
        <p className="text-sm text-slate-500 mt-2">
          Several restaurants are within walking distance — ask your lunch buddy for recommendations!
        </p>
      </div>
    ),
  },
  {
    title: 'Key Contacts',
    icon: Phone,
    color: 'bg-purple-50 text-purple-600',
    content: (
      <div className="space-y-2 text-sm text-slate-600">
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="font-medium">IT Help Desk</span>
          <span className="text-slate-500">ext. 4357</span>
        </div>
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="font-medium">HR Department</span>
          <span className="text-slate-500">ext. 2100</span>
        </div>
        <div className="flex justify-between items-center py-1 border-b border-slate-100">
          <span className="font-medium">Facilities</span>
          <span className="text-slate-500">ext. 3200</span>
        </div>
        <div className="flex justify-between items-center py-1">
          <span className="font-medium">Payroll</span>
          <span className="text-slate-500">payroll@winmarkcorporation.com</span>
        </div>
      </div>
    ),
  },
]

export default function Facilities() {
  return (
    <div>
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Building className="w-6 h-6 text-winmark-500" />
          <h1 className="text-2xl font-bold text-slate-800">Office & Facilities</h1>
        </div>
        <p className="text-slate-500">Everything about the office, parking, and amenities.</p>
      </div>

      <div className="space-y-4">
        {FACILITIES_INFO.map((section, index) => {
          const Icon = section.icon
          return (
            <div key={index} className="bg-white rounded-xl border border-slate-200 p-5">
              <div className="flex items-center gap-3 mb-3">
                <div className={`p-2 rounded-lg ${section.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <h3 className="font-semibold text-slate-800">{section.title}</h3>
              </div>
              <div className="ml-11">{section.content}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
