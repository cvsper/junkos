import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { jobsAPI } from '@/lib/api'
import { Calendar, dateFnsLocalizer } from 'react-big-calendar'
import { format, parse, startOfWeek, getDay } from 'date-fns'
import { enUS } from 'date-fns/locale'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatCurrency, getStatusColor } from '@/lib/utils'
import JobDetailModal from '@/components/jobs/JobDetailModal'
import 'react-big-calendar/lib/css/react-big-calendar.css'

const locales = {
  'en-US': enUS,
}

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek,
  getDay,
  locales,
})

export default function CalendarPage() {
  const [selectedJob, setSelectedJob] = useState(null)
  const [currentDate, setCurrentDate] = useState(new Date())

  const { data, refetch } = useQuery({
    queryKey: ['jobs', 'scheduled'],
    queryFn: async () => {
      const response = await jobsAPI.getAll({ has_schedule: true })
      return response.data
    },
  })

  const events = useMemo(() => {
    return (data?.jobs || []).map((job) => ({
      id: job.id,
      title: `${job.customer_name} - ${formatCurrency(job.total_price)}`,
      start: new Date(job.scheduled_date),
      end: new Date(new Date(job.scheduled_date).getTime() + 2 * 60 * 60 * 1000), // 2 hours default
      resource: job,
    }))
  }, [data])

  const eventStyleGetter = (event) => {
    const job = event.resource
    let backgroundColor = '#3b82f6' // default blue

    switch (job.status) {
      case 'pending':
        backgroundColor = '#f59e0b' // yellow
        break
      case 'in-progress':
        backgroundColor = '#8b5cf6' // purple
        break
      case 'completed':
        backgroundColor = '#10b981' // green
        break
      case 'cancelled':
        backgroundColor = '#ef4444' // red
        break
    }

    return {
      style: {
        backgroundColor,
        borderRadius: '5px',
        opacity: 0.9,
        color: 'white',
        border: '0px',
        display: 'block',
      },
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Calendar</h1>
          <p className="text-muted-foreground">Schedule and view upcoming jobs</p>
        </div>
        <Button>Schedule New Job</Button>
      </div>

      <Card className="p-6">
        <style>
          {`
            .rbc-calendar {
              font-family: inherit;
            }
            .rbc-header {
              padding: 12px 3px;
              font-weight: 600;
              border-bottom: 2px solid #e5e7eb;
            }
            .rbc-today {
              background-color: #eff6ff;
            }
            .rbc-event {
              padding: 4px 6px;
              font-size: 13px;
            }
            .rbc-toolbar button {
              padding: 6px 12px;
              border-radius: 6px;
              border: 1px solid #e5e7eb;
              background: white;
              font-weight: 500;
            }
            .rbc-toolbar button:hover {
              background: #f3f4f6;
            }
            .rbc-toolbar button.rbc-active {
              background: hsl(var(--primary));
              color: white;
              border-color: hsl(var(--primary));
            }
          `}
        </style>
        <Calendar
          localizer={localizer}
          events={events}
          startAccessor="start"
          endAccessor="end"
          style={{ height: 600 }}
          eventStyleGetter={eventStyleGetter}
          onSelectEvent={(event) => setSelectedJob(event.resource)}
          views={['month', 'week', 'day', 'agenda']}
          defaultView="month"
          date={currentDate}
          onNavigate={(date) => setCurrentDate(date)}
        />
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#f59e0b' }} />
            <div>
              <p className="text-sm font-medium">Pending</p>
              <p className="text-xs text-muted-foreground">Awaiting confirmation</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#3b82f6' }} />
            <div>
              <p className="text-sm font-medium">Scheduled</p>
              <p className="text-xs text-muted-foreground">Ready to go</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#8b5cf6' }} />
            <div>
              <p className="text-sm font-medium">In Progress</p>
              <p className="text-xs text-muted-foreground">Driver on site</p>
            </div>
          </div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#10b981' }} />
            <div>
              <p className="text-sm font-medium">Completed</p>
              <p className="text-xs text-muted-foreground">Job finished</p>
            </div>
          </div>
        </Card>
      </div>

      {selectedJob && (
        <JobDetailModal
          job={selectedJob}
          open={!!selectedJob}
          onClose={() => setSelectedJob(null)}
          onUpdate={refetch}
        />
      )}
    </div>
  )
}
