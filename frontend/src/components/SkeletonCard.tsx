export function SkeletonCard() {
  return (
    <div className="card-movie skeleton" aria-hidden="true">
      <div className="poster shimmer" />
      <div className="card-body">
        <div className="sk-line shimmer" style={{ width: "75%" }} />
        <div className="sk-line shimmer" style={{ width: "40%" }} />
        <div className="sk-line shimmer" style={{ width: "90%" }} />
      </div>
    </div>
  );
}
