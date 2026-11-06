type LoadingSkeletonProps = {
  label: string;
};

/** A static cream placeholder. It is not a chat bubble. */
export function LoadingSkeleton({ label }: LoadingSkeletonProps) {
  return (
    <div className="mt-2" aria-busy="true">
      <p className="sr-only">{label}</p>
      <span className="my-3 block h-3.5 max-w-full rounded-lg bg-[var(--sunken)]" />
      <span className="my-3 block h-3.5 max-w-full rounded-lg bg-[var(--sunken)]" />
      <span className="my-3 block h-3.5 max-w-[58%] rounded-lg bg-[var(--sunken)]" />
    </div>
  );
}
