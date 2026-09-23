export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return 'Just now';

  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 'Recently';

  const deltaSeconds = Math.max(0, Math.round((Date.now() - timestamp) / 1000));
  if (deltaSeconds < 60) return 'Just now';

  const deltaMinutes = Math.round(deltaSeconds / 60);
  if (deltaMinutes < 60) return `${deltaMinutes}m ago`;

  const deltaHours = Math.round(deltaMinutes / 60);
  if (deltaHours < 24) return `${deltaHours}h ago`;

  const deltaDays = Math.round(deltaHours / 24);
  if (deltaDays < 7) return `${deltaDays}d ago`;

  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(new Date(timestamp));
}

export function formatDueLabel(value: string | null | undefined): string {
  if (!value) return 'No due date';

  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return 'Upcoming';

  const today = new Date();
  const due = new Date(timestamp);
  const dayDiff = Math.floor((Date.UTC(due.getFullYear(), due.getMonth(), due.getDate()) - Date.UTC(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);

  if (dayDiff < 0) return 'Overdue';
  if (dayDiff === 0) return 'Due today';
  if (dayDiff === 1) return 'Due tomorrow';
  return `Due in ${dayDiff} days`;
}
