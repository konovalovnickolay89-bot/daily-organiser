type LoadingSkeletonProps = {
  label: string;
};

/** A static cream placeholder. It is not a chat bubble. */
export function LoadingSkeleton({ label }: LoadingSkeletonProps) {
  return (
    <div className="skeleton" aria-busy="true">
      <p className="sr-only">{label}</p>
      <span className="skeleton-bar" />
      <span className="skeleton-bar" />
      <span className="skeleton-bar is-short" />
    </div>
  );
}
