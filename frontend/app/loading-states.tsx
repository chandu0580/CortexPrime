export function PageLoading() {
  return <div className="flex items-center justify-center min-h-[400px]"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" /></div>;
}

export function PageError({ message }: { message?: string }) {
  return <div className="flex flex-col items-center justify-center min-h-[400px] text-destructive"><p>{message || 'Failed to load page'}</p></div>;
}

export function PageEmpty({ message }: { message?: string }) {
  return <div className="flex flex-col items-center justify-center min-h-[400px] text-muted-foreground"><p>{message || 'No data available'}</p></div>;
}
