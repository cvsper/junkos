import React from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd'
import { jobsAPI, driversAPI } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { MapPin, Clock, DollarSign, Package } from 'lucide-react'
import { toast } from 'sonner'

export default function DispatchPage() {
  const { data: jobsData, refetch: refetchJobs } = useQuery({
    queryKey: ['jobs', 'unassigned'],
    queryFn: async () => {
      const response = await jobsAPI.getAll({ assigned: false, status: 'scheduled' })
      return response.data
    },
  })

  const { data: driversData } = useQuery({
    queryKey: ['drivers', 'active'],
    queryFn: async () => {
      const response = await driversAPI.getAll({ available: true })
      return response.data
    },
  })

  const assignJobMutation = useMutation({
    mutationFn: ({ jobId, driverId }) => jobsAPI.assignDriver(jobId, driverId),
    onSuccess: () => {
      toast.success('Job assigned successfully')
      refetchJobs()
    },
    onError: () => {
      toast.error('Failed to assign job')
    },
  })

  const handleDragEnd = (result) => {
    const { source, destination } = result

    if (!destination) return

    // If dropped in unassigned, do nothing (would need unassign API)
    if (destination.droppableId === 'unassigned') {
      toast.info('Drop on a driver to assign')
      return
    }

    const jobId = result.draggableId.replace('job-', '')
    const driverId = destination.droppableId.replace('driver-', '')

    assignJobMutation.mutate({ jobId, driverId })
  }

  const unassignedJobs = jobsData?.jobs || []
  const drivers = driversData?.drivers || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dispatch</h1>
        <p className="text-muted-foreground">Assign jobs to available drivers</p>
      </div>

      <DragDropContext onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Unassigned Jobs */}
          <div className="lg:col-span-1">
            <Card>
              <CardHeader>
                <CardTitle>Unassigned Jobs ({unassignedJobs.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <Droppable droppableId="unassigned">
                  {(provided, snapshot) => (
                    <div
                      ref={provided.innerRef}
                      {...provided.droppableProps}
                      className={`space-y-2 min-h-[200px] p-2 rounded-lg transition-colors ${
                        snapshot.isDraggingOver ? 'bg-blue-50' : ''
                      }`}
                    >
                      {unassignedJobs.map((job, index) => (
                        <Draggable key={job.id} draggableId={`job-${job.id}`} index={index}>
                          {(provided, snapshot) => (
                            <div
                              ref={provided.innerRef}
                              {...provided.draggableProps}
                              {...provided.dragHandleProps}
                              className={`bg-white border rounded-lg p-3 shadow-sm hover:shadow-md transition-shadow cursor-move ${
                                snapshot.isDragging ? 'shadow-lg rotate-2' : ''
                              }`}
                            >
                              <div className="space-y-2">
                                <div className="flex items-start justify-between">
                                  <h4 className="font-semibold text-sm">{job.customer_name}</h4>
                                  <Badge variant="outline" className="text-xs">
                                    {formatCurrency(job.total_price)}
                                  </Badge>
                                </div>
                                <div className="flex items-start gap-1 text-xs text-muted-foreground">
                                  <MapPin className="h-3 w-3 mt-0.5 flex-shrink-0" />
                                  <span className="line-clamp-2">{job.address}</span>
                                </div>
                                {job.scheduled_date && (
                                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                                    <Clock className="h-3 w-3" />
                                    {formatDateTime(job.scheduled_date)}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </Draggable>
                      ))}
                      {provided.placeholder}
                      {unassignedJobs.length === 0 && (
                        <div className="text-center py-8 text-muted-foreground text-sm">
                          No unassigned jobs
                        </div>
                      )}
                    </div>
                  )}
                </Droppable>
              </CardContent>
            </Card>
          </div>

          {/* Driver Columns */}
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-4">
            {drivers.map((driver) => (
              <Card key={driver.id}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <span className="text-base">{driver.name}</span>
                    <Badge variant={driver.available ? 'default' : 'secondary'}>
                      {driver.available ? 'Available' : 'Busy'}
                    </Badge>
                  </CardTitle>
                  {driver.current_location && (
                    <p className="text-xs text-muted-foreground">{driver.current_location}</p>
                  )}
                </CardHeader>
                <CardContent>
                  <Droppable droppableId={`driver-${driver.id}`}>
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.droppableProps}
                        className={`space-y-2 min-h-[150px] p-2 rounded-lg transition-colors ${
                          snapshot.isDraggingOver ? 'bg-green-50 border-2 border-green-300' : 'bg-gray-50'
                        }`}
                      >
                        {driver.assigned_jobs?.map((job, index) => (
                          <div
                            key={job.id}
                            className="bg-white border rounded-lg p-3 shadow-sm"
                          >
                            <div className="space-y-2">
                              <div className="flex items-start justify-between">
                                <h4 className="font-semibold text-sm">{job.customer_name}</h4>
                                <span className="text-xs font-medium">{formatCurrency(job.total_price)}</span>
                              </div>
                              <div className="flex items-start gap-1 text-xs text-muted-foreground">
                                <MapPin className="h-3 w-3 mt-0.5 flex-shrink-0" />
                                <span className="line-clamp-1">{job.address}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                        {provided.placeholder}
                        {(!driver.assigned_jobs || driver.assigned_jobs.length === 0) && (
                          <div className="text-center py-6 text-muted-foreground text-sm">
                            Drop jobs here
                          </div>
                        )}
                      </div>
                    )}
                  </Droppable>
                  <div className="mt-3 text-xs text-muted-foreground">
                    {driver.assigned_jobs?.length || 0} job(s) assigned
                  </div>
                </CardContent>
              </Card>
            ))}
            {drivers.length === 0 && (
              <Card className="md:col-span-2">
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground">No available drivers</p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </DragDropContext>
    </div>
  )
}
