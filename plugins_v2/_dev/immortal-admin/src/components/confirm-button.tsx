import { useState, type ReactNode } from 'react'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"

interface ConfirmButtonProps {
  triggerText: ReactNode
  title?: string
  description?: string
  confirmText?: string
  cancelText?: string
  pendingText?: string
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
  onConfirm: () => void | Promise<void>
  disabled?: boolean
  confirmDisabled?: boolean
  className?: string
}

export function ConfirmButton({
  triggerText,
  title = "确认操作",
  description = "此操作不可撤销，是否继续？",
  confirmText = "确认",
  cancelText = "取消",
  pendingText = "处理中...",
  variant = "default",
  onConfirm,
  disabled = false,
  confirmDisabled = false,
  className,
}: ConfirmButtonProps) {
  const [isConfirming, setIsConfirming] = useState(false)
  const isActionDisabled = disabled || confirmDisabled || isConfirming

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button variant={variant} disabled={disabled || isConfirming} className={className}>
          {triggerText}
        </Button>
      </AlertDialogTrigger>

      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isConfirming}>{cancelText}</AlertDialogCancel>
          <AlertDialogAction
            disabled={isActionDisabled}
            onClick={async (event) => {
              if (isActionDisabled) {
                event.preventDefault()
                return
              }

              try {
                setIsConfirming(true)
                await onConfirm()
              } finally {
                setIsConfirming(false)
              }
            }}
          >
            {isConfirming ? pendingText : confirmText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
