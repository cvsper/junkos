import React, { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { driversAPI } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Phone, Mail, MapPin, Truck, Plus, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

export default function DriversPage() {
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['drivers'],
    queryFn: async () => {
      const response = await driversAPI.getAll()
      return response.data
    },
  })

  const updateAvailabilityMutation = useMutation({
    mutationFn: ({ id, available }) => driversAPI.updateAvailability(id, available),
    onSuccess: () => {
      toast.success('Driver availability updated')
      refetch()
    },
    onError: () => {
      toast.error('Failed to update availability')
    },
  })

  const drivers = data?.drivers || []

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Drivers</h1>
          <p className="text-muted-foreground">Manage your driver team</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Add Driver
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Card key={i}>
              <CardHeader>
                <div className="h-4 bg-gray-200 rounded w-32 animate-pulse" />
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="h-3 bg-gray-200 rounded w-full animate-pulse" />
                  <div className="h-3 bg-gray-200 rounded w-3/4 animate-pulse" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : drivers.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Truck className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground">No drivers found</p>
            <Button className="mt-4">
              <Plus className="mr-2 h-4 w-4" />
              Add Your First Driver
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {drivers.map((driver) => (
            <Card key={driver.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>{driver.name}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">#{driver.id}</p>
                  </div>
                  <Badge variant={driver.available ? 'default' : 'secondary'}>
                    {driver.available ? 'Available' : 'Unavailable'}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <Phone className="h-4 w-4 text-muted-foreground" />
                    <span>{driver.phone}</span>
                  </div>
                  {driver.email && (
                    <div className="flex items-center gap-2 text-sm">
                      <Mail className="h-4 w-4 text-muted-foreground" />
                      <span>{driver.email}</span>
                    </div>
                  )}
                  {driver.current_location && (
                    <div className="flex items-start gap-2 text-sm">
                      <MapPin className="h-4 w-4 text-muted-foreground mt-0.5" />
                      <span className="line-clamp-2">{driver.current_location}</span>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Availability</span>
                    <Switch
                      checked={driver.available}
                      onCheckedChange={(checked) =>
                        updateAvailabilityMutation.mutate({ id: driver.id, available: checked })
                      }
                      disabled={updateAvailabilityMutation.isPending}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-center">
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-2xl font-bold">{driver.jobs_today || 0}</p>
                      <p className="text-xs text-muted-foreground">Jobs Today</p>
                    </div>
                    <div className="bg-gray-50 rounded-lg p-2">
                      <p className="text-2xl font-bold">{driver.jobs_total || 0}</p>
                      <p className="text-xs text-muted-foreground">Total Jobs</p>
                    </div>
                  </div>
                </div>

                <Button variant="outline" className="w-full" size="sm">
                  View Details
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
