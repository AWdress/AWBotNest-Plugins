import { Button } from '@/components/ui/button'

export function MaintenanceError() {
  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>503</h1>
        <span className='font-medium'>护山大阵整修中</span>
        <p className='text-center text-muted-foreground'>
          此界山门暂且封闭，诸般法阵正在调息。<br />
          待灵气归位后，便会重新开山迎客。
        </p>
        <div className='mt-6 flex gap-4'>
          <Button variant='outline'>查看告示</Button>
        </div>
      </div>
    </div>
  )
}
