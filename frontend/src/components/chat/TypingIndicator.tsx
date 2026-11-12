export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-2" role="status" aria-label="Assistant is responding">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="size-1.5 animate-bounce rounded-full bg-gray-400 dark:bg-gray-500"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  )
}
