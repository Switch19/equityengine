import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 text-center">
      <p className="font-mono text-beacon-600 text-sm mb-2">404</p>
      <h1 className="text-2xl font-display font-semibold">This page doesn't exist.</h1>
      <p className="text-slate mt-2 max-w-sm">
        The link may be broken, or the page may have moved.
      </p>
      <Link to="/" className="btn-primary mt-6">
        Back to EquityEngine
      </Link>
    </div>
  );
}
