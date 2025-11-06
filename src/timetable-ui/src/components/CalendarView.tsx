interface Activity {
  id: number
  day: string
  start_time: string
  activity_name: string
  end_time: string
  notes: string | null
}

interface CalendarViewProps {
  activities: Activity[]
}

// Generate 30-min timeslots from 8:00 AM to 4:00 PM
const generateTimeslots = (): string[] => {
  const timeslots: string[] = []
  for (let hour = 8; hour < 16; hour++) {
    timeslots.push(`${hour}:00`)
    timeslots.push(`${hour}:30`)
  }
  return timeslots
}

// Convert time string to minutes from midnight for comparison
const timeToMinutes = (time: string): number => {
  const [hours, minutes] = time.split(':').map(Number)
  return hours * 60 + minutes
}

// Find all activities in a specific timeslot
const getActivitiesForSlot = (
  day: string,
  slotStart: string,
  slotEnd: string,
  activities: Activity[]
): Activity[] => {
  const slotStartMins = timeToMinutes(slotStart)
  const slotEndMins = timeToMinutes(slotEnd)

  return activities.filter((activity) => {
    if (activity.day.toLowerCase() !== day.toLowerCase()) return false

    const actStartMins = timeToMinutes(activity.start_time)
    const actEndMins = timeToMinutes(activity.end_time)

    // Check if activity overlaps with this timeslot
    return actStartMins < slotEndMins && actEndMins > slotStartMins
  })
}

export default function CalendarView({ activities }: CalendarViewProps) {
  const days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
  const timeslots = generateTimeslots()

  // Next timeslot for determining cell height
  const getNextTimeslot = (index: number): string => {
    return timeslots[index + 1] || '16:00'
  }

  return (
    <div className="calendar-wrapper">
      <div className="calendar-table">
        {/* Header row with days */}
        <div className="calendar-header">
          <div className="time-column-header"></div>
          {days.map((day) => (
            <div key={day} className="day-header">
              {day}
            </div>
          ))}
        </div>

        {/* Timeslot rows */}
        {timeslots.map((timeslot, idx) => (
          <div key={timeslot} className="calendar-row">
            {/* Time label column */}
            <div className="time-cell">{timeslot}</div>

            {/* Activity cells for each day */}
            {days.map((day) => {
              const nextTimeslot = getNextTimeslot(idx)
              const slotActivities = getActivitiesForSlot(day, timeslot, nextTimeslot, activities)

              return (
                <div key={`${day}-${timeslot}`} className="activity-cell">
                  {slotActivities.length > 0 && (
                    <div className="activities-in-slot">
                      {slotActivities.map((activity) => (
                        <div key={activity.id} className="activity-item">
                          <div className="activity-name">{activity.activity_name}</div>
                          <div className="activity-time">
                            {activity.start_time} - {activity.end_time}
                          </div>
                          {activity.notes && (
                            <div className="activity-notes">{activity.notes}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}
