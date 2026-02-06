import React from 'react'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatDateTime, getStatusColor } from '@/lib/utils'
import { MapPin, Calendar, User, DollarSign } from 'lucide-react'

export default function JobCard({ job, onClick }) {
  return (
    <Card className="cursor-pointer hover:shadow-lg transition-shadow" onClick={onClick}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h3 className="font-semibold text-lg">{job.customer_name}</h3>
            <p className="text-sm text-muted-foreground">{job.customer_phone}</p>
          </div>
          <Badge className={getStatusColor(job.status)}>{job.status}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-start gap-2">
          <MapPin className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
          <p className="text-sm">{job.address}</p>
        </div>
        
        {job.scheduled_date && (
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm">{formatDateTime(job.scheduled_date)}</p>
          </div>
        )}

        {job.driver_name && (
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-muted-foreground" />
            <p className="text-sm">{job.driver_name}</p>
          </div>
        )}

        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-muted-foreground" />
            <span className="font-semibold">{formatCurrency(job.total_price || 0)}</span>
          </div>
          {job.item_count && (
            <span className="text-sm text-muted-foreground">{job.item_count} items</span>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
