import React, { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { jobsAPI, driversAPI } from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogClose,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatDateTime, getStatusColor } from '@/lib/utils'
import {
  MapPin,
  Calendar,
  User,
  Phone,
  Mail,
  DollarSign,
  Package,
  Image as ImageIcon,
  Truck,
} from 'lucide-react'
import { toast } from 'sonner'

export default function JobDetailModal({ job, open, onClose, onUpdate }) {
  const [selectedStatus, setSelectedStatus] = useState(job.status)

  const updateStatusMutation = useMutation({
    mutationFn: (status) => jobsAPI.updateStatus(job.id, status),
    onSuccess: () => {
      toast.success('Job status updated')
      onUpdate()
      onClose()
    },
    onError: () => {
      toast.error('Failed to update job status')
    },
  })

  const statuses = ['pending', 'scheduled', 'in-progress', 'completed', 'cancelled']

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogClose onClose={onClose} />
        <DialogHeader>
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="text-2xl">Job #{job.id}</DialogTitle>
              <DialogDescription>Created {formatDateTime(job.created_at)}</DialogDescription>
            </div>
            <Badge className={getStatusColor(job.status)}>{job.status}</Badge>
          </div>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Customer Info */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Customer Information</h3>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span>{job.customer_name}</span>
              </div>
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <span>{job.customer_phone}</span>
              </div>
              {job.customer_email && (
                <div className="flex items-center gap-2">
                  <Mail className="h-4 w-4 text-muted-foreground" />
                  <span>{job.customer_email}</span>
                </div>
              )}
              <div className="flex items-start gap-2">
                <MapPin className="h-4 w-4 text-muted-foreground mt-0.5" />
                <span>{job.address}</span>
              </div>
            </div>
          </div>

          {/* Job Details */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Job Details</h3>
            <div className="space-y-2">
              {job.scheduled_date && (
                <div className="flex items-center gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground" />
                  <span>Scheduled: {formatDateTime(job.scheduled_date)}</span>
                </div>
              )}
              {job.driver_name && (
                <div className="flex items-center gap-2">
                  <Truck className="h-4 w-4 text-muted-foreground" />
                  <span>Driver: {job.driver_name}</span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <span className="font-semibold">{formatCurrency(job.total_price || 0)}</span>
              </div>
              {job.items && job.items.length > 0 && (
                <div className="mt-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Package className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">Items ({job.items.length})</span>
                  </div>
                  <ul className="ml-6 space-y-1">
                    {job.items.map((item, idx) => (
                      <li key={idx} className="text-sm">
                        {item.name} - {formatCurrency(item.price)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          {/* Photos */}
          {job.photos && job.photos.length > 0 && (
            <div>
              <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
                <ImageIcon className="h-5 w-5" />
                Photos ({job.photos.length})
              </h3>
              <div className="grid grid-cols-3 gap-2">
                {job.photos.map((photo, idx) => (
                  <img
                    key={idx}
                    src={photo.url}
                    alt={`Job photo ${idx + 1}`}
                    className="w-full h-32 object-cover rounded-lg border"
                  />
                ))}
              </div>
            </div>
          )}

          {/* Map */}
          {job.latitude && job.longitude && (
            <div>
              <h3 className="font-semibold text-lg mb-3">Location</h3>
              <div className="w-full h-48 bg-gray-200 rounded-lg flex items-center justify-center">
                <p className="text-muted-foreground">Map placeholder</p>
                <p className="text-xs text-muted-foreground ml-2">
                  ({job.latitude}, {job.longitude})
                </p>
              </div>
            </div>
          )}

          {/* Notes */}
          {job.notes && (
            <div>
              <h3 className="font-semibold text-lg mb-3">Notes</h3>
              <p className="text-sm bg-gray-50 p-3 rounded-lg">{job.notes}</p>
            </div>
          )}

          {/* Status Updates */}
          <div>
            <h3 className="font-semibold text-lg mb-3">Update Status</h3>
            <div className="flex flex-wrap gap-2">
              {statuses.map((status) => (
                <Button
                  key={status}
                  variant={selectedStatus === status ? 'default' : 'outline'}
                  onClick={() => {
                    setSelectedStatus(status)
                    updateStatusMutation.mutate(status)
                  }}
                  disabled={updateStatusMutation.isPending}
                  className="capitalize"
                >
                  {status}
                </Button>
              ))}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex justify-end gap-2 pt-4 border-t">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
            <Button>Edit Job</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
