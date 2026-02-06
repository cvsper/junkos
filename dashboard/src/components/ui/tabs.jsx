import * as React from 'react'
import { cn } from '@/lib/utils'

const Tabs = ({ defaultValue, value: controlledValue, onValueChange, children, className }) => {
  const [value, setValue] = React.useState(defaultValue)
  const currentValue = controlledValue !== undefined ? controlledValue : value

  const handleValueChange = (newValue) => {
    if (controlledValue === undefined) {
      setValue(newValue)
    }
    onValueChange?.(newValue)
  }

  return (
    <div className={className}>
      {React.Children.map(children, (child) =>
        React.isValidElement(child)
          ? React.cloneElement(child, { value: currentValue, onValueChange: handleValueChange })
          : child
      )}
    </div>
  )
}

const TabsList = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      'inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground',
      className
    )}
    {...props}
  />
))
TabsList.displayName = 'TabsList'

const TabsTrigger = React.forwardRef(({ className, value: tabValue, currentValue, onValueChange, ...props }, ref) => {
  const isActive = currentValue === tabValue
  return (
    <button
      ref={ref}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        isActive && 'bg-background text-foreground shadow-sm',
        className
      )}
      onClick={() => onValueChange(tabValue)}
      {...props}
    />
  )
})
TabsTrigger.displayName = 'TabsTrigger'

const TabsContent = React.forwardRef(({ className, value: tabValue, currentValue, ...props }, ref) => {
  if (currentValue !== tabValue) return null
  return (
    <div
      ref={ref}
      className={cn(
        'mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className
      )}
      {...props}
    />
  )
})
TabsContent.displayName = 'TabsContent'

// Enhance children with context values
const EnhancedTabsList = ({ value, onValueChange, children, ...props }) => (
  <TabsList {...props}>
    {React.Children.map(children, (child) =>
      React.isValidElement(child)
        ? React.cloneElement(child, { currentValue: value, onValueChange })
        : child
    )}
  </TabsList>
)

const EnhancedTabsContent = ({ value, children, ...props }) =>
  React.Children.map(children, (child) =>
    React.isValidElement(child) ? React.cloneElement(child, { currentValue: value }) : child
  )

export { Tabs, EnhancedTabsList as TabsList, TabsTrigger, TabsContent }
