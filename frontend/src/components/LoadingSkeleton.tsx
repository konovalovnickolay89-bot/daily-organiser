type LoadingSkeletonProps = {
  label: string;
};

/** A static cream placeholder. It is not a chat bubble. */
export function LoadingSkeleton({ label }: LoadingSkeletonProps) {
  return (
    <div className="mt-2" aria-busy="true" data-state="loading">
      <p className="sr-only">{label}</p>
      <span className="my-2 block h-2 max-w-full rounded-house bg-[var(--sunken)]" />
      <span className="my-2 block h-2 max-w-full rounded-house bg-[var(--sunken)]" />
      <span className="my-2 block h-2 w-2/3 rounded-house bg-[var(--sunken)]" />
    </div>
  );
}
